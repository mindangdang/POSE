import jwt
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer

from project.backend.app.manage.settings import get_settings

settings = get_settings()
JWT_SECRET = settings.jwt_secret

# FastAPI의 OAuth2 표준에 따라 Authorization 헤더에서 Bearer 토큰을 추출합니다.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/google")


# 팀 내 백엔드 컨벤션: 인증이 필요한 API 호출 시 이 Dependency를 사용합니다.
async def get_current_user(token: str = Depends(oauth2_scheme)):
    if not JWT_SECRET:
        raise HTTPException(status_code=500, detail="JWT_SECRET not configured")

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
