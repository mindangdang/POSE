from dataclasses import dataclass
from typing import Any

from project.backend.app.repositories.saved_posts import SavedPostsRepository
from project.backend.app.repositories.product_db import ProductDBRepository

@dataclass(slots=True)
class Repositories:
    saved_posts: SavedPostsRepository
    product_db: ProductDBRepository
    
def get_repositories(conn: Any) -> Repositories:
    return Repositories(
        saved_posts=SavedPostsRepository(conn),
        product_db=ProductDBRepository(conn),
    )
