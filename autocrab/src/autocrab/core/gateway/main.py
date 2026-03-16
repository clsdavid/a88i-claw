import uvicorn
import os
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
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
        title="AutoCrab Gateway",
        version="1.0.0",
        description="The Python-based API Gateway for AutoCrab."
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 1. Resolve UI Path
    current_dir = os.path.dirname(os.path.abspath(__file__))
    # /home/chenl/Projects/a88i-claw/autocrab/src/autocrab/core/gateway/main.py
    # We need to go up 5 levels to reach Projects/a88i-claw
    root_path = current_dir
    for _ in range(5):
        root_path = os.path.dirname(root_path)
    ui_path = os.path.join(root_path, "dist", "control-ui")

    # 2. Add Health Check
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

    # 3. Add WebSocket
    @app.websocket("/gateway")
    @app.websocket("/")
    async def websocket_endpoint(websocket: WebSocket):
        """
        Main WebSocket endpoint for real-time agent streams.
        Implements the AutoCrab Gateway protocol (connect handshake, req/res framing).
        """
        print(f"WS: New connection from {websocket.client}")
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
                        from autocrab.core.models.gateway import SessionDefaults
                        
                        default_id = "main"
                        if settings.agents and settings.agents.list:
                            has_default = False
                            for agent in settings.agents.list:
                                if agent.default:
                                    default_id = agent.id
                                    has_default = True
                                    break
                            if not has_default and settings.agents.list:
                                default_id = settings.agents.list[0].id
                                    
                        snapshot = Snapshot(
                            stateVersion=StateVersion(presence=1, health=1),
                            uptimeMs=int(time.time() * 1000),
                            sessionDefaults=SessionDefaults(
                                defaultAgentId=default_id,
                                mainKey="main",
                                mainSessionKey="main"
                            )
                        )
                        
                        hello_ok = HelloOk(
                            protocol=3,
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
                                    
                                    # Handle Start of Tool Calls (AIMessage with tool_calls)
                                    tool_calls = getattr(last_msg, "tool_calls", [])
                                    if not tool_calls and hasattr(last_msg, "additional_kwargs"):
                                        tool_calls = last_msg.additional_kwargs.get("tool_calls", [])
                                        
                                    if tool_calls:
                                        for tool_call in tool_calls:
                                            # Normalize tool_call format
                                            t_name = ""
                                            t_args = ""
                                            t_id = ""
                                            
                                            if isinstance(tool_call, dict):
                                                t_id = tool_call.get("id", str(uuid.uuid4()))
                                                t_name = tool_call.get("name") or tool_call.get("function", {}).get("name", "tool")
                                                t_args = tool_call.get("args") or tool_call.get("function", {}).get("arguments", "{}")
                                            else:
                                                t_id = getattr(tool_call, "id", str(uuid.uuid4()))
                                                t_name = getattr(tool_call, "name", "tool")
                                                t_args = json.dumps(getattr(tool_call, "args", {}))

                                            event = {
                                                "type": "event",
                                                "event": "agent",
                                                "payload": {
                                                    "runId": session_id,
                                                    "sessionKey": session_id,
                                                    "stream": "tool",
                                                    "ts": int(time.time() * 1000),
                                                    "data": {
                                                        "toolCallId": t_id,
                                                        "name": t_name,
                                                        "phase": "start",
                                                        "args": t_args
                                                    }
                                                }
                                            }
                                            await websocket.send_json(event)
                                            print(f"WS: Emitted tool start: {t_name}")

                                    # Handle End of Tool Calls (ToolMessage)
                                    elif hasattr(last_msg, "type") and last_msg.type == "tool":
                                        t_id = getattr(last_msg, "tool_call_id", "call_1")
                                        t_name = getattr(last_msg, "name", "tool")
                                        
                                        event = {
                                            "type": "event",
                                            "event": "agent",
                                            "payload": {
                                                "runId": session_id,
                                                "sessionKey": session_id,
                                                "stream": "tool",
                                                "ts": int(time.time() * 1000),
                                                "data": {
                                                    "toolCallId": t_id,
                                                    "name": t_name,
                                                    "phase": "end",
                                                    "output": str(last_msg.content)
                                                }
                                            }
                                        }
                                        await websocket.send_json(event)
                                        print(f"WS: Emitted tool end: {t_name}")
                                    elif hasattr(last_msg, "type") and last_msg.type == "ai" and last_msg.content:
                                        event = {
                                            "type": "event",
                                            "event": "chat",
                                            "payload": {
                                                "runId": session_id,
                                                "sessionKey": session_id,
                                                "state": "delta",
                                                "message": {
                                                    "role": "assistant",
                                                    "content": [{"type": "text", "text": str(last_msg.content)}],
                                                    "timestamp": int(time.time() * 1000)
                                                }
                                            }
                                        }
                                        await websocket.send_json(event)
                                        
                        # Send final chat event when done
                        final_event = {
                            "type": "event",
                            "event": "chat",
                            "payload": {
                                "runId": session_id,
                                "sessionKey": session_id,
                                "state": "final"
                            }
                        }
                        await websocket.send_json(final_event)

                    elif method == "agents.list":
                        from autocrab.core.models.gateway import AgentsListResult, AgentSummary, AgentIdentity
                        agent_summaries = []
                        if not settings.agents or not settings.agents.list:
                             agent_summaries.append(AgentSummary(
                                id="main",
                                name="AutoCrab",
                                identity=AgentIdentity(
                                    name="AutoCrab",
                                    emoji="🦀"
                                )
                            ))
                        else:
                            for agent in settings.agents.list:
                                agent_summaries.append(AgentSummary(
                                    id=agent.id,
                                    name=agent.name or agent.id,
                                    identity=AgentIdentity(
                                        name=agent.name or agent.id,
                                        emoji=agent.params.get("emoji") if agent.params else "🤖",
                                        avatar=agent.params.get("avatar") if agent.params else None
                                    )
                                ))
                        
                        default_id = "main"
                        if settings.agents and settings.agents.list:
                            has_default = False
                            for agent in settings.agents.list:
                                if agent.default:
                                    default_id = agent.id
                                    has_default = True
                                    break
                            if not has_default and settings.agents.list:
                                default_id = settings.agents.list[0].id
                        
                        payload = AgentsListResult(
                            defaultId=default_id,
                            mainKey="main",
                            scope="per-sender",
                            agents=agent_summaries
                        )
                        print(f"WS: agents.list result: {payload.model_dump()}")
                        await websocket.send_json(ResponseFrame(id=req.id, ok=True, payload=payload.model_dump()).model_dump())

                    elif method == "models.list":
                        from autocrab.core.models.gateway import ModelsListResult, ModelChoice
                        model_choices = []
                        if settings.models and settings.models.providers:
                            for p_name, p_config in settings.models.providers.items():
                                if p_config.models:
                                    for m in p_config.models:
                                        m_id = m.id
                                        # If id doesn't have provider prefix, add it (parity with Node.js)
                                        if "/" not in m_id:
                                            m_id = f"{p_name}/{m_id}"
                                            
                                        model_choices.append(ModelChoice(
                                            id=m_id,
                                            name=m.name,
                                            provider=p_name,
                                            contextWindow=m.contextWindow,
                                            reasoning=m.reasoning
                                        ))
                        
                        payload = ModelsListResult(models=model_choices)
                        print(f"WS: models.list result: {payload.model_dump()}")
                        await websocket.send_json(ResponseFrame(id=req.id, ok=True, payload=payload.model_dump()).model_dump())

                    elif method == "tools.catalog":
                        # Returning basic catalog for now
                        payload = {
                            "agentId": req.params.get("agentId", "main") if req.params else "main",
                            "profiles": [
                                {"id": "minimal", "label": "Minimal"},
                                {"id": "coding", "label": "Coding"},
                                {"id": "full", "label": "Full"}
                            ],
                            "groups": [
                                {
                                    "id": "core",
                                    "label": "Core Tools",
                                    "source": "core",
                                    "tools": [
                                        {"id": "fs_read", "label": "Read File", "description": "Read file content", "source": "core", "defaultProfiles": ["minimal", "coding", "full"]},
                                        {"id": "fs_list", "label": "List Files", "description": "List files in directory", "source": "core", "defaultProfiles": ["coding", "full"]}
                                    ]
                                }
                            ]
                        }
                        await websocket.send_json(ResponseFrame(id=req.id, ok=True, payload=payload).model_dump())

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

    # 4. Add catch-all UI serving at the END
    if os.path.exists(ui_path):
        from fastapi.responses import FileResponse
        
        @app.get("/{full_path:path}")
        async def serve_ui(full_path: str):
            # Ensure the path is safe
            if ".." in full_path:
                return FileResponse(os.path.join(ui_path, "index.html"))
            
            target_path = os.path.join(ui_path, full_path)
            if full_path and os.path.isfile(target_path):
                return FileResponse(target_path)
            
            # Fallback to index.html for SPA routing or missing files
            return FileResponse(os.path.join(ui_path, "index.html"))
            
        print(f"Serving UI from {ui_path} via catch-all route")
    else:
        print(f"Warning: UI path {ui_path} not found. Static serving disabled.")

    @app.on_event("startup")
    async def startup_event():
        """
        Runs on API startup.
        Initializes and connects all configured ecosystem channel plugins.
        """
        from autocrab.core.plugins.loader import load_plugins_from_directory, start_all_channels
        from autocrab.core.plugins.handler import handle_channel_event
        
        # Discover Plugins
        plugin_base = os.path.join(os.path.dirname(__file__), "..", "..", "plugins", "channels")
        if os.path.exists(plugin_base):
            for subdir in os.listdir(plugin_base):
                plugin_dir = os.path.join(plugin_base, subdir)
                if os.path.isdir(plugin_dir):
                    load_plugins_from_directory(plugin_dir)
        
        # Start all discovered channel plugins
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

if __name__ == "__main__":
    port = int(os.environ.get("AUTOCRAB_GATEWAY_PORT", 5174))
    uvicorn.run(app, host="0.0.0.0", port=port)
