from dataclasses import dataclass
from typing import Any

from project.backend.app.repositories.saved_posts import SavedPostsRepository
from project.backend.app.repositories.product_db import ProductDBRepository
from project.backend.app.repositories.event_logs import EventLogsRepository

@dataclass(slots=True)
class Repositories:
    saved_posts: SavedPostsRepository
    product_db: ProductDBRepository
    event_logs: EventLogsRepository
    
def get_repositories(conn: Any) -> Repositories:
    return Repositories(
        saved_posts=SavedPostsRepository(conn),
        product_db=ProductDBRepository(conn),
        event_logs=EventLogsRepository(conn),
    )
