from dataclasses import dataclass
from typing import Any

from project.backend.app.repositories.saved_posts import SavedPostsRepository


@dataclass(slots=True)
class Repositories:
    saved_posts: SavedPostsRepository


def get_repositories(conn: Any) -> Repositories:
    return Repositories(
        saved_posts=SavedPostsRepository(conn),
    )
