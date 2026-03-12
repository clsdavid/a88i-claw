from fastapi import WebSocket
from ...config.manager import settings
import os
import aiofiles
import json

async def handle_sessions_list(websocket: WebSocket, req_id: str, params: dict):
    sessions = []
    if os.path.exists(settings.sessions_dir):
        try:
            # List .jsonl files in sessions_dir
            files = [f for f in os.listdir(settings.sessions_dir) if f.endswith(".jsonl")]
            # Sort by mtime checks
            files.sort(key=lambda x: os.path.getmtime(os.path.join(settings.sessions_dir, x)), reverse=True)
            
            for f in files[:20]: # Limit to 20 recent
                path = os.path.join(settings.sessions_dir, f)
                session_id = f.replace(".jsonl", "")
                sessions.append({
                    "id": session_id,
                    "key": session_id,
                    "label": session_id,
                    "path": path,
                    "updated": int(os.path.getmtime(path) * 1000)
                })
        except Exception as e:
            print(f"Error listing sessions: {e}")

    await websocket.send_json({
        "type": "res",
        "id": req_id,
        "ok": True,
        "payload": {
            "sessions": sessions
        }
    })
