from dataclasses import dataclass
from typing import Any

from project.backend.app.repositories.saved_posts import SavedPostsRepository
from project.backend.app.repositories.taste_profile import TasteProfileRepository


@dataclass(slots=True)
class Repositories:
    saved_posts: SavedPostsRepository
    taste_profile: TasteProfileRepository


def get_repositories(conn: Any) -> Repositories:
    return Repositories(
        saved_posts=SavedPostsRepository(conn),
        taste_profile=TasteProfileRepository(conn),
    )
