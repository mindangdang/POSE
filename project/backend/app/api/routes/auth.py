from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, HTTPException, Depends
from google.oauth2 import id_token
from google.auth.transport import requests
import jwt
from project.backend.app.schemas.auth_response import *
from psycopg.rows import dict_row
from project.backend.app.api.dependencies import get_current_user
from project.backend.app.manage.database import get_db_connection
from project.backend.app.manage.settings import get_settings

router = APIRouter()

settings = get_settings()
GOOGLE_CLIENT_ID = settings.google_client_id
JWT_SECRET = settings.jwt_secret

@router.post("/auth/google", response_model=AuthTokenResponse)
async def google_auth(request: GoogleAuthRequest, conn=Depends(get_db_connection)):
    try:
        # Verify GOOGLE_CLIENT_ID is configured
        if not GOOGLE_CLIENT_ID:
            raise HTTPException(status_code=500, detail="GOOGLE_CLIENT_ID not configured")
        if not JWT_SECRET:
            raise HTTPException(status_code=500, detail="JWT_SECRET not configured")
        
        # 1. 프론트엔드에서 보낸 구글 토큰 검증
        idinfo = id_token.verify_oauth2_token(
            request.access_token, 
            requests.Request(), 
            GOOGLE_CLIENT_ID
        )
        
        email = idinfo.get("email")
        name = idinfo.get("name")
        picture = idinfo.get("picture")
        google_id = idinfo.get("sub")

        # 2. Neon DB에서 유저 조회 및 가입 처리
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute("SELECT * FROM users WHERE email = %s", (email,))
            user = await cur.fetchone()
            if not user:
                await cur.execute(
                    """
                    INSERT INTO users (user_id, email, name, profile_image)
                    VALUES (%s, %s, %s, %s) RETURNING *
                    """,
                    (google_id, email, name, picture)
                )
                user = await cur.fetchone()
            await conn.commit()

        # 3. 자체 JWT 발급
        expiration = datetime.now(timezone.utc) + timedelta(days=7)
        internal_token = jwt.encode(
            {"sub": google_id, "name": name, "exp": expiration},
            JWT_SECRET,
            algorithm="HS256"
        )

        # 프론트엔드에서 사용할 AppUser 형태의 데이터와 access_token 반환
        user_data = {"user_id": google_id, "email": email, "name": name, "profile_image": picture}
        return {"access_token": internal_token, "token_type": "bearer", "user": user_data}
        
    except ValueError as e:
        raise HTTPException(status_code=401, detail=f"Invalid Google token: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Token verification failed: {str(e)}")

@router.post("/auth/guest", response_model=AuthTokenResponse)
async def guest_auth(conn=Depends(get_db_connection)):
    if not JWT_SECRET:
        raise HTTPException(status_code=500, detail="JWT_SECRET not configured")

    guest_id = "1"
    guest_email = "guest@pose.local"
    guest_name = "Guest"
    guest_profile_image = None

    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute("SELECT * FROM users WHERE user_id = %s", (guest_id,))
        user = await cur.fetchone()
        if not user:
            await cur.execute(
                "INSERT INTO users (user_id, email, name, profile_image) VALUES (%s, %s, %s, %s) RETURNING *",
                (guest_id, guest_email, guest_name, guest_profile_image)
            )
            user = await cur.fetchone()
        await conn.commit()

    expiration = datetime.now(timezone.utc) + timedelta(days=7)
    internal_token = jwt.encode(
        {"sub": guest_id, "name": guest_name, "exp": expiration},
        JWT_SECRET,
        algorithm="HS256"
    )

    user_data = {
        "user_id": user["user_id"],
        "email": user["email"],
        "name": user["name"],
        "profile_image": user["profile_image"],
        "username": user["name"],
    }
    return {"access_token": internal_token, "token_type": "bearer", "user": user_data}

@router.get("/auth/me", response_model=CurrentUserResponse)
async def get_current_user_info(current_user: dict = Depends(get_current_user), conn=Depends(get_db_connection)):
    """현재 로그인한 사용자의 정보를 반환합니다."""
    try:
        user_id: str = current_user.get("sub")
        
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                "SELECT user_id, email, name, profile_image FROM users WHERE user_id = %s",
                (user_id,)
            )
            user = await cur.fetchone()
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # 프론트엔드가 사용하는 AppUser 형태의 데이터 반환
        user_data = {
            "user_id": user["user_id"],
            "email": user["email"],
            "name": user["name"],
            "profile_image": user["profile_image"],
            "username": user["name"]  # username도 추가 (프론트엔드에서 사용)
        }
        return {"user": user_data}
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error fetching user info: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
