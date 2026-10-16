"""WebSocket endpoint for live browser updates."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ...logging_config import get_logger

router = APIRouter(tags=["transport"])
logger = get_logger("phantom.api.ws")


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    hub = websocket.app.state.ctx.hub
    client_id = f"client_{uuid.uuid4().hex[:10]}"
    await hub.register(client_id, websocket)
    try:
        await websocket.send_json(
            {"type": "connected", "ts": None, "payload": {"client_id": client_id}}
        )
        while True:
            # We do not require inbound messages; this read keeps the connection
            # open and detects disconnects.
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    except Exception:  # noqa: BLE001 - connection boundary
        pass
    finally:
        await hub.unregister(client_id)
