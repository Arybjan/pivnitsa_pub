"""Служебные команды.

    python -m app.cli set-role +996555123456 owner
"""
import argparse
import asyncio

from sqlalchemy import select

from app.core.database import async_session_maker, engine
from app.core.redis import redis_client
from app.core.roles import Role
from app.models import User
from app.schemas.base import normalize_phone
from app.services.session_store import SessionStore


async def set_role(phone: str, role: Role) -> None:
    async with async_session_maker() as db:
        user = await db.scalar(select(User).where(User.phone == normalize_phone(phone)))
        if user is None:
            raise SystemExit(f"User {phone} not found — register first")
        user.role = role
        await db.commit()
        await SessionStore(redis_client).revoke_all(user.id)
        print(f"User #{user.id} ({user.phone}) is now {role}")
    await redis_client.aclose()
    await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    cmd = sub.add_parser("set-role", help="назначить роль пользователю (например, первого владельца)")
    cmd.add_argument("phone")
    cmd.add_argument("role", choices=[r.value for r in Role])
    args = parser.parse_args()
    asyncio.run(set_role(args.phone, Role(args.role)))


if __name__ == "__main__":
    main()
