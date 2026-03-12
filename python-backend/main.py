from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
import json
import time
import uuid
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
        stream=True, # We always stream from backend to here, but checking request.stream for response
        temperature=request.temperature,
        max_tokens=request.max_tokens
    )

    if request.stream:
        return StreamingResponse(
            stream_generator(generator, model_name),
            media_type="text/event-stream"
        )
    else:
        # Collect full response
        full_content = ""
        async for chunk in generator:
            full_content += chunk
            
        return JSONResponse({
            "id": f"chatcmpl-{uuid.uuid4()}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": model_name,
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": full_content
                },
                "finish_reason": "stop"
            }],
            "usage": {
                "prompt_tokens": truncated_count,
                "completion_tokens": get_token_count(full_content),
                "total_tokens": truncated_count + get_token_count(full_content)
            }
        })


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
    """Wraps content chunks into OpenAI SSE format"""
    chat_id = f"chatcmpl-{uuid.uuid4()}"
    created = int(time.time())
    
    async for content in generator:
        chunk = {
            "id": chat_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model_name,
            "choices": [{
                "index": 0,
                "delta": {"content": content},
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
    app.mount("/", StaticFiles(directory=UI_DIR, html=True, check_dir=False), name="ui")
    
    # Simple workaround for SPA routing (FastAPI StaticFiles doesn't do fallback by default easily)
    # But for a basic "index.html" serve it works if you hit /.
    # For deep links, we might need a catch-all exceptions handler or route.
    @app.exception_handler(404)
    async def not_found_exception_handler(request, exc):
        # Fallback to index.html for SPA client-side routing
        index_path = os.path.join(UI_DIR, "index.html")
        if os.path.exists(index_path):
             from fastapi.responses import FileResponse
             return FileResponse(index_path)
        return {"detail": "Not Found"}
else:
    print(f"Warning: UI directory not found at {UI_DIR}. Frontend will not be served.")
