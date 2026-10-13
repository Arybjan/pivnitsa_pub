from fastapi import APIRouter, status

from app.api.deps import Auth, CurrentUser
from app.core.config import settings
from app.schemas.auth import (
    AuthResponse,
    LoginRequest,
    OtpSendRequest,
    OtpSendResponse,
    OtpVerifyRequest,
    OtpVerifyResponse,
    PasswordResetRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
)

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/otp/send", response_model=OtpSendResponse)
async def send_otp(data: OtpSendRequest, auth: Auth):
    """Шаг 1: отправить SMS-код (purpose: register | login | reset_password)."""
    issued = await auth.send_otp(data.phone, data.purpose)
    return OtpSendResponse(
        message="If the number is valid, a code has been sent",
        expires_in=issued.expires_in,
        resend_after=issued.resend_after,
        debug_code=issued.code if settings.otp_exposed else None,
    )


@router.post("/otp/verify", response_model=OtpVerifyResponse)
async def verify_otp(data: OtpVerifyRequest, auth: Auth):
    """Шаг 2: проверить код и получить одноразовый verification_token."""
    token, expires_in = await auth.otp.verify(data.phone, data.purpose, data.code)
    return OtpVerifyResponse(verification_token=token, expires_in=expires_in)


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register(data: RegisterRequest, auth: Auth):
    """Шаг 3: регистрация по verification_token (purpose=register) и паролю."""
    return await auth.register(data)


@router.post("/login", response_model=AuthResponse)
async def login(data: LoginRequest, auth: Auth):
    """Вход по phone + password или по verification_token (purpose=login)."""
    return await auth.login(data)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(data: RefreshRequest, auth: Auth):
    """Обмен refresh-токена на новую пару. Старый refresh-токен становится недействительным."""
    return await auth.refresh(data.refresh_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(data: RefreshRequest, auth: Auth):
    """Выход на текущем устройстве (US-06)."""
    await auth.logout(data.refresh_token)


@router.post("/logout-all", status_code=status.HTTP_204_NO_CONTENT)
async def logout_all(user: CurrentUser, auth: Auth):
    """Выход на всех устройствах."""
    await auth.sessions.revoke_all(user.id)


@router.post("/password/reset", status_code=status.HTTP_204_NO_CONTENT)
async def reset_password(data: PasswordResetRequest, auth: Auth):
    """Сброс пароля по verification_token (purpose=reset_password). Завершает все сессии."""
    await auth.reset_password(data)
