import os

from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.middleware.cors import CORSMiddleware
from project.backend.app import create_app


app = create_app()

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        # 구글 인증 팝업과 안전하게 통신하기 위해 COOP, COEP 보안 헤더를 조정합니다.
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin-allow-popups"
        response.headers["Cross-Origin-Embedder-Policy"] = "unsafe-none"
        return response

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(SecurityHeadersMiddleware)

if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("BACKEND_PORT", os.environ.get("PORT", 8000)))
    uvicorn.run("project.backend.main:app", host="0.0.0.0", port=port, reload=True)
