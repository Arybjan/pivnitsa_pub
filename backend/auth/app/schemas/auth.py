from enum import StrEnum
from typing import Literal

from pydantic import EmailStr, Field, model_validator

from app.schemas.base import Password, Phone, StrictModel
from app.schemas.user import UserResponse


class OtpPurpose(StrEnum):
    REGISTER = "register"
    LOGIN = "login"
    RESET_PASSWORD = "reset_password"


class OtpSendRequest(StrictModel):
    phone: Phone
    purpose: OtpPurpose = OtpPurpose.REGISTER


class OtpSendResponse(StrictModel):
    message: str
    expires_in: int
    resend_after: int
    # Заполняется только при OTP_EXPOSE_IN_RESPONSE=true вне production
    debug_code: str | None = None


class OtpVerifyRequest(StrictModel):
    phone: Phone
    code: str = Field(pattern=r"^\d{4,8}$")
    purpose: OtpPurpose = OtpPurpose.REGISTER


class OtpVerifyResponse(StrictModel):
    verification_token: str
    expires_in: int


class RegisterRequest(StrictModel):
    verification_token: str
    password: Password
    first_name: str | None = Field(default=None, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)
    email: EmailStr | None = None


class LoginRequest(StrictModel):
    """Вход по паролю (phone + password) или по SMS-коду (verification_token с purpose=login)."""

    phone: Phone | None = None
    password: str | None = Field(default=None, max_length=72)
    verification_token: str | None = None

    @model_validator(mode="after")
    def _one_method(self):
        by_password = self.phone is not None and self.password is not None
        by_otp = self.verification_token is not None
        if by_password == by_otp:
            raise ValueError("Provide either phone + password or verification_token")
        return self


class RefreshRequest(StrictModel):
    refresh_token: str


class PasswordResetRequest(StrictModel):
    verification_token: str
    new_password: Password


class TokenResponse(StrictModel):
    access_token: str
    refresh_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int


class AuthResponse(TokenResponse):
    user: UserResponse
