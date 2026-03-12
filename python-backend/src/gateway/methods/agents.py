from fastapi import WebSocket

async def handle_agents_list(websocket: WebSocket, req_id: str, params: dict):
     await websocket.send_json({
        "type": "res",
        "id": req_id,
        "ok": True,
        "payload": {
            "defaultId": "default",
            "mainKey": "default",
            "scope": "user",
            "agents": [
                {
                    "id": "default", 
                    "name": "Python Agent", 
                    "description": "Local Python Agent", 
                    "color": "blue",
                    "avatar": "🤖"
                }
            ]
        }
    })

async def handle_agent_identity_get(websocket: WebSocket, req_id: str, params: dict):
    await websocket.send_json({
        "type": "res",
        "id": req_id,
        "ok": True,
        "payload": {
            "agentId": "default", 
            "name": "Python Agent", 
            "avatar": "🤖", 
            "emoji": "🤖"
        }
    })

async def handle_tools_catalog(websocket: WebSocket, req_id: str, params: dict):
     await websocket.send_json({
        "type": "res",
        "id": req_id,
        "ok": True,
        "payload": {
            "agentId": "default",
            "profiles": [],
            "groups": []
        }
    })
