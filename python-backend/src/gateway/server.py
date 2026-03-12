import json
import logging
import os
from pathlib import Path
from typing import Dict, Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from ..config.manager import settings
from .registry import get_handler

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("gateway")

app = FastAPI()

# Input loop
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# FRONTEND SERVING
# Resolve project root relative to this file: src/gateway/server.py -> 3 levels up to python-backend -> 1 level up to repo root
PROJECT_ROOT = Path(__file__).resolve().parents[3]
FRONTEND_DIST = PROJECT_ROOT / "dist" / "control-ui"

# Define WS endpoint first
# Handlers for both /ws and / (root) to support different clients
async def websocket_handler(websocket: WebSocket):
    await websocket.accept()
    logger.info("Client connected")
    
    try:
        # Challenge for older clients expecting it on connect
        if websocket.url.path == "/":
             import uuid
             nonce = str(uuid.uuid4())
             await websocket.send_json({
                 "event": "connect.challenge", 
                 "payload": {"nonce": nonce}
             })

        while True:
            try:
                data = await websocket.receive_text()
                message = json.loads(data)
                
                msg_type = message.get("type")
                req_id = message.get("id")
                method = message.get("method")
                params = message.get("params", {})

                if msg_type == "req":
                    if method == "connect":
                        await websocket.send_json({
                             "type": "res",
                             "id": req_id,
                             "ok": True,
                             "payload": {}
                        })
                        continue

                    handler = get_handler(method)
                    if handler:
                        logger.info(f"Handling method: {method} id: {req_id}")
                        try:
                            # Await the handler
                            await handler(websocket, req_id, params)
                        except Exception as e:
                            logger.error(f"Error executing {method}: {e}", exc_info=True)
                            await websocket.send_json({
                                "type": "res",
                                "id": req_id,
                                "ok": False,
                                "error": str(e)
                            })
                    else:
                        logger.warning(f"Unknown method: {method}")
                        await websocket.send_json({
                            "type": "res",
                            "id": req_id,
                            "ok": False,
                            "error": f"Method {method} not found"
                        })
                        
                elif msg_type == "ping":
                     await websocket.send_json({"type": "pong"})

            except json.JSONDecodeError:
                logger.error("Invalid JSON received")
                await websocket.send_json({"error": "Invalid JSON"})
                
    except WebSocketDisconnect:
        logger.info("Client disconnected")
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)

app.websocket("/ws")(websocket_handler)
app.websocket("/")(websocket_handler)

# Define static handling last
if FRONTEND_DIST.exists():
    logger.info(f"Serving frontend from {FRONTEND_DIST}")
    # Mount assets
    if (FRONTEND_DIST / "assets").exists():
        app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIST / "assets")), name="assets")
    
    # Root
    @app.get("/")
    async def serve_index():
         return FileResponse(FRONTEND_DIST / "index.html")
    
    # Config
    @app.get("/__autocrab/control-ui-config.json")
    async def serve_config():
        return {"backend": "python", "environment": "dev", "ws": "/"}

    # Catch-all for SPA
    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        # Allow requests to specific files
        file_path = FRONTEND_DIST / full_path
        if file_path.exists() and file_path.is_file():
            return FileResponse(file_path)
            
        # Otherwise serve index.html
        return FileResponse(FRONTEND_DIST / "index.html")
else:
    logger.warning(f"Frontend dist not found at {FRONTEND_DIST}")
    @app.get("/")
    async def root():
        return {"status": "ok", "service": "autocrab-python-backend", "warning": "frontend_not_found"}
