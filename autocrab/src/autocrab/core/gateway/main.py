import uvicorn
from fastapi import FastAPI, WebSocket, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
import time
import uuid

from autocrab.core.models.config import settings
from autocrab.core.models.api import (
    CreateResponseBody,
    ResponseResource,
    Usage,
    OutputMessageItem,
    OutputTextContentPart,
)
from autocrab.core.db.database import engine, Base
import autocrab.core.db.models  # Ensure models are loaded map

def create_app() -> FastAPI:
    """
    Application Factory for the AutoCrab API Gateway.
    Sets up the initial routes and middleware.
    """
    Base.metadata.create_all(bind=engine)
    
    app = FastAPI(
        title="AutoCrab Gateway API",
        version="1.0.0",
        description="The Python-based API Gateway for AutoCrab."
    )

    # Allow connections from the Lit Web UI or Canvas apps
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    async def health_check():
        """Simple health check endpoint."""
        return {"status": "ok", "version": app.version}

    @app.post("/v1/responses", response_model=ResponseResource)
    async def create_response(request: CreateResponseBody):
        """
        Main HTTP endpoint for answering a prompt.
        Phase 1: Stub implementation returning a static completion.
        """
        # Echo the input format back as a stub validation
        input_text = request.input if isinstance(request.input, str) else "complex_payload"
        
        reply_part = OutputTextContentPart(
            text=f"[STUB] Received prompt: {input_text}. Brain not connected yet!"
        )
        
        message_item = OutputMessageItem(
            id=f"msg_{uuid.uuid4().hex[:10]}",
            content=[reply_part],
            status="completed"
        )
        
        return ResponseResource(
            id=f"resp_{uuid.uuid4().hex[:10]}",
            created_at=int(time.time()),
            status="completed",
            model=request.model,
            output=[message_item],
            usage=Usage(input_tokens=0, output_tokens=0, total_tokens=0)
        )

    @app.websocket("/v1/events")
    async def websocket_endpoint(websocket: WebSocket):
        """
        Main WebSocket endpoint for real-time agent streams.
        Phase 1: Accept connection and wait.
        """
        await websocket.accept()
        try:
            while True:
                data = await websocket.receive_json()
                # Just echo back for now
                await websocket.send_json({"type": "ack", "data": data})
        except Exception:
            pass # Handle disconnects gracefully

    return app

# The default application instance
app = create_app()
