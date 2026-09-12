from pydantic import BaseModel, Field


class RequestCodeRequest(BaseModel):
    phone: str = Field(
        min_length=10,
        max_length=20,
    )


class RequestCodeResponse(BaseModel):
    message: str


class VerifyCodeRequest(BaseModel):
    phone: str = Field(
        min_length=10,
        max_length=20,
    )

    code: str = Field(
        min_length=6,
        max_length=6,
    )


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    