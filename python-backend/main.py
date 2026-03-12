from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
import json
import time
import uuid
import aiofiles
import asyncio
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

from config import settings
from context_manager import truncate_context, get_token_count
from model_client import ModelClient

from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import HTTPException
import os

app = FastAPI(title="OpenClaw Python Backend", version="1.0.0")

# CORS - Allow all for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

model_client = ModelClient()

class ChatCompletionRequest(BaseModel):
    messages: List[Dict[str, Any]]
    model: Optional[str] = None
    stream: bool = False
    max_tokens: Optional[int] = None
    temperature: Optional[float] = 0.7
    top_p: Optional[float] = 1.0
    presence_penalty: Optional[float] = 0.0
    frequency_penalty: Optional[float] = 0.0
    tools: Optional[List[Dict[str, Any]]] = None
    tool_choice: Optional[Any] = None


@app.get("/health")
async def health_check():
    return {
        "ok": True,
        "backend": "python",
        "model": settings.model_name
    }

@app.get("/api/health")
async def api_health_check():
    return await health_check()

@app.websocket("/")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    
    # Send connect.challenge
    nonce = str(uuid.uuid4())
    await websocket.send_json({
        "event": "connect.challenge",
        "payload": {"nonce": nonce}
    })
    
    try:
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
            except json.JSONDecodeError:
                continue
                
            msg_type = msg.get("type")
            
            if msg_type == "req":
                req_id = msg.get("id")
                method = msg.get("method")
                
                print(f"WS Request: {method} (id={req_id})")

                if method == "connect":
                    await websocket.send_json({
                         "type": "res",
                         "id": req_id,
                         "ok": True,
                         "payload": {
                             "features": {
                                 "methods": ["health", "channels.status", "doctor.memory.status", "sessions.list", "memory.search", "chat.history", "chat.send"]
                             }
                         }
                    })
                elif method == "ping":
                    await websocket.send_json({
                        "type": "res",
                        "id": req_id,
                        "ok": True,
                        "payload": {"pong": True}
                    })
                elif method == "health":
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
                elif method == "channels.status":
                     await websocket.send_json({
                         "type": "res",
                         "id": req_id,
                         "ok": True,
                         "payload": {}
                     })
                elif method == "doctor.memory.status":
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
                elif method == "sessions.list":
                    sessions = []
                    if os.path.exists(settings.sessions_dir):
                        try:
                            # List .jsonl files in sessions_dir
                            files = [f for f in os.listdir(settings.sessions_dir) if f.endswith(".jsonl")]
                            # Sort by mtime checks
                            files.sort(key=lambda x: os.path.getmtime(os.path.join(settings.sessions_dir, x)), reverse=True)
                            
                            for f in files[:20]: # Limit to 20 recent
                                path = os.path.join(settings.sessions_dir, f)
                                sessions.append({
                                    "id": f.replace(".jsonl", ""),
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
                elif method == "memory.search":
                    query = msg.get("params", {}).get("query", "")
                    results = []
                    # Simple mock search or file grep if memory_dir exists
                    if os.path.exists(settings.memory_dir):
                        # TODO: Implement actual search
                        pass
                        
                    await websocket.send_json({
                        "type": "res",
                        "id": req_id,
                        "ok": True,
                        "payload": {
                            "results": results,
                            "provider": "python-simple",
                            "mode": "text"
                        }
                    })
                elif method == "chat.history":
                    session_key = msg.get("params", {}).get("sessionKey")
                    messages = []
                    if session_key and settings.sessions_dir:
                        session_file = os.path.join(settings.sessions_dir, f"{session_key}.jsonl")
                        if os.path.exists(session_file):
                            async with aiofiles.open(session_file, mode='r') as f:
                                async for line in f:
                                    if line.strip():
                                        try:
                                            messages.append(json.loads(line))
                                        except:
                                            pass

                    await websocket.send_json({
                        "type": "res",
                        "id": req_id,
                        "ok": True,
                        "payload": {
                            "messages": messages,
                            "thinkingLevel": "low"
                        }
                    })
                elif method == "chat.send":
                    session_key = msg.get("params", {}).get("sessionKey")
                    user_message = msg.get("params", {}).get("message")
                    
                    # 1. Send ACK immediately
                    await websocket.send_json({
                        "type": "res",
                        "id": req_id,
                        "ok": True,
                        "payload": {}
                    })

                    # 2. Store User Message
                    if session_key and settings.sessions_dir:
                        if not os.path.exists(settings.sessions_dir):
                            os.makedirs(settings.sessions_dir, exist_ok=True)
                        
                        session_file = os.path.join(settings.sessions_dir, f"{session_key}.jsonl")
                        
                        user_entry = {"role": "user", "content": user_message, "ts": int(time.time() * 1000)}
                        async with aiofiles.open(session_file, mode='a') as f:
                            await f.write(json.dumps(user_entry) + "\n")
                        
                        # 3. Load History
                        history = []
                        async with aiofiles.open(session_file, mode='r') as f:
                             async for line in f:
                                 if line.strip():
                                     try:
                                         msg_obj = json.loads(line)
                                         # Clean for model context
                                         clean_msg = {k: v for k, v in msg_obj.items() if k in ["role", "content", "name", "tool_calls"]}
                                         history.append(clean_msg)
                                     except:
                                         pass
                        
                        # 4. Stream Response
                        run_id = str(uuid.uuid4())
                        full_content = ""
                        seq = 0
                        
                        try:
                            truncated_history = truncate_context(history)
                            async for chunk in model_client.chat_completions(messages=truncated_history, stream=True):
                                 content = chunk.get("content", "")
                                 if content:
                                     full_content += content
                                 
                                 await websocket.send_json({
                                     "type": "event",
                                     "event": "chat.event",
                                     "payload": {
                                         "runId": run_id,
                                         "sessionKey": session_key,
                                         "seq": seq,
                                         "state": "delta",
                                         "message": chunk
                                     }
                                 })
                                 seq += 1
                            
                            # Final event
                            await websocket.send_json({
                                "type": "event",
                                "event": "chat.event",
                                "payload": {
                                    "runId": run_id,
                                    "sessionKey": session_key,
                                    "seq": seq,
                                    "state": "final",
                                    "message": {"role": "assistant", "content": full_content}
                                }
                            })
                            
                            # Save assistant message
                            assistant_entry = {"role": "assistant", "content": full_content, "ts": int(time.time() * 1000)}
                            async with aiofiles.open(session_file, mode='a') as f:
                                await f.write(json.dumps(assistant_entry) + "\n")
                                
                        except Exception as e:
                            print(f"Error generation: {e}")
                            await websocket.send_json({
                                "type": "event",
                                "event": "chat.event",
                                "payload": {
                                    "runId": run_id,
                                    "sessionKey": session_key,
                                    "seq": seq,
                                    "state": "error",
                                    "errorMessage": str(e)
                                }
                            })

                else:
                     await websocket.send_json({
                         "type": "res",
                         "id": req_id,
                         "ok": False,
                         "error": {
                             "code": "method_not_found",
                             "message": f"Method {method} not implemented in Python backend"
                         }
                     })
    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"WebSocket Error: {e}")

@app.post("/v1/chat/completions")
async def chat_completions(request: ChatCompletionRequest):
    # 1. Truncate Context
    # Ensure strict adherence to context window
    truncated_messages = truncate_context(request.messages)
    
    # Log token usage (optional, print to console for debugging)
    original_count = sum(get_token_count(str(m.get("content",""))) for m in request.messages)
    truncated_count = sum(get_token_count(str(m.get("content",""))) for m in truncated_messages)
    print(f"Context: {original_count} tokens -> {truncated_count} tokens (Limit: {settings.max_context_tokens})")

    # 2. Call Model Client
    # We use the requested model or default from config
    model_name = request.model or settings.model_name
    
    # Prepare generator
    generator = model_client.chat_completions(
        messages=truncated_messages,
        stream=request.stream,
        temperature=request.temperature,
        max_tokens=request.max_tokens,
        tools=request.tools,
        tool_choice=request.tool_choice
    )

    if request.stream:
        return StreamingResponse(
            stream_generator(generator, model_name),
            media_type="text/event-stream"
        )
    else:
        # For non-streaming requests, we expect a single full response object from the generator
        full_response = None
        async for item in generator:
            full_response = item
            break # Should be only one
        
        if full_response:
             if "error" in full_response:
                 raise HTTPException(status_code=500, detail=full_response["error"])
             
             # The backend response should already match OpenAI format if it's direct passthrough.
             # However, model_client wraps it slightly differently based on backend.
             # If using OpenAI backend, it's exact.
             # If using Ollama/Llama.cpp, ensure format matches.
             # Our model_client simply runs response.json().
             return JSONResponse(full_response)
        
        raise HTTPException(status_code=500, detail="Empty response from model backend")


@app.get("/v1/channels")
async def get_channels_status():
    """Mock channel status for CLI compatibility"""
    return {}

@app.get("/v1/doctor/memory")
async def get_memory_status():
    """Mock memory status for CLI compatibility"""
    return {
        "agentId": "default",
        "embedding": {
            "ok": True,
            "error": None
        },
        "provider": "python-local"
    }

@app.get("/v1/system/status")
async def system_status():
    return {"ok": True, "version": "1.0.0", "backend": "python"}

@app.get("/api/health")
async def health_check():
    return {"status": "ok", "backend": "python", "model": settings.model_name}

@app.get("/v1/models")
async def list_models():
    """Mock list models endpoint for compatibility."""
    return {
        "object": "list",
        "data": [
            {
                "id": settings.model_name,
                "object": "model",
                "created": 1677610602,
                "owned_by": "openai"
            }
        ]
    }

async def stream_generator(generator, model_name):
    """Wraps delta chunks into OpenAI SSE format"""
    chat_id = f"chatcmpl-{uuid.uuid4()}"
    created = int(time.time())
    
    # We iterate over delta dictionaries from the model_client
    async for delta in generator:
        if "error" in delta:
            # If an error object is yielded, send it. 
            # Standard OpenAI stream usually doesn't send error as data event but as HTTP error.
            # But if stream started, we must break it.
            # Let's send a final chunk with error content for now or just log it.
            print(f"Error in stream: {delta['error']}")
            continue

        chunk = {
            "id": chat_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model_name,
            "choices": [{
                "index": 0,
                "delta": delta,
                "finish_reason": None
            }]
        }
        yield f"data: {json.dumps(chunk)}\n\n"
    
    # Send [DONE]
    yield "data: [DONE]\n\n"

# Serve Frontend Static Files (SPA Pattern)
# Mount static files at root, but ensure API routes take precedence
UI_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../dist/control-ui"))
if os.path.exists(UI_DIR):
    # Mount /assets explicitly if it exists to avoid catch-all interference for static assets
    assets_dir = os.path.join(UI_DIR, "assets")
    if os.path.exists(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    # Catch-all for SPA - serves index.html for any non-API route
    @app.exception_handler(404)
    async def not_found_exception_handler(request, exc):
        # Fallback to index.html for SPA client-side routing
        index_path = os.path.join(UI_DIR, "index.html")
        if os.path.exists(index_path):
             from fastapi.responses import FileResponse
             return FileResponse(index_path)
        return {"detail": "Not Found"}

    # Also mount root to static files, but careful with ordering.
    # Actually, a better pattern for SPA is to catch 404s and serve index.html.
    # If we mount named static file directory directly, it might shadow if path matches.
    # Let's use the 404 handler approach combined with specific asset mounting.
    # If we mount "/" to StaticFiles(html=True), it catches everything.
    # So instead, let's just rely on the 404 handler to serve index.html?
    # No, that's inefficient.
    # The standard way is:
    # 1. Mount /assets
    # 2. Mount other specific static folders.
    # 3. Use a catch-all route at the end for index.html.

    from fastapi.responses import FileResponse

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        # Check if file exists in UI_DIR
        potential_path = os.path.join(UI_DIR, full_path)
        if os.path.exists(potential_path) and os.path.isfile(potential_path):
             return FileResponse(potential_path)
        
        # Otherwise serve index.html
        return FileResponse(os.path.join(UI_DIR, "index.html"))

else:
    print(f"Warning: UI directory not found at {UI_DIR}. Frontend will not be served.")
