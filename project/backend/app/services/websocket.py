from fastapi import WebSocket


class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, list[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, user_id: str):
        await websocket.accept()
        self.active_connections.setdefault(user_id, []).append(websocket)

    def disconnect(self, websocket: WebSocket, user_id: str):
        connections = self.active_connections.get(user_id)
        if not connections:
            return

        if websocket in connections:
            connections.remove(websocket)

        if not connections:
            del self.active_connections[user_id]

    async def broadcast_to_user(self, user_id: str, message: str):
        connections = self.active_connections.get(user_id, [])
        dead_sockets = []

        for websocket in connections:
            try:
                await websocket.send_text(message)
            except Exception:
                dead_sockets.append(websocket)

        for websocket in dead_sockets:
            self.disconnect(websocket, user_id)


def get_websocket_manager(app) -> ConnectionManager:
    manager = getattr(app.state, "websocket_manager", None)
    if manager is None:
        manager = ConnectionManager()
        app.state.websocket_manager = manager
    return manager
