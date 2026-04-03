from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from project.backend.app.core.settings import FRONTEND_DIST_DIR


router = APIRouter()


@router.get("/api/debug/dist")
def debug_dist():
    exists = FRONTEND_DIST_DIR.exists()
    contents = [path.name for path in FRONTEND_DIST_DIR.iterdir()] if exists else []
    return {"exists": exists, "contents": contents}


@router.get("/{full_path:path}")
async def serve_spa(full_path: str):
    if full_path.startswith("api/"):
        raise HTTPException(status_code=404, detail=f"API route not found: {full_path}")

    if not full_path or full_path == "/":
        index_file = FRONTEND_DIST_DIR / "index.html"
        if index_file.exists():
            return FileResponse(index_file)

    file_path = FRONTEND_DIST_DIR / full_path
    if file_path.is_file():
        return FileResponse(file_path)

    index_file = FRONTEND_DIST_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)

    return {"error": "Frontend not built or route not found"}
