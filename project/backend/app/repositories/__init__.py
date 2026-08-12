from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from project.backend.app.repositories.event_logs import EventLogsRepository
from project.backend.app.repositories.product_db import ProductDBRepository
from project.backend.app.repositories.saved_posts import SavedPostsRepository
from project.backend.app.repositories.users import UsersRepository


@dataclass(slots=True)
class Repositories:
    users: UsersRepository
    saved_posts: SavedPostsRepository
    product_db: ProductDBRepository
    event_logs: EventLogsRepository


def get_repositories(session: AsyncSession) -> Repositories:
    return Repositories(
        users=UsersRepository(session),
        saved_posts=SavedPostsRepository(session),
        product_db=ProductDBRepository(session),
        event_logs=EventLogsRepository(session),
    )
