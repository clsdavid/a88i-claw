from fastapi import WebSocket
from ...config.manager import settings
import time
import uuid

async def handle_ping(websocket: WebSocket, req_id: str, params: dict):
    await websocket.send_json({
        "type": "res",
        "id": req_id,
        "ok": True,
        "payload": {"pong": True}
    })


async def handle_health(websocket: WebSocket, req_id: str, params: dict):
     await websocket.send_json({
         "type": "res",
         "id": req_id,
         "ok": True,
         "payload": {
             "ok": True,
             "backend": "python",
             "model": settings.model_name,
             "ts": int(time.time() * 1000),
             "durationMs": 0,
             "channels": {},
             "channelOrder": [],
             "channelLabels": {},
             "heartbeatSeconds": 0,
             "defaultAgentId": "default",
             "agents": [],
             "sessions": {
                 "path": "/tmp",
                 "count": 0,
                 "recent": []
             }
         }
     })

async def handle_channels_status(websocket: WebSocket, req_id: str, params: dict):
     await websocket.send_json({
         "type": "res",
         "id": req_id,
         "ok": True,
         "payload": {}
     })

async def handle_cron_status(websocket: WebSocket, req_id: str, params: dict):
     await websocket.send_json({
        "type": "res",
        "id": req_id,
        "ok": True,
        "payload": {
             "jobs": [],
             "running": False
        }
    })

async def handle_cron_list(websocket: WebSocket, req_id: str, params: dict):
     await websocket.send_json({
        "type": "res",
        "id": req_id,
        "ok": True,
        "payload": {
            "jobs": []
        }
    })

async def handle_cron_runs(websocket: WebSocket, req_id: str, params: dict):
     await websocket.send_json({
        "type": "res",
        "id": req_id,
        "ok": True,
        "payload": {
            "runs": []
        }
    })

async def handle_node_list(websocket: WebSocket, req_id: str, params: dict):
    # Mock node list response
    await websocket.send_json({
        "type": "res",
        "id": req_id,
        "ok": True,
        "payload": {
            "nodes": [
                {
                    "nodeId": "local-machine",
                    "name": "Local Machine",
                    "connected": True,
                    "platform": "linux",
                    "version": "1.0.0"
                }
            ]
        }
    })

async def handle_device_pair_list(websocket: WebSocket, req_id: str, params: dict):
      await websocket.send_json({
        "type": "res",
        "id": req_id,
        "ok": True,
        "payload": {
            "pairs": []
        }
    })
