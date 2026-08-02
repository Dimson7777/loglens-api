from __future__ import annotations

import asyncio

from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.config import get_settings
from app.core.security import hash_password
from app.database.session import get_engine
from app.models.user import UserRole
from app.repositories.user import UserRepository


async def seed_admin_user() -> None:
    settings = get_settings()

    if not settings.admin_bootstrap_email or not settings.admin_bootstrap_password:
        raise SystemExit(
            "ADMIN_BOOTSTRAP_EMAIL and ADMIN_BOOTSTRAP_PASSWORD "
            "must be set before seeding admin user."
        )

    session_factory = async_sessionmaker(bind=get_engine(), expire_on_commit=False)

    async with session_factory() as session:
        user_repo = UserRepository(session)
        async with session.begin():
            existing = await user_repo.get_by_email(settings.admin_bootstrap_email.lower())
            if existing is not None:
                print("Admin user already exists; skipping seed.")
                return

            await user_repo.create_user(
                email=settings.admin_bootstrap_email.lower(),
                password_hash=hash_password(settings.admin_bootstrap_password),
                role=UserRole.ADMIN,
                is_active=True,
            )

    print("Admin user seeded successfully.")


def main() -> None:
    asyncio.run(seed_admin_user())


if __name__ == "__main__":
    main()
