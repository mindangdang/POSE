from pydantic import BaseModel

class AuthUserResponse(BaseModel):
    id: str
    email: str | None = None
    name: str | None = None
    profile_image: str | None = None
    username: str | None = None


class AuthTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: AuthUserResponse


class CurrentUserResponse(BaseModel):
    user: AuthUserResponse

class GoogleAuthRequest(BaseModel):
    access_token: str