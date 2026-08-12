from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from project.backend.app.db.models.user import User


@dataclass(slots=True)
class UsersRepository:
    session: AsyncSession

    async def upsert_oauth_user(
        self,
        *,
        oauth_user_id: str,
        email: str,
        name: str | None,
        profile_image: str | None,
    ) -> User:
        statement = (
            insert(User)
            .values(
                oauth_user_id=oauth_user_id,
                email=email,
                name=name,
                profile_image=profile_image,
            )
            .on_conflict_do_update(
                index_elements=[User.oauth_user_id],
                set_={
                    "email": email,
                    "name": name,
                    "profile_image": profile_image,
                },
            )
            .returning(User)
        )
        return (await self.session.scalars(statement)).one()

    async def get_by_id(self, user_id: int) -> User | None:
        return await self.session.get(User, user_id)

    async def get_by_oauth_user_id(self, oauth_user_id: str) -> User | None:
        return await self.session.scalar(
            select(User).where(User.oauth_user_id == oauth_user_id)
        )
