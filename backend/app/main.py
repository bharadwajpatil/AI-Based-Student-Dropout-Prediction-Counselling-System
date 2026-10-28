from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Response, status
from fastapi.middleware.cors import CORSMiddleware

from backend.app.core.config import settings
from backend.app.core.logging import setup_logging
from backend.app.core.middleware import (
    NoSQLInjectionMiddleware,
    RateLimitingMiddleware,
    RequestIDMiddleware,
    RequestSizeLimitMiddleware,
    SecurityHeadersMiddleware,
    register_exception_handlers,
)
from backend.app.db.indexes import create_indexes
from backend.app.db.mongo import (
    close_mongo_connection,
    connect_to_mongo,
    get_database,
    ping_database,
)

logger = setup_logging(app_name=settings.APP_NAME, debug=settings.APP_DEBUG)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manages application startup and shutdown lifecycle."""
    logger.info("Starting up %s in %s mode...", settings.APP_NAME, settings.APP_ENV)

    # 1. Connect to MongoDB with retry & exponential backoff
    await connect_to_mongo(
        uri=settings.MONGODB_URI,
        database_name=settings.MONGODB_DATABASE,
        max_retries=settings.MONGODB_MAX_RETRIES,
        initial_delay=settings.MONGODB_RETRY_DELAY,
    )

    # 2. Idempotently initialize indexes
    db = get_database()
    await create_indexes(db)

    logger.info("%s startup complete and ready to receive requests.", settings.APP_NAME)
    yield

    # Shutdown
    logger.info("Shutting down %s...", settings.APP_NAME)
    await close_mongo_connection()
    logger.info("Shutdown complete.")


def create_app() -> FastAPI:
    """Application factory for FastAPI."""
    app = FastAPI(
        title="AI-Based Student Dropout Prediction & Counselling System",
        description="Backend API for student dropout risk prediction, monitoring, and counselling.",
        version=settings.APP_VERSION,
        lifespan=lifespan,
        docs_url="/docs" if settings.APP_DEBUG else None,
        redoc_url="/redoc" if settings.APP_DEBUG else None,
    )

    # 1. CORS Restricted to Configured Origins
    cors_origins = settings.get_cors_origins()
    logger.info("Configured CORS allowed origins: %s", cors_origins)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=[
            "X-Request-ID",
            "X-RateLimit-Limit",
            "X-RateLimit-Remaining",
            "X-RateLimit-Reset",
        ],
    )

    # 2. Hardening Middlewares (OWASP Secure Headers, Request Size Limits, NoSQL Injection Defense, Rate Limiting)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RequestSizeLimitMiddleware)
    app.add_middleware(NoSQLInjectionMiddleware)
    app.add_middleware(RateLimitingMiddleware)

    # 3. Request ID Tracking Middleware
    app.add_middleware(RequestIDMiddleware)

    # 3. Global Structured Exception Handlers
    register_exception_handlers(app, debug=settings.APP_DEBUG)

    # 4. Core Endpoints
    @app.get("/", tags=["Root"])
    async def root():
        return {
            "name": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "environment": settings.APP_ENV,
            "status": "online",
        }

    @app.get("/health", tags=["Health"])
    async def health_check(response: Response):
        """
        Health check endpoint.
        Returns 200 OK if app and database are healthy.
        Returns 503 Service Unavailable if database connection is failing.
        """
        db_healthy = await ping_database()
        if not db_healthy:
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
            return {
                "status": "degraded",
                "app": settings.APP_NAME,
                "version": settings.APP_VERSION,
                "database": "disconnected",
            }

        return {
            "status": "ok",
            "app": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "database": "connected",
        }

    # 5. Routers (mounted at both root and /api/v1 for API versioning and backward compatibility)
    from fastapi import APIRouter
    from backend.app.routers.analytics import router as analytics_router
    from backend.app.routers.auth import router as auth_router
    from backend.app.routers.counselling import router as counselling_router
    from backend.app.routers.events import router as events_router
    from backend.app.routers.imports import router as imports_router
    from backend.app.routers.notifications import router as notifications_router
    from backend.app.routers.students import router as students_router
    from backend.app.routers.admin import router as admin_router
    from backend.app.routers.hod import router as hod_router
    from backend.app.routers.subjects import router as subjects_router
    from backend.app.routers.marks import router as marks_router

    api_v1 = APIRouter(prefix="/api/v1")
    for r in [
        auth_router,
        students_router,
        imports_router,
        counselling_router,
        analytics_router,
        notifications_router,
        events_router,
        admin_router,
        hod_router,
        subjects_router,
        marks_router,
    ]:
        app.include_router(r)
        api_v1.include_router(r)

    app.include_router(api_v1)

    return app




app = create_app()
