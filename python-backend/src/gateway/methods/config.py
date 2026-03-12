from fastapi import WebSocket
from ...config.manager import settings

async def handle_config_get(websocket: WebSocket, req_id: str, params: dict):
     await websocket.send_json({
        "type": "res",
        "id": req_id,
        "ok": True,
        "payload": {
            "config": {}
        }
    })

async def handle_config_schema(websocket: WebSocket, req_id: str, params: dict):
     # Return minimal schema
     await websocket.send_json({
        "type": "res",
        "id": req_id,
        "ok": True,
        "payload": {
            "schema": {
                "type": "object",
                "properties": {},
                "additionalProperties": True
            },
            "uiHints": {},
            "version": "1.0.0",
            "generatedAt": "2026-03-12T00:00:00Z"
        }
    })

async def handle_config_schema_lookup(websocket: WebSocket, req_id: str, params: dict):
     path = params.get("path", "")
     # Return minimal lookup
     await websocket.send_json({
        "type": "res",
        "id": req_id,
        "ok": True,
        "payload": {
            "path": path,
            "schema": {},
            "children": []
        }
    })

async def handle_models_list(websocket: WebSocket, req_id: str, params: dict):
     await websocket.send_json({
        "type": "res",
        "id": req_id,
        "ok": True,
        "payload": {
            "models": [{"id": settings.model_name}]
        }
    })
