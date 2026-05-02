import os
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from google.oauth2 import id_token
from google.auth.transport import requests
import jwt
from fastapi.security import OAuth2PasswordBearer
from psycopg.rows import dict_row
from project.backend.app.core.database import get_db_connection

router = APIRouter()

GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID")
JWT_SECRET = os.environ.get("JWT_SECRET")

# FastAPI의 OAuth2 표준에 따라 Authorization 헤더에서 Bearer 토큰을 추출합니다.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/google")

class GoogleAuthRequest(BaseModel):
    token: str

@router.post("/auth/google")
async def google_auth(request: GoogleAuthRequest, conn=Depends(get_db_connection)):
    try:
        # 1. 프론트엔드에서 보낸 구글 토큰 검증
        idinfo = id_token.verify_oauth2_token(
            request.token, 
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
                    INSERT INTO users (id, email, name, profile_image)
                    VALUES (%s, %s, %s, %s) RETURNING *
                    """,
                    (google_id, email, name, picture)
                )
                user = await cur.fetchone()
            await conn.commit()

        # 3. 자체 JWT 발급
        expiration = datetime.utcnow() + timedelta(days=7)
        internal_token = jwt.encode(
            {"sub": google_id, "name": name, "exp": expiration},
            JWT_SECRET,
            algorithm="HS256"
        )

        # 프론트엔드에서 사용할 AppUser 형태의 데이터와 access_token 반환
        user_data = {"id": google_id, "email": email, "name": name, "profile_image": picture}
        return {"access_token": internal_token, "token_type": "bearer", "user": user_data}
        
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid Google authentication token")

# 팀 내 백엔드 컨벤션: 인증이 필요한 API 호출 시 이 Dependency를 사용합니다.
async def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid authentication credentials")
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid authentication credentials")