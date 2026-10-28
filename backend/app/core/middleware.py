import json
import logging
import time
import uuid
from collections import defaultdict
from collections.abc import Callable
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware

from backend.app.core.config import settings
from backend.app.core.logging import request_id_ctx

logger = logging.getLogger("student-dropout-system.middleware")


class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Extracts or generates an X-Request-ID for every incoming request,
    attaches it to contextvars for logging, and includes it in response headers.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Any:
        incoming_id = request.headers.get("X-Request-ID")
        req_id = incoming_id if incoming_id else str(uuid.uuid4())

        # Set into context variable for logging
        token = request_id_ctx.set(req_id)
        request.state.request_id = req_id

        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = req_id
            return response
        finally:
            request_id_ctx.reset(token)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Applies OWASP-recommended security headers to all responses.
    Guards against MIME-type sniffing, clickjacking, iframe embedding, and XSS.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Any:
        response = await call_next(request)
        if not settings.SECURITY_HEADERS_ENABLED:
            return response

        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"

        if request.url.path in ("/docs", "/redoc", "/openapi.json"):
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
                "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
                "img-src 'self' data: https://fastapi.tiangolo.com; "
                "frame-ancestors 'none'; object-src 'none'; base-uri 'self';"
            )
        else:
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; frame-ancestors 'none'; object-src 'none'; base-uri 'self';"
            )
        response.headers["X-XSS-Protection"] = "0"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"

        if settings.HSTS_ENABLED or request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains; preload"

        return response


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """
    Enforces maximum request body size limits to defend against resource exhaustion DoS.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Any:
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                length = int(content_length)
                is_upload = "/import" in request.url.path
                max_size = settings.MAX_UPLOAD_SIZE_BYTES if is_upload else settings.MAX_REQUEST_SIZE_BYTES
                if length > max_size:
                    return JSONResponse(
                        status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                        content={
                            "error": {
                                "code": "PAYLOAD_TOO_LARGE",
                                "message": f"Request payload ({length} bytes) exceeds maximum limit of {max_size} bytes.",
                            }
                        },
                    )
            except ValueError:
                pass
        return await call_next(request)


def _contains_prohibited_key(obj: Any) -> tuple[bool, str | None]:
    """Recursively checks for keys starting with '$' or containing '.' (NoSQL injection vectors)."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(k, str) and (k.startswith("$") or "." in k):
                return True, k
            has_bad, bad_key = _contains_prohibited_key(v)
            if has_bad:
                return True, bad_key
    elif isinstance(obj, list):
        for item in obj:
            has_bad, bad_key = _contains_prohibited_key(item)
            if has_bad:
                return True, bad_key
    return False, None


class NoSQLInjectionMiddleware(BaseHTTPMiddleware):
    """
    Inspects query parameters and JSON payloads, strictly rejecting keys
    starting with '$' or containing '.' to neutralize NoSQL injection attacks.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Any:
        # 1. Inspect query parameters
        for key in request.query_params.keys():
            if key.startswith("$") or "." in key:
                return JSONResponse(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content={
                        "error": {
                            "code": "PROHIBITED_INPUT_KEY",
                            "message": f"Prohibited query parameter: '{key}'. Keys starting with '$' or containing '.' are forbidden.",
                        }
                    },
                )

        # 2. Inspect JSON request body if present
        content_type = request.headers.get("content-type", "")
        if "application/json" in content_type:
            body_bytes = await request.body()
            if body_bytes:
                try:
                    parsed = json.loads(body_bytes)
                    has_bad, bad_key = _contains_prohibited_key(parsed)
                    if has_bad:
                        return JSONResponse(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            content={
                                "error": {
                                    "code": "PROHIBITED_INPUT_KEY",
                                    "message": f"Prohibited key in JSON payload: '{bad_key}'. Keys starting with '$' or containing '.' are forbidden.",
                                }
                            },
                        )
                except json.JSONDecodeError:
                    pass

                # Reset body so downstream dependencies can parse it
                request._body = body_bytes
                async def receive():
                    return {"type": "http.request", "body": body_bytes}
                request._receive = receive

        return await call_next(request)


class SlidingWindowRateLimiter:
    """In-memory sliding window rate limiter."""

    def __init__(self):
        self.history: dict[str, list[float]] = defaultdict(list)

    def is_allowed(self, client_key: str, limit: int, window_seconds: float = 60.0) -> tuple[bool, int, float]:
        now = time.time()
        cutoff = now - window_seconds
        # Clean expired timestamps
        timestamps = [t for t in self.history[client_key] if t > cutoff]
        self.history[client_key] = timestamps

        if len(timestamps) >= limit:
            oldest = timestamps[0]
            reset_in = max(1.0, oldest + window_seconds - now)
            return False, 0, reset_in

        timestamps.append(now)
        remaining = limit - len(timestamps)
        reset_in = window_seconds
        return True, remaining, reset_in

    def reset(self) -> None:
        self.history.clear()


rate_limiter = SlidingWindowRateLimiter()


class RateLimitingMiddleware(BaseHTTPMiddleware):
    """
    Token/sliding-window rate limiter per IP, enforcing stricter limits on authentication endpoints.
    Adds X-RateLimit headers and returns 429 Too Many Requests when limits are exceeded.
    """

    def __init__(self, app: Any, limiter: SlidingWindowRateLimiter | None = None):
        super().__init__(app)
        self.limiter = limiter or rate_limiter

    async def dispatch(self, request: Request, call_next: Callable) -> Any:
        if not settings.RATE_LIMIT_ENABLED:
            return await call_next(request)

        # Extract client IP
        forwarded = request.headers.get("x-forwarded-for")
        client_ip = forwarded.split(",")[0].strip() if forwarded else (request.client.host if request.client else "unknown")

        path = request.url.path
        is_auth = "/auth/" in path
        limit = settings.RATE_LIMIT_AUTH_PER_MINUTE if is_auth else settings.RATE_LIMIT_GLOBAL_PER_MINUTE
        key = f"{client_ip}:auth" if is_auth else f"{client_ip}:global"

        allowed, remaining, reset_in = self.limiter.is_allowed(key, limit=limit, window_seconds=60.0)

        if not allowed:
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                headers={
                    "Retry-After": str(int(reset_in)),
                    "X-RateLimit-Limit": str(limit),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(int(reset_in)),
                },
                content={
                    "error": {
                        "code": "RATE_LIMIT_EXCEEDED",
                        "message": f"Rate limit exceeded. Please retry after {int(reset_in)} seconds.",
                    }
                },
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(int(reset_in))
        return response


def register_exception_handlers(app: FastAPI, debug: bool = False) -> None:
    """Registers global exception handlers returning {error: {code, message, details}}."""

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        error_code = f"HTTP_{exc.status_code}"
        details: Any | None = None
        message = str(exc.detail)

        # If detail is a dictionary, extract message and details
        if isinstance(exc.detail, dict):
            message = exc.detail.get("message", str(exc.detail))
            details = exc.detail.get("details", None)
            error_code = exc.detail.get("code", error_code)

        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": error_code,
                    "message": message,
                    "details": details,
                }
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        field_errors = []
        for err in exc.errors():
            loc = " -> ".join(str(item) for item in err.get("loc", []))
            field_errors.append(
                {
                    "field": loc,
                    "message": err.get("msg"),
                    "type": err.get("type"),
                }
            )

        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Invalid request payload or parameters.",
                    "details": field_errors,
                }
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled server exception: %s", str(exc))
        details = str(exc) if debug else None

        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": {
                    "code": "INTERNAL_SERVER_ERROR",
                    "message": "An unexpected error occurred. Please try again later.",
                    "details": details,
                }
            },
        )
