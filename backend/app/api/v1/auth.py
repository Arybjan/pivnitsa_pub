from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.schemas.auth import (
    RequestCodeRequest,
    RequestCodeResponse,
    TokenResponse,
    VerifyCodeRequest,
)
from app.services.auth import AuthService


router = APIRouter(
    prefix="/auth",
    tags=["Auth"],
)


@router.post(
    "/request-code",
    response_model=RequestCodeResponse,
)
async def request_code(
    data: RequestCodeRequest,
    db: AsyncSession = Depends(get_db),
):
    service = AuthService(db)

    await service.request_code(
        phone=data.phone,
    )

    return RequestCodeResponse(
        message="Verification code sent",
    )


@router.post(
    "/verify-code",
    response_model=TokenResponse,
)
async def verify_code(
    data: VerifyCodeRequest,
    db: AsyncSession = Depends(get_db),
):
    service = AuthService(db)

    return await service.verify_code(
        phone=data.phone,
        code=data.code,
    )