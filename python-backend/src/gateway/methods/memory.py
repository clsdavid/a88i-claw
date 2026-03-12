from fastapi import WebSocket
from ...config.manager import settings
import os
import aiofiles

async def handle_memory_search(websocket: WebSocket, req_id: str, params: dict):
    query = params.get("query", "").lower()
    results = []
    
    if os.path.exists(settings.memory_dir):
        try:
            # List .md files
            files = [f for f in os.listdir(settings.memory_dir) if f.endswith(".md")]
            for filename in files:
                filepath = os.path.join(settings.memory_dir, filename)
                try:
                    async with aiofiles.open(filepath, mode='r', errors='ignore') as f:
                        content = await f.read()
                        if query in content.lower():
                            # Simple snippet extraction
                            idx = content.lower().find(query)
                            start = max(0, idx - 50)
                            end = min(len(content), idx + 150)
                            snippet = content[start:end].replace("\n", " ")
                            
                            results.append({
                                "file": filename,
                                "snippet": f"...{snippet}...",
                                "path": filepath
                            })
                except Exception as e:
                    print(f"Error reading {filename}: {e}")
        except Exception as e:
             print(f"Error searching memory: {e}")

    await websocket.send_json({
        "type": "res",
        "id": req_id,
        "ok": True,
        "payload": {
            "results": results,
            "provider": "python-local-fs",
            "mode": "text"
        }
    })

async def handle_doctor_memory_status(websocket: WebSocket, req_id: str, params: dict):
     await websocket.send_json({
         "type": "res",
         "id": req_id,
         "ok": True,
         "payload": {
            "agentId": "default",
            "embedding": {"ok": True, "error": None},
            "provider": "python-local"
         }
     })
