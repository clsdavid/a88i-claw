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
from autocrab.core.agent.graph import agent_executor
from langchain_core.messages import HumanMessage

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
        Uses the deployed LangGraph ReAct engine (The Brain) to process the request.
        """
        
        input_text = request.input if isinstance(request.input, str) else str(request.input)
        agent_id = request.model or "default"
        session_id = f"{agent_id}_{uuid.uuid4().hex[:8]}"
        
        initial_state = {
            "messages": [HumanMessage(content=input_text)],
            "session_id": session_id,
            "agent_id": agent_id,
            "context": "",
            "instructions": getattr(request, "instructions", None),
            "tool_choice": getattr(request, "tool_choice", None)
        }
        
        final_state = await agent_executor.ainvoke(initial_state)
        last_msg = final_state["messages"][-1]
        
        reply_part = OutputTextContentPart(
            text=str(last_msg.content)
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
        Delegates queries to the LangGraph executor.
        """
        
        await websocket.accept()
        session_id = f"ws_{uuid.uuid4().hex[:8]}"
        try:
            while True:
                data = await websocket.receive_json()
                content = data.get("text", "")
                if not content:
                    await websocket.send_json({"type": "ack", "data": data})
                    continue
                    
                agent_id = data.get("model", "default")
                initial_state = {
                    "messages": [HumanMessage(content=content)],
                    "session_id": session_id,
                    "agent_id": agent_id,
                    "context": "",
                    "instructions": data.get("instructions"),
                    "tool_choice": data.get("tool_choice")
                }
                
                # Stream the graph execution
                async for update in agent_executor.astream(initial_state):
                    for node, state in update.items():
                        if "messages" in state and len(state["messages"]) > 0:
                            last_msg = state["messages"][-1]
                            
                            if hasattr(last_msg, "tool_calls") and last_message.tool_calls:
                                # Agent decided to use a tool
                                for call in last_msg.tool_calls:
                                    await websocket.send_json({
                                        "type": "tool_call",
                                        "name": call["name"],
                                        "args": call["args"]
                                    })
                            elif hasattr(last_msg, "type") and last_msg.type == "tool":
                                # Tool completed
                                await websocket.send_json({
                                    "type": "tool_result",
                                    "name": last_msg.name, # LangGraph ToolMessage usually has name, or we can just send content
                                    "content": last_msg.content
                                })
                            elif hasattr(last_msg, "type") and last_msg.type == "ai" and last_msg.content:
                                # Final AI response
                                await websocket.send_json({
                                    "type": "message", 
                                    "text": str(last_msg.content)
                                })
        except Exception:
            pass # Handle disconnects gracefully

    return app

# The default application instance
app = create_app()
