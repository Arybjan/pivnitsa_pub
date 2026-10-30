import re
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field

_PHONE_RE = re.compile(r"^\+[1-9]\d{9,14}$")
_PHONE_CHARS_RE = re.compile(r"^\+?[\d\s\-().]+$")


def normalize_phone(value: str) -> str:
    """Приводит номер к E.164: '0705 07-20-03', '705072003', '996705072003' -> '+996705072003'."""
    value = value.strip()
    if not _PHONE_CHARS_RE.fullmatch(value):
        raise ValueError("Invalid phone number, expected format +996XXXXXXXXX")
    has_plus = value.startswith("+")
    digits = re.sub(r"\D", "", value)
    if digits.startswith("0") and len(digits) == 10:
        digits = "996" + digits[1:]  # местный формат 0XXX XXX XXX (в том числе с лишним «+»)
    elif not has_plus and digits.startswith("00"):
        digits = digits[2:]  # международный префикс 00
    elif not has_plus and len(digits) == 9:
        digits = "996" + digits  # номер без кода страны и без 0
    phone = "+" + digits
    if not _PHONE_RE.fullmatch(phone):
        raise ValueError("Invalid phone number, expected format +996XXXXXXXXX")
    return phone


def _check_password(value: str) -> str:
    if len(value.encode()) > 72:
        raise ValueError("Password is too long (max 72 bytes)")
    if not re.search(r"[A-Za-zА-Яа-яЁё]", value) or not re.search(r"\d", value):
        raise ValueError("Password must contain at least one letter and one digit")
    return value


Phone = Annotated[str, Field(min_length=9, max_length=25, examples=["+996555123456"]), AfterValidator(normalize_phone)]
Password = Annotated[str, Field(min_length=8, max_length=72), AfterValidator(_check_password)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
