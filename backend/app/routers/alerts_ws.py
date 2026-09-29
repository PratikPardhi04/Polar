from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from app.auth.security import decode_token
from app.services import broadcaster

router = APIRouter(tags=["alerts"])


@router.websocket("/api/v1/ws/alerts")
async def alerts(ws: WebSocket, token: str = Query(default="")):
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            await ws.close(code=4401)
            return
    except ValueError:
        await ws.close(code=4401)
        return
    await ws.accept()
    await broadcaster.register(ws)
    try:
        await ws.send_json({"kind": "HELLO", "message": "subscribed to POLARIS alerts"})
        while True:
            await ws.receive_text()  # heartbeat; server pushes unprompted
    except WebSocketDisconnect:
        await broadcaster.unregister(ws)
