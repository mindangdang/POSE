from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    Request,
    WebSocket,
    WebSocketDisconnect,
    UploadFile,
    File,
    Form,
)
from fastapi.responses import FileResponse
from typing import Optional

from project.backend.app.manage.database import get_repos
from project.backend.app.repositories import Repositories
from project.backend.app.schemas.requests import ManualItemCreate, SearchRequest, UrlAnalyzeRequest
from project.backend.app.api.dependencies import get_current_user
from project.backend.app.services.content import (
    delete_item_for_user,
    enqueue_pse_search,
    list_items_for_user,
    resolve_image_path,
    save_manual_item_for_user,
    search_with_lens,
    start_url_extraction,
)
from project.backend.app.services.websocket import get_websocket_manager

router = APIRouter()

@router.post("/crawl_product")
async def extract_and_save_url(
    payload: UrlAnalyzeRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    repos: Repositories = Depends(get_repos),
    current_user: dict = Depends(get_current_user)
):
    post_url = payload.url
    user_id = str(current_user.get("sub"))

    request.app.state.websocket_manager = websocket_manager_instance

    try:
        new_item_id = await repos.saved_posts.create_processing_item(user_id, post_url)
        print("임시 아이템 저장 성공")
    except Exception as exc:
        await repos.saved_posts.conn.rollback()
        raise HTTPException(status_code=500, detail=f"임시 데이터 저장 실패: {exc}") from exc

    background_tasks.add_task(
        background_crawl_and_save,
        request.app,
        new_item_id,
        user_id,
        post_url,
    )

    return {
        "success": True,
        "message": "데이터 추출 및 AI 분석이 시작되었습니다.",
        "item_id": new_item_id,
        "data": [
            {   
                "item_id": new_item_id,
                "title": "PROCESSING",
                "price": None,
                "brand": None,
                "category": "PROCESSING",
                "is_available": None,
                "image_url": "",
                "image_vector": None,
                "shop": None,
                "source_url": post_url,
            }
        ],
    }

######################################################################################

@router.post("/pse")
async def run_serpapi_search(
    payload: SearchRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user)
):
    return enqueue_pse_search(
        payload=payload,
        app=request.app,
        background_tasks=background_tasks,
        user_id=str(current_user.get("sub")),
    )

@router.post("/lens")
async def run_serpapi_lens_search(
    file: Optional[UploadFile] = File(None),
    query: Optional[str] = Form(None)
):
    return await search_with_lens(file=file, query=query)

@router.post("/items/manual") 
async def save_manual_item(
    payload: ManualItemCreate,
    repos: Repositories = Depends(get_repos),
    current_user: dict = Depends(get_current_user)
):
    return await save_manual_item_for_user(
        payload=payload,
        user_id=str(current_user.get("sub")),
        repos=repos,
    )
    
######################################################################################

@router.get("/items")
async def get_items(
    current_user: dict = Depends(get_current_user), 
    repos: Repositories = Depends(get_repos)
):
    return await list_items_for_user(user_id=str(current_user.get("sub")), repos=repos)

@router.delete("/items/{item_id}")
async def delete_item(
    item_id: int, 
    current_user: dict = Depends(get_current_user), 
    repos: Repositories = Depends(get_repos)
):
    return await delete_item_for_user(item_id=item_id, user_id=str(current_user.get("sub")), repos=repos)

@router.get("/images/{filename}")
async def serve_image(filename: str):
    return FileResponse(path=resolve_image_path(filename))

@router.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    manager = get_websocket_manager(websocket.app)
    await manager.connect(websocket, user_id)
    try:
        while True:
            await websocket.receive_text()  # Keep connection alive
    except WebSocketDisconnect:
        manager.disconnect(websocket, user_id)
