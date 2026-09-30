import asyncio
from typing import List, Dict, Any
from fastapi import WebSocket


class ConnectionManager:
    """
    Manages active WebSocket client connections and broadcasts real-time
    spatial tree mutations, audit log events, and lock lease expirations.
    """

    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: Dict[str, Any]):
        """Broadcasts JSON payload to all active clients."""
        to_remove = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                to_remove.append(connection)

        for conn in to_remove:
            self.disconnect(conn)


ws_manager = ConnectionManager()
