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
        Implements the AutoCrab Gateway protocol (connect handshake, req/res framing).
        """
        from autocrab.core.models.gateway import (
            ConnectParams, HelloOk, RequestFrame, ResponseFrame, EventFrame, 
            Snapshot, StateVersion, ErrorShape
        )
        
        await websocket.accept()
        conn_id = str(uuid.uuid4())
        session_id = f"ws_{conn_id[:8]}"
        
        # 1. Send connect challenge
        connect_nonce = str(uuid.uuid4())
        await websocket.send_json({
            "type": "event",
            "event": "connect.challenge",
            "payload": {"nonce": connect_nonce, "ts": int(time.time() * 1000)}
        })
        
        client_connected = False
        
        try:
            while True:
                data = await websocket.receive_json()
                
                # Protocol Framing: Wait for 'connect' request first
                if not client_connected:
                    if data.get("type") == "req" and data.get("method") == "connect":
                        # Validate connect params (simplified for now)
                        req = RequestFrame(**data)
                        
                        # Send hello-ok response
                        snapshot = Snapshot(
                            stateVersion=StateVersion(presence=1, health=1),
                            uptimeMs=int(time.time() * 1000), # Simple uptime for now
                        )
                        
                        hello_ok = HelloOk(
                            protocol=1,
                            server={"version": app.version, "name": "AutoCrab Python"},
                            features={"caps": ["chat", "tools", "plugins"]},
                            snapshot=snapshot,
                            policy={"handshakeTimeoutMs": 30000}
                        )
                        
                        res = ResponseFrame(
                            id=req.id,
                            ok=True,
                            payload=hello_ok.model_dump()
                        )
                        await websocket.send_json(res.model_dump())
                        client_connected = True
                        continue
                    else:
                        # Close if first frame is not connect
                        await websocket.close(code=1008)
                        break
                
                # Handle subsequent requests
                if data.get("type") == "req":
                    req = RequestFrame(**data)
                    method = req.method
                    
                    if method == "chat.send":
                        params = req.params or {}
                        content = params.get("text", "")
                        agent_id = params.get("model", "default")
                        
                        # Start streaming response
                        initial_state = {
                            "messages": [HumanMessage(content=content)],
                            "session_id": session_id,
                            "agent_id": agent_id,
                            "context": "",
                            "instructions": params.get("instructions"),
                            "tool_choice": params.get("tool_choice")
                        }
                        
                        # Send initial 'ack' or similar if needed (optional for req/res)
                        # The response to the request should be 'ok' true once the stream starts or finishes.
                        # Original protocol usually sends 'res' once the request is accepted, then 'event' for data.
                        
                        await websocket.send_json(ResponseFrame(id=req.id, ok=True).model_dump())
                        
                        async for update in agent_executor.astream(initial_state):
                            for node, state in update.items():
                                if "messages" in state and len(state["messages"]) > 0:
                                    last_msg = state["messages"][-1]
                                    
                                    if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
                                        for call in last_msg.tool_calls:
                                            event = EventFrame(
                                                event="tool_call",
                                                payload={"name": call["name"], "args": call["args"]}
                                            )
                                            await websocket.send_json(event.model_dump())
                                    elif hasattr(last_msg, "type") and last_msg.type == "tool":
                                        event = EventFrame(
                                            event="tool_result",
                                            payload={"name": last_msg.name, "content": last_msg.content}
                                        )
                                        await websocket.send_json(event.model_dump())
                                    elif hasattr(last_msg, "type") and last_msg.type == "ai" and last_msg.content:
                                        event = EventFrame(
                                            event="chat.send.delta",
                                            payload={"text": str(last_msg.content)}
                                        )
                                        await websocket.send_json(event.model_dump())
                                        
                        # Send chat.send.completion event when done
                        await websocket.send_json(EventFrame(event="chat.send.completion", payload={}).model_dump())

                    elif method == "ping":
                         await websocket.send_json(ResponseFrame(id=req.id, ok=True, payload="pong").model_dump())
                    
                    else:
                        # Unknown method
                        await websocket.send_json(ResponseFrame(
                            id=req.id, 
                            ok=False, 
                            error=ErrorShape(code="METHOD_NOT_FOUND", message=f"Method {method} not found")
                        ).model_dump())

        except Exception as e:
            print(f"WS Error: {str(e)}")
            pass # Handle disconnects gracefully

    @app.on_event("startup")
    async def startup_event():
        """
        Runs on API startup.
        Initializes and connects all configured ecosystem channel plugins.
        """
        import os
        from fastapi.staticfiles import StaticFiles
        from autocrab.core.plugins.loader import load_plugins_from_directory, start_all_channels
        from autocrab.core.plugins.handler import handle_channel_event
        
        # 1. Mount Static Files for UI
        ui_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "dist", "control-ui"))
        if os.path.exists(ui_path):
            app.mount("/", StaticFiles(directory=ui_path, html=True), name="ui")
            print(f"Mounted UI from {ui_path}")
        else:
            print(f"Warning: UI path {ui_path} not found. Static serving disabled.")

        # 2. Discover Plugins
        plugin_base = os.path.join(os.path.dirname(__file__), "..", "..", "plugins", "channels")
        if os.path.exists(plugin_base):
            for subdir in os.listdir(plugin_base):
                plugin_dir = os.path.join(plugin_base, subdir)
                if os.path.isdir(plugin_dir):
                    load_plugins_from_directory(plugin_dir)
        
        # 3. Start all discovered channel plugins with the central handler
        print("Starting ecosystem channel plugins...")
        await start_all_channels(on_event=handle_channel_event)

    @app.on_event("shutdown")
    async def shutdown_event():
        """Gracefully shuts down ecosystem plugins."""
        from autocrab.core.plugins.loader import stop_all_channels
        await stop_all_channels()

    return app

# The default application instance
app = create_app()
