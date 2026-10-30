from typing import Annotated
from pydantic import BaseModel, Field, model_validator
from fastapi import Path

MAX_BIGINT = 9_223_372_036_854_775_807

# Типы для безопасных BigInt (валидируют 1 <= ID <= MAX_BIGINT)
BigIntId = Annotated[int, Field(gt=0, le=MAX_BIGINT)]
BigIntPath = Annotated[int, Path(gt=0, le=MAX_BIGINT)]


class SafeBaseModel(BaseModel):
    """Базовый класс с быстрой защитой от Null-byte инъекций"""
    @model_validator(mode="before")
    @classmethod
    def _validate_no_null_bytes(cls, data: dict):
        if isinstance(data, dict):
            for v in data.values():
                if isinstance(v, str) and "\x00" in v:
                    raise ValueError("Null bytes (\\x00) are not allowed")
        return data
