from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from google.auth.transport import requests
from google.oauth2 import id_token
import jwt
from psycopg.rows import dict_row

from project.backend.app.api.dependencies import get_current_user
from project.backend.app.manage.database import get_db_connection
from project.backend.app.manage.settings import get_settings
from project.backend.app.schemas.auth_response import (
    AuthTokenResponse,
    CurrentUserResponse,
    GoogleAuthRequest,
)


router = APIRouter()
settings = get_settings()
GOOGLE_CLIENT_ID = settings.google_client_id
JWT_SECRET = settings.jwt_secret


def _create_access_token(*, user_id: int, name: str | None) -> str:
    if not JWT_SECRET:
        raise HTTPException(status_code=500, detail="JWT_SECRET not configured")
    expiration = datetime.now(timezone.utc) + timedelta(days=7)
    return jwt.encode(
        {"sub": str(user_id), "name": name, "exp": expiration},
        JWT_SECRET,
        algorithm="HS256",
    )


def _user_response(user: dict) -> dict:
    return {
        "id": int(user["id"]),
        "email": user["email"],
        "name": user["name"],
        "profile_image": user["profile_image"],
        "username": user["name"],
    }


@router.post("/auth/google", response_model=AuthTokenResponse)
async def google_auth(request: GoogleAuthRequest, conn=Depends(get_db_connection)):
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=500, detail="GOOGLE_CLIENT_ID not configured")

    try:
        idinfo = id_token.verify_oauth2_token(
            request.access_token,
            requests.Request(),
            GOOGLE_CLIENT_ID,
        )
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=f"Invalid Google token: {exc}") from exc

    oauth_user_id = idinfo.get("sub")
    email = idinfo.get("email")
    if not oauth_user_id or not email:
        raise HTTPException(status_code=401, detail="Google token is missing user identity")

    name = idinfo.get("name")
    picture = idinfo.get("picture")
    async with conn.cursor(row_factory=dict_row) as cursor:
        await cursor.execute(
            """
            INSERT INTO users (user_id, email, name, profile_image)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (user_id) DO UPDATE SET
                email = EXCLUDED.email,
                name = EXCLUDED.name,
                profile_image = EXCLUDED.profile_image
            RETURNING id, user_id, email, name, profile_image
            """,
            (oauth_user_id, email, name, picture),
        )
        user = await cursor.fetchone()
        await conn.commit()

    token = _create_access_token(user_id=int(user["id"]), name=user["name"])
    return {"access_token": token, "token_type": "bearer", "user": _user_response(user)}


@router.post("/auth/guest", response_model=AuthTokenResponse)
async def guest_auth(conn=Depends(get_db_connection)):
    async with conn.cursor(row_factory=dict_row) as cursor:
        await cursor.execute(
            """
            INSERT INTO users (user_id, email, name, profile_image)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (user_id) DO UPDATE SET name = EXCLUDED.name
            RETURNING id, user_id, email, name, profile_image
            """,
            ("guest", "guest@pose.local", "Guest", None),
        )
        user = await cursor.fetchone()
        await conn.commit()

    token = _create_access_token(user_id=int(user["id"]), name=user["name"])
    return {"access_token": token, "token_type": "bearer", "user": _user_response(user)}


@router.get("/auth/me", response_model=CurrentUserResponse)
async def get_current_user_info(
    current_user: dict = Depends(get_current_user),
    conn=Depends(get_db_connection),
):
    internal_user_id = int(current_user["sub"])
    async with conn.cursor(row_factory=dict_row) as cursor:
        await cursor.execute(
            """
            SELECT id, user_id, email, name, profile_image
            FROM users
            WHERE id = %s
            """,
            (internal_user_id,),
        )
        user = await cursor.fetchone()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {"user": _user_response(user)}
