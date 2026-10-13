from enum import StrEnum


class Role(StrEnum):
    # Значения в нижнем регистре — Booking и Payment сравнивают role с ("admin", "owner")
    USER = "user"
    ADMIN = "admin"
    OWNER = "owner"


ADMIN_ROLES = frozenset({Role.ADMIN, Role.OWNER})
