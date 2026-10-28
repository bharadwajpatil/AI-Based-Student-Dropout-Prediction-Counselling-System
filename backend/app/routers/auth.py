from datetime import UTC

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status

from bson import ObjectId
from backend.app.core.config import settings
from backend.app.core.deps import get_current_user, require_role
from backend.app.models.user import UserRole, UserStatus
from backend.app.schemas.auth import (
    ForgotPasswordRequest,
    GenericMessageResponse,
    LoginRequest,
    RegisterRequest,
    ResetPasswordRequest,
    TokenResponse,
    UserProfileResponse,
    VerifyEmailRequest,
)
from backend.app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication"])


def get_auth_service() -> AuthService:
    return AuthService()


@router.post("/register", response_model=GenericMessageResponse)
async def register(
    req: RegisterRequest,
    auth_service: AuthService = Depends(get_auth_service),
):
    """Registers a new user account with layered genuine email check and roster verification."""
    success, message, extra = await auth_service.register(req)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "REGISTRATION_FAILED", "message": message},
        )
    return GenericMessageResponse(message=message, details=extra)


@router.post("/verify-email", response_model=GenericMessageResponse)
async def verify_email(
    req: VerifyEmailRequest,
    auth_service: AuthService = Depends(get_auth_service),
):
    """Verifies email address using link token or 6-digit code."""
    success, message = await auth_service.verify_email(req)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "VERIFICATION_FAILED", "message": message},
        )
    return GenericMessageResponse(message=message)


@router.post("/login", response_model=TokenResponse)
async def login(
    req: LoginRequest,
    request: Request,
    response: Response,
    auth_service: AuthService = Depends(get_auth_service),
):
    """
    Authenticates user, sets httpOnly refresh token cookie,
    and returns access token in response body.
    """
    client_ip = request.client.host if request.client else "127.0.0.1"
    user_agent = request.headers.get("user-agent")

    success, message, data = await auth_service.login(
        req, client_ip=client_ip, user_agent=user_agent
    )
    if not success or not data:
        # Determine appropriate status code
        status_code = status.HTTP_401_UNAUTHORIZED
        if (
            "locked" in message.lower()
            or "approval" in message.lower()
            or "verify" in message.lower()
        ):
            status_code = status.HTTP_403_FORBIDDEN
        raise HTTPException(
            status_code=status_code,
            detail={"code": "LOGIN_FAILED", "message": message},
        )

    # Set httpOnly, Secure, SameSite=Strict cookie for refresh token
    refresh_token = data["refresh_token"]
    is_secure = settings.APP_ENV != "development" and settings.APP_ENV != "testing"
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=is_secure,
        samesite="strict",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        path="/auth",
    )

    return TokenResponse(
        access_token=data["access_token"],
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserProfileResponse(**data["user"]),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_session(
    request: Request,
    response: Response,
    refresh_token: str | None = Cookie(default=None),
    auth_service: AuthService = Depends(get_auth_service),
):
    """Rotates refresh token and returns a new access token."""
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "MISSING_REFRESH_TOKEN",
                "message": "No refresh token provided in cookies.",
            },
        )

    client_ip = request.client.host if request.client else "127.0.0.1"
    user_agent = request.headers.get("user-agent")

    success, message, data = await auth_service.refresh_session(
        refresh_token, client_ip=client_ip, user_agent=user_agent
    )
    if not success or not data:
        response.delete_cookie(key="refresh_token", path="/auth")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "REFRESH_FAILED", "message": message},
        )

    # Set rotated cookie
    is_secure = settings.APP_ENV != "development" and settings.APP_ENV != "testing"
    response.set_cookie(
        key="refresh_token",
        value=data["refresh_token"],
        httponly=True,
        secure=is_secure,
        samesite="strict",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        path="/auth",
    )

    # Fetch user profile to construct response
    from bson import ObjectId

    from backend.app.core.security import decode_access_token
    from backend.app.db.mongo import get_database

    payload = decode_access_token(data["access_token"])
    db = get_database()
    user = await db.users.find_one({"_id": ObjectId(payload["sub"])})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "USER_NOT_FOUND", "message": "User not found."},
        )
    user_profile = {
        "id": str(user["_id"]),
        "name": user["name"],
        "email": user["email"],
        "phone_e164": user.get("phone_e164"),
        "role": user["role"],
        "status": user["status"],
        "email_verified": user.get("email_verified", False),
        "phone_verified": user.get("phone_verified", False),
    }

    return TokenResponse(
        access_token=data["access_token"],
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserProfileResponse(**user_profile),
    )


@router.post("/logout", response_model=GenericMessageResponse)
async def logout(
    response: Response,
    refresh_token: str | None = Cookie(default=None),
):
    """Logs out user by clearing the refresh token cookie and revoking session."""
    if refresh_token:
        from datetime import datetime

        from backend.app.core.security import hash_token
        from backend.app.db.mongo import get_database

        db = get_database()
        await db.refresh_tokens.update_one(
            {"token_hash": hash_token(refresh_token)},
            {"$set": {"revoked_at": datetime.now(UTC)}},
        )

    response.delete_cookie(key="refresh_token", path="/auth")
    return GenericMessageResponse(message="Successfully logged out.")


@router.post("/forgot-password", response_model=GenericMessageResponse)
async def forgot_password(
    req: ForgotPasswordRequest,
    request: Request,
    auth_service: AuthService = Depends(get_auth_service),
):
    """
    Requests password reset instructions. Always returns generic message
    to avoid account enumeration.
    """
    client_ip = request.client.host if request.client else "127.0.0.1"
    _, message = await auth_service.forgot_password(req, client_ip=client_ip)
    return GenericMessageResponse(message=message)


@router.post("/reset-password", response_model=GenericMessageResponse)
async def reset_password(
    req: ResetPasswordRequest,
    auth_service: AuthService = Depends(get_auth_service),
):
    """Resets password using single-use token or OTP."""
    success, message = await auth_service.reset_password(req)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "RESET_FAILED", "message": message},
        )
    return GenericMessageResponse(message=message)


@router.get("/me", response_model=UserProfileResponse)
async def get_me(current_user: dict = Depends(get_current_user)):
    """Returns the authenticated user's profile."""
    return UserProfileResponse(
        id=str(current_user["_id"]),
        name=current_user["name"],
        email=current_user["email"],
        phone_e164=current_user.get("phone_e164"),
        role=current_user["role"],
        status=current_user["status"],
        email_verified=current_user.get("email_verified", False),
        phone_verified=current_user.get("phone_verified", False),
    )


@router.get("/pending-approvals")
async def list_pending_approvals(
    current_user: dict = Depends(require_role(UserRole.ADMIN)),
):
    """Lists faculty and HOD accounts awaiting administrator approval."""
    from backend.app.db.mongo import get_database

    db = get_database()
    cursor = db.users.find({"status": UserStatus.PENDING_APPROVAL.value}).sort("created_at", -1)
    users = await cursor.to_list(100)
    return [
        {
            "id": str(u["_id"]),
            "name": u["name"],
            "email": u["email"],
            "role": u["role"],
            "department": u.get("department"),
            "email_verified": u.get("email_verified", False),
            "created_at": u.get("created_at"),
        }
        for u in users
    ]


@router.patch("/approve/{user_id}", response_model=GenericMessageResponse)
async def approve_user(
    user_id: str,
    request: Request,
    current_user: dict = Depends(require_role(UserRole.ADMIN)),
):
    """Approves a pending Teacher or HOD account, activating it for login."""
    if not ObjectId.is_valid(user_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "USER_NOT_FOUND", "message": "User not found."},
        )

    from datetime import datetime
    from backend.app.db.mongo import get_database
    from backend.app.services.audit_service import audit_service

    db = get_database()
    u_oid = ObjectId(user_id)
    user = await db.users.find_one({"_id": u_oid})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "USER_NOT_FOUND", "message": "User not found."},
        )

    await db.users.update_one(
        {"_id": u_oid},
        {"$set": {"status": UserStatus.ACTIVE.value, "updated_at": datetime.now(UTC)}},
    )

    client_ip = request.client.host if request.client else None
    await audit_service.log_action(
        action="user_account_approved",
        target_type="user",
        target_id=user_id,
        actor_id=current_user["_id"],
        after={"role": user.get("role"), "email": user.get("email"), "status": UserStatus.ACTIVE.value},
        ip=client_ip,
    )

    return GenericMessageResponse(message=f"User {user['email']} successfully approved and activated.")

