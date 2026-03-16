import uvicorn
import os
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import time
import uuid
from pathlib import Path

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
import socket
import platform
import hashlib
import json

# Global state tracking
presence_store = {}
START_TIME = time.time()

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
        print(f"WS: New connection from {websocket.client}", flush=True)
        from autocrab.core.models.gateway import (
            ConnectParams, HelloOk, RequestFrame, ResponseFrame, EventFrame, 
            Snapshot, StateVersion, ErrorShape, ModelsListResult, ModelChoice,
            ExecApprovalsSnapshot, ExecApprovalsFile,
            AgentsFilesListResult, AgentsFilesGetResult, AgentsFilesSetResult, AgentFileEntry
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
                        from autocrab.core.models.gateway import SessionDefaults, PresenceEntry
                        from autocrab.core.agent.memory import HybridMemoryStore
                        
                        client_info = req.params.get("client") if req.params else None
                        client_id = client_info.get("id") if client_info else conn_id
                        
                        # Register in presence store
                        presence_store[conn_id] = PresenceEntry(
                            deviceId=client_id,
                            instanceId=client_info.get("instanceId") if client_info else None,
                            host=socket.gethostname(),
                            ip=socket.gethostbyname(socket.gethostname()),
                            version=client_info.get("version") if client_info else "1.0.0",
                            platform=client_info.get("platform") if client_info else platform.system(),
                            mode=client_info.get("mode") if client_info else "client",
                            ts=int(time.time() * 1000),
                            text=f"Client: {client_id}"
                        )

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
                            presence=[],
                            health={}, # Non-null as required by schema
                            stateVersion=StateVersion(presence=1, health=1),
                            uptimeMs=int((time.time() - START_TIME) * 1000),
                            sessionDefaults=SessionDefaults(
                                defaultAgentId=default_id,
                                mainKey="main",
                                mainSessionKey="main"
                            )
                        )
                        
                        from autocrab.core.models.gateway import HelloOkServer, HelloOkFeatures, HelloOkPolicy
                        
                        hello_ok = HelloOk(
                            protocol=3,
                            server=HelloOkServer(version=app.version, connId=conn_id),
                            features=HelloOkFeatures(
                                methods=[
                                    "chat.send", "chat.history", "system-presence", "system-event",
                                    "config.get", "config.schema", "sessions.list",
                                    "skills.status", "skills.bins", "skills.install",
                                    "channels.status", "cron.runs", "cron.list", "cron.status",
                                    "agents.list", "models.list", "tools.catalog", "ping",
                                    "status", "health", "last-heartbeat",
                                    "exec.approvals.get", "exec.approvals.set",
                                    "agents.files.list", "agents.files.get", "agents.files.set"
                                ],
                                events=["chat", "agent", "connect.challenge", "connect.ack"]
                            ),
                            snapshot=snapshot,
                            policy=HelloOkPolicy()
                        )
                        
                        res = ResponseFrame(
                            id=req.id,
                            ok=True,
                            payload=hello_ok.model_dump()
                        )
                        print(f"WS: Sending hello-ok for {conn_id}", flush=True)
                        await websocket.send_json(res.model_dump())
                        
                        # 3. Send connect.ack to finalize handshake
                        print(f"WS: Sending connect.ack for {conn_id}", flush=True)
                        await websocket.send_json({
                            "type": "event",
                            "event": "connect.ack",
                            "payload": {
                                "connId": conn_id,
                                "snapshot": snapshot.model_dump()
                            }
                        })
                        
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
                    full_ai_response = "" # Track for persistence
                    
                    if method == "chat.send":
                        params = req.params or {}
                        content = params.get("text", "") # Standard model-agnostic text field
                        if not content:
                            content = params.get("message", "") # Fallback to core-compatible 'message' field
                            
                        agent_id = params.get("model", "main")
                        
                        # sessionKey is the unique ID for the conversation thread
                        session_key = params.get("sessionKey", "main")
                        
                        # Persistence: Record Human message
                        store = HybridMemoryStore(session_id=session_key, agent_id=agent_id)
                        await store.add_interaction("human", content)
                        
                        # Start streaming response
                        initial_state = {
                            "messages": [HumanMessage(content=content)],
                            "session_id": session_key,
                            "agent_id": agent_id,
                            "context": "",
                            "instructions": params.get("instructions"),
                            "tool_choice": params.get("tool_choice")
                        }
                        
                        print(f"WS: Starting astream_events for session_key={session_key} (conn={session_id}, flush=True)")
                        try:
                            # Use agent_executor from module import. 
                            # If using a multi-agent system, we'd look up the specific executor here.
                            async for event_data in agent_executor.astream_events(initial_state, version="v2"):
                                kind = event_data["event"]
                                # print(f"WS: Event kind={kind}", flush=True) # Aggressive debug
                                
                                # Real-time Token Streaming
                                if kind == "on_chat_model_stream":
                                    chunk = event_data["data"]["chunk"]
                                    if hasattr(chunk, "content") and chunk.content:
                                        text_delta = chunk.content
                                        if isinstance(text_delta, list):
                                            text_delta = "".join([c.get("text", "") for c in text_delta if isinstance(c, dict) and "text" in c])
                                        
                                        if text_delta:
                                            ws_event = {
                                                "type": "event",
                                                "event": "chat",
                                                "payload": {
                                                    "runId": session_key,
                                                    "sessionKey": session_key,
                                                    "state": "delta",
                                                    "message": {
                                                        "role": "assistant",
                                                        "text": str(text_delta), # Standard text field (trim safety)
                                                        "content": [{"type": "text", "text": str(text_delta)}],
                                                        "timestamp": int(time.time() * 1000)
                                                    }
                                                }
                                            }
                                            await websocket.send_json(ws_event)
                                            full_ai_response += str(text_delta)

                                # Tool Start Events
                                elif kind == "on_tool_start":
                                    t_name = event_data["name"]
                                    t_args = json.dumps(event_data["data"].get("input", {}))
                                    t_id = event_data["run_id"]
                                    
                                    ws_event = {
                                        "type": "event",
                                        "event": "agent",
                                        "payload": {
                                            "runId": session_key,
                                            "sessionKey": session_key,
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
                                    await websocket.send_json(ws_event)
                                    print(f"WS: Emitted tool start: {t_name}", flush=True)

                                # Tool End Events
                                elif kind == "on_tool_end":
                                    t_name = event_data["name"]
                                    t_output = str(event_data["data"].get("output", ""))
                                    t_id = event_data["run_id"]
                                    
                                    ws_event = {
                                        "type": "event",
                                        "event": "agent",
                                        "payload": {
                                            "runId": session_key,
                                            "sessionKey": session_key,
                                            "stream": "tool",
                                            "ts": int(time.time() * 1000),
                                            "data": {
                                                "toolCallId": t_id,
                                                "name": t_name,
                                                "phase": "end",
                                                "output": t_output
                                            }
                                        }
                                    }
                                    await websocket.send_json(ws_event)
                                    print(f"WS: Emitted tool end: {t_name}", flush=True)
                            print(f"WS: astream_events loop finished for {session_key}", flush=True)
                                    
                        except Exception as e:
                            print(f"WS: Error in astream_events for session {session_key}: {e}", flush=True)
                            import traceback
                            traceback.print_exc()

                        # Final Persistence: Record Assistant message
                        if full_ai_response:
                            await store.add_interaction("assistant", full_ai_response)
                        else:
                            print(f"WS: No response captured for session {session_key}", flush=True)
                            
                        # Send final chat event when done
                        final_event = {
                            "type": "event",
                            "event": "chat",
                            "payload": {
                                "runId": session_key,
                                "sessionKey": session_key,
                                "state": "final"
                            }
                        }
                        await websocket.send_json(final_event)
                        
                        # Finally, acknowledge the original request is COMPLETE
                        await websocket.send_json(ResponseFrame(id=req.id, ok=True).model_dump())
                        print(f"WS: Sent ResponseFrame for chat.send {req.id}", flush=True)

                    elif method == "chat.history":
                        params = req.params or {}
                        session_key = params.get("sessionKey", "main")
                        agent_id = params.get("model", "main")
                        limit = params.get("limit", 200)
                        
                        from autocrab.core.agent.memory import HybridMemoryStore
                        store = HybridMemoryStore(session_id=session_key, agent_id=agent_id)
                        messages = store.writer.load_messages()
                        
                        # Slicing
                        if len(messages) > limit:
                            messages = messages[-limit:]
                            
                        # Formatting to match original protocol
                        formatted_messages = []
                        for m in messages:
                            formatted_messages.append({
                                "role": m["role"],
                                "content": [{"type": "text", "text": m["content"]}],
                                "timestamp": m["timestamp"]
                            })
                            
                        payload = {
                            "sessionKey": session_key,
                            "sessionId": session_key, # Usually same as key in flat-file mode
                            "messages": formatted_messages,
                            "thinkingLevel": "none",
                            "verboseLevel": "none"
                        }
                        await websocket.send_json(ResponseFrame(id=req.id, ok=True, payload=payload).model_dump())

                    elif method == "system-presence":
                        # Return all active entries
                        print(f"WS: system-presence requested, count={len(presence_store)}", flush=True)
                        now_ms = int(time.time() * 1000)
                        # Basic cleanup: remove entries older than 5 minutes
                        expired = [k for k, v in presence_store.items() if now_ms - v.ts > 300000]
                        for k in expired:
                            del presence_store[k]
                            
                        presence_list = [v.model_dump() for v in presence_store.values()]
                        await websocket.send_json(ResponseFrame(id=req.id, ok=True, payload=presence_list).model_dump())

                    elif method == "system-event":
                        # Update presence based on event
                        params = req.params or {}
                        text = params.get("text", "Event")
                        if conn_id in presence_store:
                            entry = presence_store[conn_id]
                            entry.text = text
                            entry.ts = int(time.time() * 1000)
                            if params.get("mode"):
                                entry.mode = params.get("mode")
                        
                        await websocket.send_json(ResponseFrame(id=req.id, ok=True, payload={"ok": True}).model_dump())

                    elif method == "config.get":
                        from autocrab.core.models.gateway import ConfigFileSnapshot
                        config_path = settings.config_root / "autocrab.json"
                        raw_content = None
                        if config_path.exists():
                            with open(config_path, "r", encoding="utf-8") as f:
                                raw_content = f.read()
                        
                        config_hash = hashlib.sha256(raw_content.encode()).hexdigest() if raw_content else None
                        
                        snapshot = ConfigFileSnapshot(
                            path=str(config_path),
                            exists=config_path.exists(),
                            valid=True,
                            raw=raw_content,
                            parsed=settings.model_dump(),
                            resolved=settings.model_dump(),
                            config=settings.model_dump(),
                            hash=config_hash
                        )
                        await websocket.send_json(ResponseFrame(id=req.id, ok=True, payload=snapshot.model_dump()).model_dump())

                    elif method == "config.schema":
                        # Basic schema to satisfy UI
                        schema = {
                            "type": "object",
                            "properties": {
                                "gateway": {"type": "object"},
                                "agents": {"type": "object"},
                                "models": {"type": "object"}
                            },
                            "uiHints": {}
                        }
                        await websocket.send_json(ResponseFrame(id=req.id, ok=True, payload=schema).model_dump())

                    elif method == "sessions.list":
                        agent_id = req.params.get("agentId", "main") if req.params else "main"
                        sessions_data = []
                        
                        # We check two possible locations for sessions:
                        # 1. New Python structure: agents/<agent_id>/agent/sessions/<session_id>/
                        # 2. Legacy/Alternative structure: agents/<agent_id>/sessions/
                        
                        search_paths = [
                            settings.config_root / "agents" / agent_id / "agent" / "sessions",
                            settings.config_root / "agents" / agent_id / "sessions"
                        ]
                        
                        seen_keys = set()
                        
                        for base_path in search_paths:
                            if not base_path.exists():
                                continue
                                
                            # If sessions.json exists in this folder, use it as a legacy registry
                            registry_file = base_path / "sessions.json"
                            if registry_file.exists():
                                try:
                                    with open(registry_file, "r", encoding="utf-8") as f:
                                        raw_sessions = json.load(f)
                                        for key, entry in raw_sessions.items():
                                            if key not in seen_keys:
                                                if isinstance(entry, dict):
                                                    entry["key"] = str(entry.get("key", key))
                                                    entry["sessionId"] = str(entry.get("sessionId", key))
                                                    entry["label"] = str(entry.get("label", entry["sessionId"]))
                                                    entry["updatedAt"] = int(entry.get("updatedAt", int(time.time() * 1000)))
                                                    entry["model"] = str(entry.get("model", "main"))
                                                    entry["modelProvider"] = str(entry.get("modelProvider", "ollama"))
                                                    sessions_data.append(entry)
                                                else:
                                                    sessions_data.append({
                                                        "key": key,
                                                        "sessionId": key,
                                                        "label": key,
                                                        "updatedAt": int(time.time() * 1000),
                                                        "model": "main",
                                                        "modelProvider": "ollama"
                                                    })
                                                seen_keys.add(key)
                                except:
                                    pass
                                    
                            # Also scan directory for session folders (Python structure)
                            # Each folder name is a session key
                            if base_path.is_dir():
                                for item in base_path.iterdir():
                                    if item.is_dir() and item.name not in seen_keys:
                                        # Basic entry for the folder
                                        sessions_data.append({
                                            "key": item.name,
                                            "sessionId": item.name,
                                            "label": item.name,
                                            "updatedAt": int(item.stat().st_mtime * 1000),
                                            "model": "main",
                                            "modelProvider": "ollama"
                                        })
                                        seen_keys.add(item.name)
                                        
                        await websocket.send_json(ResponseFrame(id=req.id, ok=True, payload={"sessions": sessions_data}).model_dump())

                    elif method == "skills.status":
                        from autocrab.core.models.gateway import SkillStatusReport, SkillStatusEntry
                        from autocrab.core.plugins.loader import get_registered_schemas, get_markdown_skills
                        
                        agent_id = req.params.get("agentId", "main") if req.params else "main"
                        workspace_dir = settings.config_root / "workspace"
                        if agent_id != "main":
                             workspace_dir = settings.config_root / f"workspace-{agent_id}"
                             
                        schemas = get_registered_schemas()
                        skills_status = []
                        
                        for schema in schemas:
                            func = schema.function
                            skills_status.append(SkillStatusEntry(
                                name=func.name,
                                description=func.description,
                                source="python-plugin",
                                bundled=False,
                                filePath="dynamic",
                                baseDir=str(settings.config_root),
                                skillKey=func.name,
                                eligible=True,
                                requirements={},
                                missing={}
                            ))
                            
                        # Add Markdown skills
                        for s in get_markdown_skills():
                            skills_status.append(SkillStatusEntry(
                                name=s.name,
                                description=s.description,
                                source="autocrab-skill",
                                bundled=False,
                                filePath=s.filePath,
                                baseDir=s.baseDir,
                                skillKey=s.metadata.skillKey if s.metadata and s.metadata.skillKey else s.name,
                                emoji=s.metadata.emoji if s.metadata else None,
                                homepage=s.metadata.homepage if s.metadata else None,
                                primaryEnv=s.metadata.primaryEnv if s.metadata else None,
                                eligible=True,
                                requirements=s.metadata.requires if s.metadata else {},
                                missing={}
                            ))
                            
                        report = SkillStatusReport(
                            workspaceDir=str(workspace_dir),
                            managedSkillsDir=str(settings.config_root / "skills"),
                            skills=skills_status
                        )
                        await websocket.send_json(ResponseFrame(id=req.id, ok=True, payload=report.model_dump()).model_dump())

                    elif method == "skills.bins":
                        # Return empty bins for now to satisfy UI
                        await websocket.send_json(ResponseFrame(id=req.id, ok=True, payload={"bins": []}).model_dump())

                    elif method == "skills.install":
                        # Stub install success
                        await websocket.send_json(ResponseFrame(id=req.id, ok=True, payload={"ok": True, "message": "Skill installed (stub)"}).model_dump())

                    elif method == "channels.status":
                        from autocrab.core.models.gateway import ChannelStatusEntry, ChannelsStatusResult
                        from autocrab.core.plugins.loader import get_channel_plugins

                        channels_data = []
                        plugins = get_channel_plugins()

                        for p_id, plugin in plugins.items():
                            is_connected = False
                            status_text = "disconnected"
                            
                            # Inspect the plugin instance for status details if available
                            if hasattr(plugin, "client") and plugin.client:
                                try:
                                    if hasattr(plugin.client, "is_ready") and callable(plugin.client.is_ready) and plugin.client.is_ready():
                                        is_connected = True
                                        status_text = "connected"
                                except:
                                    pass
                            # Check for generic connected property
                            elif hasattr(plugin, "connected"):
                                is_connected = bool(plugin.connected)
                                status_text = "connected" if is_connected else "disconnected"

                            account_val = None
                            if hasattr(plugin, "account"):
                                account_val = str(plugin.account)
                                
                            channels_data.append(ChannelStatusEntry(
                                id=plugin.id,
                                name=plugin.id.capitalize(),
                                status=status_text,
                                connected=is_connected,
                                version=plugin.version,
                                account=account_val
                            ))
                            
                        result = ChannelsStatusResult(channels=channels_data)
                        await websocket.send_json(ResponseFrame(id=req.id, ok=True, payload=result.model_dump()).model_dump())

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

                    elif method == "exec.approvals.get":
                        approvals_path = settings.config_root / "exec-approvals.json"
                        exists = approvals_path.exists()
                        hash_val = "none"
                        file_data = {"version": 1, "socket": {}, "defaults": {}, "agents": {}}
                        
                        if exists:
                            try:
                                with open(approvals_path, "r") as f:
                                    raw = f.read()
                                    file_data = json.loads(raw)
                                    hash_val = hashlib.sha256(raw.encode()).hexdigest()
                            except Exception as e:
                                print(f"WS Error reading approvals: {e}", flush=True)

                        try:
                            snapshot = ExecApprovalsSnapshot(
                                path=str(approvals_path),
                                exists=exists,
                                hash=hash_val,
                                file=ExecApprovalsFile(**file_data)
                            )
                            await websocket.send_json(ResponseFrame(id=req.id, ok=True, payload=snapshot.model_dump()).model_dump())
                        except Exception as e:
                            print(f"WS Error creating ExecApprovalsSnapshot: {e}", flush=True)
                            await websocket.send_json(ResponseFrame(id=req.id, ok=False, error=ErrorShape(code="internal", message=str(e))).model_dump())

                    elif method == "exec.approvals.set":
                        params = req.params or {}
                        new_file_data = params.get("file")
                        
                        approvals_path = settings.config_root / "exec-approvals.json"
                        
                        try:
                            # Ensure directory exists
                            os.makedirs(approvals_path.parent, exist_ok=True)
                            with open(approvals_path, "w") as f:
                                json.dump(new_file_data, f, indent=2)
                            
                            with open(approvals_path, "r") as f:
                                raw = f.read()
                                hash_val = hashlib.sha256(raw.encode()).hexdigest()

                            snapshot = ExecApprovalsSnapshot(
                                path=str(approvals_path),
                                exists=True,
                                hash=hash_val,
                                file=ExecApprovalsFile(**new_file_data)
                            )
                            await websocket.send_json(ResponseFrame(id=req.id, ok=True, payload=snapshot.model_dump()).model_dump())
                        except Exception as e:
                            print(f"WS Error saving approvals: {e}", flush=True)
                            await websocket.send_json(ResponseFrame(
                                id=req.id, ok=False, 
                                error=ErrorShape(code="save_failed", message=str(e))
                            ).model_dump())

                    elif method == "agents.files.list":
                        agent_id = req.params.get("agentId", "main") if req.params else "main"
                        workspace_dir = None
                        if settings.agents and settings.agents.list:
                            for ac in settings.agents.list:
                                if ac.id == agent_id:
                                    if ac.workspace:
                                        workspace_dir = Path(ac.workspace)
                                    break
                        if not workspace_dir:
                            if agent_id == "main" or agent_id == "default":
                                workspace_dir = settings.config_root / "workspace"
                            else:
                                workspace_dir = settings.config_root / f"workspace-{agent_id}"
                        
                        files = []
                        if workspace_dir.exists():
                            for f in workspace_dir.iterdir():
                                if f.is_file():
                                    files.append(AgentFileEntry(
                                        name=f.name,
                                        path=str(f),
                                        missing=False,
                                        size=f.stat().st_size,
                                        updatedAtMs=int(f.stat().st_mtime * 1000)
                                    ))
                        
                        payload = AgentsFilesListResult(
                            agentId=agent_id,
                            workspace=str(workspace_dir),
                            files=files
                        )
                        await websocket.send_json(ResponseFrame(id=req.id, ok=True, payload=payload.model_dump()).model_dump())

                    elif method == "agents.files.get":
                        params = req.params or {}
                        agent_id = params.get("agentId", "main")
                        filename = params.get("name")
                        
                        workspace_dir = None
                        if settings.agents and settings.agents.list:
                            for ac in settings.agents.list:
                                if ac.id == agent_id:
                                    if ac.workspace:
                                        workspace_dir = Path(ac.workspace)
                                    break
                        if not workspace_dir:
                            if agent_id == "main" or agent_id == "default":
                                workspace_dir = settings.config_root / "workspace"
                            else:
                                workspace_dir = settings.config_root / f"workspace-{agent_id}"
                        
                        f_path = workspace_dir / filename
                        if f_path.exists() and f_path.is_file():
                            content = f_path.read_text(encoding="utf-8")
                            payload = AgentsFilesGetResult(
                                agentId=agent_id,
                                workspace=str(workspace_dir),
                                file=AgentFileEntry(
                                    name=filename,
                                    path=str(f_path),
                                    missing=False,
                                    size=f_path.stat().st_size,
                                    updatedAtMs=int(f_path.stat().st_mtime * 1000),
                                    content=content
                                )
                            )
                            await websocket.send_json(ResponseFrame(id=req.id, ok=True, payload=payload.model_dump()).model_dump())
                        else:
                            await websocket.send_json(ResponseFrame(id=req.id, ok=False, error=ErrorShape(code="not_found", message="File not found")).model_dump())

                    elif method == "agents.files.set":
                        params = req.params or {}
                        agent_id = params.get("agentId", "main")
                        filename = params.get("name")
                        content = params.get("content", "")
                        
                        workspace_dir = None
                        if settings.agents and settings.agents.list:
                            for ac in settings.agents.list:
                                if ac.id == agent_id:
                                    if ac.workspace:
                                        workspace_dir = Path(ac.workspace)
                                    break
                        if not workspace_dir:
                            if agent_id == "main" or agent_id == "default":
                                workspace_dir = settings.config_root / "workspace"
                            else:
                                workspace_dir = settings.config_root / f"workspace-{agent_id}"
                        
                        f_path = workspace_dir / filename
                        workspace_dir.mkdir(parents=True, exist_ok=True)
                        f_path.write_text(content, encoding="utf-8")
                        
                        payload = AgentsFilesSetResult(
                            agentId=agent_id,
                            workspace=str(workspace_dir),
                            file=AgentFileEntry(
                                name=filename,
                                path=str(f_path),
                                missing=False,
                                size=len(content),
                                updatedAtMs=int(time.time() * 1000),
                                content=content
                            )
                        )
                        await websocket.send_json(ResponseFrame(id=req.id, ok=True, payload=payload.model_dump()).model_dump())

                    elif method == "cron.runs":
                        from autocrab.core.models.gateway import CronRunsResult, CronRunLogEntry
                        # Stub response with empty list
                        params = req.params or {}
                        limit = params.get("limit", 50)
                        
                        runs_result = CronRunsResult(
                            entries=[], # No runs yet
                            total=0,
                            limit=limit,
                            offset=0,
                            hasMore=False
                        )
                        await websocket.send_json(ResponseFrame(id=req.id, ok=True, payload=runs_result.model_dump()).model_dump())

                    elif method == "cron.list":
                        from autocrab.core.models.gateway import CronJobsListResult
                        # Stub response with empty list
                        params = req.params or {}
                        limit = params.get("limit", 50)
                        
                        jobs_result = CronJobsListResult(
                            jobs=[], # No jobs yet
                            total=0,
                            limit=limit,
                            offset=0,
                            hasMore=False
                        )
                        await websocket.send_json(ResponseFrame(id=req.id, ok=True, payload=jobs_result.model_dump()).model_dump())

                    elif method == "cron.status":
                        from autocrab.core.models.gateway import CronStatus
                        
                        # Stub response assuming cron engine is not yet active/configured
                        status = CronStatus(
                            enabled=False,
                            jobs=0,
                            nextWakeAtMs=None
                        )
                        await websocket.send_json(ResponseFrame(id=req.id, ok=True, payload=status.model_dump()).model_dump())

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

                    elif method == "status":
                        status_summary = {
                            "version": app.version,
                            "mode": "standalone",
                            "status": "ok",
                            "uptimeMs": int((time.time() - START_TIME) * 1000),
                            "clients": len(presence_store),
                            "memory": {} 
                        }
                        await websocket.send_json(ResponseFrame(id=req.id, ok=True, payload=status_summary).model_dump())

                    elif method == "health":
                        health_snapshot = {
                            "status": "ok",
                            "ready": True,
                            "db": "connected", 
                            "checks": []
                        }
                        await websocket.send_json(ResponseFrame(id=req.id, ok=True, payload=health_snapshot).model_dump())

                    elif method == "last-heartbeat":
                        hb = {
                            "ts": int(time.time() * 1000),
                            "ok": True
                        }
                        await websocket.send_json(ResponseFrame(id=req.id, ok=True, payload=hb).model_dump())

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
            if not isinstance(e, WebSocketDisconnect):
                print(f"WS Error from {conn_id}: {str(e)}", flush=True)
        finally:
            # Clean up presence strictly on disconnect
            if conn_id in presence_store:
                print(f"WS: Cleaning up presence for {conn_id}", flush=True)
                del presence_store[conn_id]
            print(f"WS: Connection closed for {conn_id}", flush=True)

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
            
        print(f"Serving UI from {ui_path} via catch-all route", flush=True)
    else:
        print(f"Warning: UI path {ui_path} not found. Static serving disabled.", flush=True)

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
        print("Starting ecosystem channel plugins...", flush=True)
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
