import uvicorn
import os
import asyncio
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

# ---------------------------------------------------------------------------
# Cron store — reads/writes ~/.autocrab_v2/cron/jobs.json
# ---------------------------------------------------------------------------

_CRON_DIR = Path.home() / ".autocrab_v2" / "cron"
_CRON_JOBS_FILE = _CRON_DIR / "jobs.json"
_CRON_RUNS_DIR = _CRON_DIR / "runs"


def _cron_load_jobs() -> list:
    """Load jobs from disk; return [] if file absent or broken."""
    try:
        raw = _CRON_JOBS_FILE.read_text(encoding="utf-8")
        data = json.loads(raw)
        return data.get("jobs", [])
    except Exception:
        return []


def _cron_save_jobs(jobs: list) -> None:
    """Persist jobs list to disk atomically."""
    _CRON_DIR.mkdir(parents=True, exist_ok=True)
    tmp = _CRON_JOBS_FILE.with_suffix(".json.tmp")
    tmp.write_text(
        json.dumps({"version": 1, "jobs": jobs}, indent=2), encoding="utf-8"
    )
    tmp.replace(_CRON_JOBS_FILE)


def _cron_load_runs(job_id: str | None = None, limit: int = 50, offset: int = 0) -> list:
    """
    Load run-log entries from JSONL files.
    If job_id is given, restrict to that job's file; otherwise aggregate all.
    Returns entries sorted newest-first, sliced by offset/limit.
    """
    _CRON_RUNS_DIR.mkdir(parents=True, exist_ok=True)
    entries = []
    if job_id:
        files = [_CRON_RUNS_DIR / f"{job_id}.jsonl"]
    else:
        files = sorted(_CRON_RUNS_DIR.glob("*.jsonl"))
    for f in files:
        if not f.exists():
            continue
        try:
            for line in f.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except Exception:
                        pass
        except Exception:
            pass
    # Sort newest first
    entries.sort(key=lambda e: e.get("ts", 0), reverse=True)
    return entries[offset : offset + limit], len(entries)


def _cron_compute_next_run(schedule: dict, now_ms: int) -> int | None:
    """Compute the next run timestamp (ms) from a schedule dict relative to now."""
    kind = schedule.get("kind")
    if kind == "every":
        every_ms = schedule.get("everyMs", 0)
        anchor_ms = schedule.get("anchorMs", now_ms)
        if every_ms <= 0:
            return None
        if anchor_ms >= now_ms:
            return anchor_ms
        elapsed = now_ms - anchor_ms
        periods = elapsed // every_ms
        return anchor_ms + (periods + 1) * every_ms
    # For unknown schedule kinds fall back to stored nextRunAtMs
    return None


def _cron_next_run_at(job: dict, now_ms: int | None = None) -> int | None:
    """Return the next run time for a job, recomputed from the schedule if possible."""
    if now_ms is None:
        now_ms = int(time.time() * 1000)
    schedule = job.get("schedule") or {}
    computed = _cron_compute_next_run(schedule, now_ms)
    if computed is not None:
        return computed
    state = job.get("state") or {}
    return state.get("nextRunAtMs")


def _cron_enrich_job(job: dict, now_ms: int) -> dict:
    """Return a shallow copy of job with state.nextRunAtMs recomputed."""
    import copy
    j = copy.deepcopy(job)
    nxt = _cron_next_run_at(j, now_ms)
    if nxt is not None:
        if "state" not in j or j["state"] is None:
            j["state"] = {}
        j["state"]["nextRunAtMs"] = nxt
    return j


def _cron_status_from_jobs(jobs: list) -> dict:
    """Derive CronStatus fields from the jobs list."""
    now_ms = int(time.time() * 1000)
    enabled_jobs = [j for j in jobs if j.get("enabled", False)]
    next_run = None
    for j in enabled_jobs:
        nxt = _cron_next_run_at(j, now_ms)
        if nxt and (next_run is None or nxt < next_run):
            next_run = nxt
    return {
        "enabled": len(enabled_jobs) > 0,
        "jobs": len(jobs),
        "nextWakeAtMs": next_run,
    }


# ---------------------------------------------------------------------------
# Cron scheduler — background asyncio loop that fires due jobs
# ---------------------------------------------------------------------------

_CRON_MAX_SLEEP_S = 60.0          # re-check at least every 60 s
_CRON_MIN_REFIRE_GAP_MS = 2_000   # min gap between runs of the same job
_CRON_STUCK_RUN_MS = 10 * 60_000  # clear runningAtMs markers older than 10 min
_cron_scheduler_task: "asyncio.Task | None" = None


def _cron_apply_outcome(job: dict, status: str, error: str | None,
                        summary: str | None, started_at_ms: int, ended_at_ms: int) -> None:
    """Update job state after a run and rewrite nextRunAtMs."""
    if "state" not in job or job["state"] is None:
        job["state"] = {}
    st = job["state"]
    st["runningAtMs"] = None
    st["lastRunAtMs"] = started_at_ms
    st["lastRunStatus"] = status
    st["lastStatus"] = status
    st["lastDurationMs"] = ended_at_ms - started_at_ms
    st["lastDeliveryStatus"] = "not-requested"
    if status == "error":
        st["consecutiveErrors"] = (st.get("consecutiveErrors") or 0) + 1
        st["lastError"] = error
    else:
        st["consecutiveErrors"] = 0
        st.pop("lastError", None)
    # Recompute next run
    now_ms = int(time.time() * 1000)
    nxt = _cron_next_run_at(job, now_ms)
    if nxt is not None:
        st["nextRunAtMs"] = nxt


def _cron_write_run_log(job: dict, status: str, error: str | None,
                        summary: str | None, started_at_ms: int, ended_at_ms: int) -> None:
    """Append a finished-run entry to the per-job JSONL run log."""
    job_id = job.get("id", "")
    _CRON_RUNS_DIR.mkdir(parents=True, exist_ok=True)
    now_ms = int(time.time() * 1000)
    entry = {
        "ts": now_ms,
        "jobId": job_id,
        "action": "finished",
        "status": status,
        "summary": summary,
        "deliveryStatus": "not-requested",
        "runAtMs": started_at_ms,
        "durationMs": ended_at_ms - started_at_ms,
        "nextRunAtMs": (job.get("state") or {}).get("nextRunAtMs"),
    }
    if error:
        entry["error"] = error
    run_file = _CRON_RUNS_DIR / f"{job_id}.jsonl"
    with run_file.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry) + "\n")


async def _cron_execute_job(job: dict) -> tuple[str, str | None, str | None]:
    """
    Execute one cron job.  Returns (status, error, summary).
    - status: "ok" | "error" | "skipped"
    - error:   error message if status=="error"
    - summary: last agent text if available
    """
    import copy
    from langchain_core.messages import HumanMessage as HM

    payload = job.get("payload") or {}
    kind = payload.get("kind", "systemEvent")
    text = payload.get("text", "")

    if not text:
        return "skipped", None, "no payload text"

    agent_id = job.get("agentId", "main")
    session_key = job.get("sessionKey") or f"agent:{agent_id}:main"
    session_target = job.get("sessionTarget", "main")

    # For isolated target, create a unique per-run session key
    if session_target == "isolated":
        run_id = uuid.uuid4().hex[:8]
        effective_session_key = f"{session_key}:cron:{job.get('id','unknown')}:run:{run_id}"
    else:
        effective_session_key = session_key

    try:
        initial_state = {
            "messages": [HM(content=text)],
            "session_id": effective_session_key,
            "agent_id": agent_id,
            "context": "",
            "instructions": None,
            "tool_choice": None,
        }
        final_state = await agent_executor.ainvoke(initial_state)
        last_msg = final_state["messages"][-1]
        summary = str(last_msg.content)[:500] if last_msg else None
        return "ok", None, summary
    except Exception as exc:
        return "error", str(exc), None


async def _cron_scheduler_loop() -> None:
    """
    Background loop: wake at the next due time, run all due jobs, persist, sleep.
    Mirrors the behaviour of armTimer/onTimer in src/cron/service/timer.ts.
    """
    print("CronScheduler: started", flush=True)
    running_job_ids: set = set()  # guard against concurrent runs of same job

    while True:
        try:
            now_ms = int(time.time() * 1000)
            jobs = _cron_load_jobs()

            # --- clear stuck running markers ---
            changed_stuck = False
            for j in jobs:
                st = j.get("state") or {}
                rm = st.get("runningAtMs")
                if isinstance(rm, int) and now_ms - rm > _CRON_STUCK_RUN_MS:
                    st["runningAtMs"] = None
                    j["state"] = st
                    changed_stuck = True
            if changed_stuck:
                _cron_save_jobs(jobs)

            # --- find due jobs ---
            due = [
                j for j in jobs
                if j.get("enabled", False)
                and j.get("id") not in running_job_ids
                and (j.get("state") or {}).get("runningAtMs") is None
                and isinstance((j.get("state") or {}).get("nextRunAtMs"), int)
                and (j.get("state") or {})["nextRunAtMs"] <= now_ms
            ]

            if due:
                # Mark all as running immediately and persist
                now_ms2 = int(time.time() * 1000)
                for j in due:
                    if "state" not in j or j["state"] is None:
                        j["state"] = {}
                    j["state"]["runningAtMs"] = now_ms2
                    running_job_ids.add(j["id"])
                _cron_save_jobs(jobs)

                # Execute each due job (sequentially — matches default concurrency=1)
                for j in due:
                    job_name = j.get("name", j.get("id", "?"))
                    print(f"CronScheduler: running job '{job_name}'", flush=True)
                    started_at = int(time.time() * 1000)
                    status, error, summary = await _cron_execute_job(j)
                    ended_at = int(time.time() * 1000)
                    print(
                        f"CronScheduler: job '{job_name}' finished "
                        f"status={status} duration={ended_at - started_at}ms",
                        flush=True,
                    )

                    # Reload to pick up any external changes, then apply outcome
                    jobs = _cron_load_jobs()
                    for stored in jobs:
                        if stored.get("id") == j.get("id"):
                            _cron_apply_outcome(stored, status, error, summary, started_at, ended_at)
                            _cron_write_run_log(stored, status, error, summary, started_at, ended_at)
                            break

                    running_job_ids.discard(j.get("id"))

                _cron_save_jobs(jobs)

            # --- compute sleep until next wake ---
            jobs = _cron_load_jobs()
            now_ms3 = int(time.time() * 1000)
            next_wake = None
            for j in jobs:
                if not j.get("enabled", False):
                    continue
                nxt = _cron_next_run_at(j, now_ms3)
                if nxt and (next_wake is None or nxt < next_wake):
                    next_wake = nxt

            if next_wake:
                sleep_s = max(0.5, min((next_wake - now_ms3) / 1000.0, _CRON_MAX_SLEEP_S))
            else:
                sleep_s = _CRON_MAX_SLEEP_S

            await asyncio.sleep(sleep_s)

        except asyncio.CancelledError:
            print("CronScheduler: cancelled", flush=True)
            break
        except Exception as exc:
            print(f"CronScheduler: error in loop: {exc}", flush=True)
            await asyncio.sleep(10)  # back-off on unexpected errors

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
                                    "config.get", "config.schema", "config.set", "config.apply",
                                    "sessions.list", "sessions.delete", "sessions.patch",
                                    "sessions.usage", "sessions.usage.logs", "sessions.usage.timeseries",
                                    "skills.status", "skills.bins", "skills.install", "skills.update",
                                    "channels.status", "channels.logout",
                                    "cron.runs", "cron.list", "cron.status",
                                    "cron.add", "cron.remove", "cron.run", "cron.update",
                                    "agents.list", "models.list", "tools.catalog", "ping",
                                    "status", "health", "last-heartbeat", "logs.tail",
                                    "exec.approvals.get", "exec.approvals.set",
                                    "agents.files.list", "agents.files.get", "agents.files.set",
                                    "agent.identity.get",
                                    "device.pair.approve", "device.pair.reject", "device.token.revoke",
                                    "node.list",
                                    "update.run", "usage.cost", "whatsapp",
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
                        
                        # runId should be the idempotencyKey or a generated UUID for this distinct run
                        client_run_id = params.get("idempotencyKey", params.get("runId", str(uuid.uuid4())))
                        
                        # Persistence: Record Human message
                        store = HybridMemoryStore(session_id=session_key, agent_id=agent_id)
                        await store.add_interaction("human", content)
                        
                        # 0. Acknowledge the original request as STARTED (Parity with Node.js)
                        await websocket.send_json(ResponseFrame(
                            id=req.id, 
                            ok=True, 
                            payload={"runId": client_run_id, "status": "started"}
                        ).model_dump())
                        
                        # Start streaming response
                        initial_state = {
                            "messages": [HumanMessage(content=content)],
                            "session_id": session_key,
                            "agent_id": agent_id,
                            "context": "",
                            "instructions": params.get("instructions"),
                            "tool_choice": params.get("tool_choice")
                        }
                        
                        print(f"WS: Starting astream_events for session_key={session_key} (run={client_run_id}, conn={session_id})", flush=True)
                        seq = 0
                        try:
                            # Use agent_executor from module import. 
                            # If using a multi-agent system, we'd look up the specific executor here.
                            async for event_data in agent_executor.astream_events(initial_state, version="v2"):
                                kind = event_data["event"]
                                seq += 1
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
                                                    "runId": client_run_id,
                                                    "sessionKey": session_key,
                                                    "seq": seq,
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
                                            "runId": client_run_id,
                                            "sessionKey": session_key,
                                            "seq": seq,
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
                                            "runId": client_run_id,
                                            "sessionKey": session_key,
                                            "seq": seq,
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
                        seq += 1
                        final_event = {
                            "type": "event",
                            "event": "chat",
                            "payload": {
                                "runId": client_run_id,
                                "sessionKey": session_key,
                                "seq": seq,
                                "state": "final",
                                "message": {
                                    "role": "assistant",
                                    "text": full_ai_response,
                                    "content": [{"type": "text", "text": full_ai_response}],
                                    "timestamp": int(time.time() * 1000),
                                    "usage": {"input": 0, "output": 0, "totalTokens": 0} # Stub usage
                                }
                            }
                        }
                        await websocket.send_json(final_event)
                        print(f"WS: Sent final event for chat.send {client_run_id}", flush=True)

                        # Note: Node.js version doesn't send another ResponseFrame here 
                        # because we already acknowledged it at the start.
                        # However, for robustness if the UI expects it specifically after 'final', we keep it.
                        # But wait, sending twice with same ID might be bad protocol. 
                        # Actually, Node.js 'respond' marks it done.
                        # Let's see if the UI needs it. The user said line 707 was called and didn't stop.
                        # That means we ALREADY send it. The issue was the 'final' event missing the message.

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
                        # Use Pydantic's real JSON schema for the settings model
                        from autocrab.core.models.config import AutoCrabSettings
                        schema = AutoCrabSettings.model_json_schema()
                        await websocket.send_json(ResponseFrame(id=req.id, ok=True, payload=schema).model_dump())

                    elif method == "config.set":
                        new_config = (req.params or {}).get("config", req.params or {})
                        config_path = settings.config_root / "autocrab.json"
                        try:
                            config_path.parent.mkdir(parents=True, exist_ok=True)
                            with open(config_path, "w", encoding="utf-8") as f:
                                json.dump(new_config, f, indent=2)
                            await websocket.send_json(ResponseFrame(id=req.id, ok=True, payload={"saved": True}).model_dump())
                        except Exception as e:
                            await websocket.send_json(ResponseFrame(id=req.id, ok=False, error=ErrorShape(code="CONFIG_WRITE_ERROR", message=str(e))).model_dump())

                    elif method == "config.apply":
                        new_config = (req.params or {}).get("config", req.params or {})
                        config_path = settings.config_root / "autocrab.json"
                        try:
                            config_path.parent.mkdir(parents=True, exist_ok=True)
                            with open(config_path, "w", encoding="utf-8") as f:
                                json.dump(new_config, f, indent=2)
                            await websocket.send_json(ResponseFrame(id=req.id, ok=True, payload={"applied": True}).model_dump())
                        except Exception as e:
                            await websocket.send_json(ResponseFrame(id=req.id, ok=False, error=ErrorShape(code="CONFIG_WRITE_ERROR", message=str(e))).model_dump())

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
                                        
                        sessions_path = str(settings.config_root / "agents" / agent_id / "sessions")
                        await websocket.send_json(ResponseFrame(id=req.id, ok=True, payload={
                            "ts": int(time.time() * 1000),
                            "path": sessions_path,
                            "count": len(sessions_data),
                            "defaults": {"model": None, "contextTokens": None},
                            "sessions": sessions_data,
                        }).model_dump())

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

                    elif method == "logs.tail":
                        params = req.params or {}
                        cursor = params.get("cursor")
                        limit = params.get("limit", 100)
                        max_bytes = params.get("maxBytes", 50000)
                        
                        log_path = settings.config_root / "gateway.log"
                        if not log_path.exists():
                             log_path = Path("gateway.log") # Try CWD
                        
                        lines = []
                        new_cursor = 0
                        truncated = False
                        reset = False
                        file_size = 0
                        
                        if log_path.exists():
                            try:
                                file_size = log_path.stat().st_size
                                
                                # If cursor is beyond file size, reset (file rotated/truncated)
                                if cursor is not None and cursor > file_size:
                                    cursor = None
                                    reset = True

                                with open(log_path, "rb") as f:
                                    if cursor is None:
                                        # Default tail: read last N bytes if no cursor
                                        if file_size > max_bytes:
                                            f.seek(file_size - max_bytes)
                                            # Advance to next newline to avoid partial line at start
                                            f.readline() 
                                        else:
                                            f.seek(0)
                                    else:
                                        f.seek(cursor)
                                    
                                    start_pos = f.tell()
                                    chunk = f.read(max_bytes)
                                    
                                    if len(chunk) == max_bytes and b'\n' in chunk:
                                        last_nl = chunk.rfind(b'\n')
                                        if last_nl != -1:
                                            chunk = chunk[:last_nl+1]
                                            truncated = True
                                        
                                    new_cursor = start_pos + len(chunk)
                                    text = chunk.decode("utf-8", errors="replace")
                                    if text:
                                        lines = text.splitlines()
                            except Exception as e:
                                print(f"Log read error: {e}")

                        payload = {
                            "file": str(log_path),
                            "cursor": new_cursor,
                            "size": file_size,
                            "lines": lines,
                            "truncated": truncated,
                            "reset": reset
                        }
                        await websocket.send_json(ResponseFrame(id=req.id, ok=True, payload=payload).model_dump())

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
                        params = req.params or {}
                        limit = int(params.get("limit", 50))
                        offset = int(params.get("offset", 0))
                        job_id = params.get("jobId") or None
                        page, total = _cron_load_runs(job_id=job_id, limit=limit, offset=offset)
                        payload = {
                            "entries": page,
                            "total": total,
                            "limit": limit,
                            "offset": offset,
                            "hasMore": offset + len(page) < total,
                        }
                        await websocket.send_json(ResponseFrame(id=req.id, ok=True, payload=payload).model_dump())

                    elif method == "cron.list":
                        params = req.params or {}
                        limit = int(params.get("limit", 50))
                        offset = int(params.get("offset", 0))
                        all_jobs = _cron_load_jobs()
                        now_ms = int(time.time() * 1000)
                        enriched = [_cron_enrich_job(j, now_ms) for j in all_jobs]
                        page = enriched[offset : offset + limit]
                        payload = {
                            "jobs": page,
                            "total": len(all_jobs),
                            "limit": limit,
                            "offset": offset,
                            "hasMore": offset + len(page) < len(all_jobs),
                        }
                        await websocket.send_json(ResponseFrame(id=req.id, ok=True, payload=payload).model_dump())

                    elif method == "cron.status":
                        all_jobs = _cron_load_jobs()
                        status = _cron_status_from_jobs(all_jobs)
                        await websocket.send_json(ResponseFrame(id=req.id, ok=True, payload=status).model_dump())

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

                    elif method == "agent.identity.get":
                        agent_id = (req.params or {}).get("agentId", "main")
                        agent_name = agent_id
                        if settings.agents and settings.agents.list:
                            for ac in settings.agents.list:
                                if ac.id == agent_id and ac.name:
                                    agent_name = ac.name
                                    break
                        await websocket.send_json(ResponseFrame(id=req.id, ok=True, payload={
                            "agentId": agent_id,
                            "name": agent_name,
                            "version": app.version,
                        }).model_dump())

                    elif method == "channels.logout":
                        channel_id = (req.params or {}).get("channelId", "")
                        # Stub: real implementation would stop the channel plugin
                        await websocket.send_json(ResponseFrame(id=req.id, ok=True, payload={"channelId": channel_id, "loggedOut": True}).model_dump())

                    elif method == "cron.add":
                        params = req.params or {}
                        new_id = str(uuid.uuid4())
                        now_ms = int(time.time() * 1000)
                        job = {
                            "id": new_id,
                            "agentId": params.get("agentId", "main"),
                            "sessionKey": params.get("sessionKey", ""),
                            "name": params.get("name", "unnamed"),
                            "enabled": params.get("enabled", True),
                            "createdAtMs": now_ms,
                            "updatedAtMs": now_ms,
                            "schedule": params.get("schedule", {}),
                            "sessionTarget": params.get("sessionTarget", "main"),
                            "wakeMode": params.get("wakeMode", "now"),
                            "payload": params.get("payload", {}),
                            "delivery": params.get("delivery", {"mode": "none"}),
                            "state": params.get("state", {}),
                        }
                        jobs = _cron_load_jobs()
                        jobs.append(job)
                        _cron_save_jobs(jobs)
                        await websocket.send_json(ResponseFrame(id=req.id, ok=True, payload={"added": True, "jobId": new_id, "job": job}).model_dump())

                    elif method == "cron.remove":
                        params = req.params or {}
                        job_id = params.get("jobId", "")
                        jobs = _cron_load_jobs()
                        jobs = [j for j in jobs if j.get("id") != job_id]
                        _cron_save_jobs(jobs)
                        await websocket.send_json(ResponseFrame(id=req.id, ok=True, payload={"removed": True, "jobId": job_id}).model_dump())

                    elif method == "cron.run":
                        # Force-mark the job as due (set nextRunAtMs to now) then wake the scheduler
                        params = req.params or {}
                        job_id = params.get("jobId", "")
                        now_ms = int(time.time() * 1000)
                        jobs = _cron_load_jobs()
                        triggered = False
                        for j in jobs:
                            if j.get("id") == job_id:
                                if "state" not in j or j["state"] is None:
                                    j["state"] = {}
                                # Clear any running lock and force nextRunAtMs to now
                                j["state"]["runningAtMs"] = None
                                j["state"]["nextRunAtMs"] = now_ms
                                triggered = True
                                break
                        if triggered:
                            _cron_save_jobs(jobs)
                            # Wake the scheduler immediately if it's sleeping
                            if _cron_scheduler_task and not _cron_scheduler_task.done():
                                _cron_scheduler_task.cancel()
                                _cron_scheduler_task = asyncio.create_task(_cron_scheduler_loop())
                        await websocket.send_json(ResponseFrame(id=req.id, ok=True, payload={"triggered": triggered, "jobId": job_id}).model_dump())

                    elif method == "cron.update":
                        params = req.params or {}
                        job_id = params.get("jobId", "")
                        jobs = _cron_load_jobs()
                        updated = False
                        for j in jobs:
                            if j.get("id") == job_id:
                                # Apply allowed update fields
                                for field in ("name", "enabled", "schedule", "payload",
                                              "delivery", "sessionTarget", "wakeMode",
                                              "agentId", "sessionKey", "state"):
                                    if field in params:
                                        j[field] = params[field]
                                j["updatedAtMs"] = int(time.time() * 1000)
                                updated = True
                                break
                        if updated:
                            _cron_save_jobs(jobs)
                        await websocket.send_json(ResponseFrame(id=req.id, ok=True, payload={"updated": updated, "jobId": job_id}).model_dump())

                    elif method == "device.pair.approve":
                        await websocket.send_json(ResponseFrame(id=req.id, ok=True, payload={"approved": True}).model_dump())

                    elif method == "device.pair.reject":
                        await websocket.send_json(ResponseFrame(id=req.id, ok=True, payload={"rejected": True}).model_dump())

                    elif method == "device.token.revoke":
                        await websocket.send_json(ResponseFrame(id=req.id, ok=True, payload={"revoked": True}).model_dump())

                    elif method == "node.list":
                        import socket as _socket
                        await websocket.send_json(ResponseFrame(id=req.id, ok=True, payload={"nodes": [
                            {"id": "local", "name": _socket.gethostname(), "status": "online", "type": "local"}
                        ]}).model_dump())

                    elif method == "sessions.delete":
                        session_key = (req.params or {}).get("sessionKey", "")
                        await websocket.send_json(ResponseFrame(id=req.id, ok=True, payload={"deleted": True, "sessionKey": session_key}).model_dump())

                    elif method == "sessions.patch":
                        session_key = (req.params or {}).get("sessionKey", "")
                        await websocket.send_json(ResponseFrame(id=req.id, ok=True, payload={"updated": True, "sessionKey": session_key}).model_dump())

                    elif method == "sessions.usage":
                        params = req.params or {}
                        start_date = params.get("startDate", "")
                        end_date = params.get("endDate", "")
                        empty_totals = {
                            "input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0,
                            "totalTokens": 0, "totalCost": 0.0,
                            "inputCost": 0.0, "outputCost": 0.0,
                            "cacheReadCost": 0.0, "cacheWriteCost": 0.0,
                            "missingCostEntries": 0,
                        }
                        await websocket.send_json(ResponseFrame(id=req.id, ok=True, payload={
                            "updatedAt": int(time.time() * 1000),
                            "startDate": start_date,
                            "endDate": end_date,
                            "sessions": [],
                            "totals": empty_totals,
                            "aggregates": {
                                "messages": {
                                    "total": 0, "user": 0, "assistant": 0,
                                    "toolCalls": 0, "toolResults": 0, "errors": 0,
                                },
                                "tools": {
                                    "totalCalls": 0, "uniqueTools": 0, "tools": [],
                                },
                                "byModel": [],
                                "byProvider": [],
                                "byAgent": [],
                                "byChannel": [],
                                "daily": [],
                            },
                        }).model_dump())

                    elif method == "sessions.usage.logs":
                        await websocket.send_json(ResponseFrame(id=req.id, ok=True, payload={"logs": []}).model_dump())

                    elif method == "sessions.usage.timeseries":
                        await websocket.send_json(ResponseFrame(id=req.id, ok=True, payload={"series": []}).model_dump())

                    elif method == "skills.update":
                        skill_id = (req.params or {}).get("skillId", "")
                        await websocket.send_json(ResponseFrame(id=req.id, ok=True, payload={"skillId": skill_id, "updated": True}).model_dump())

                    elif method == "update.run":
                        await websocket.send_json(ResponseFrame(id=req.id, ok=True, payload={
                            "status": "unavailable",
                            "message": "Self-update not supported in the Python gateway"
                        }).model_dump())

                    elif method == "usage.cost":
                        empty_totals = {
                            "input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0,
                            "totalTokens": 0, "totalCost": 0.0,
                            "inputCost": 0.0, "outputCost": 0.0,
                            "cacheReadCost": 0.0, "cacheWriteCost": 0.0,
                            "missingCostEntries": 0,
                        }
                        await websocket.send_json(ResponseFrame(id=req.id, ok=True, payload={
                            "updatedAt": int(time.time() * 1000),
                            "days": 0,
                            "daily": [],
                            "totals": empty_totals,
                        }).model_dump())

                    elif method == "whatsapp":
                        # Route to WhatsApp channel plugin if registered, otherwise return stub
                        from autocrab.core.plugins.loader import get_channel_plugin
                        wa_plugin = get_channel_plugin("whatsapp")
                        if wa_plugin and hasattr(wa_plugin, "handle_rpc"):
                            result = await wa_plugin.handle_rpc(req.params or {})
                            await websocket.send_json(ResponseFrame(id=req.id, ok=True, payload=result).model_dump())
                        else:
                            await websocket.send_json(ResponseFrame(id=req.id, ok=True, payload={"channel": "whatsapp", "status": "not_configured"}).model_dump())

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
        global _cron_scheduler_task

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

        # Start cron scheduler — ensure nextRunAtMs values are up-to-date first
        jobs = _cron_load_jobs()
        now_ms = int(time.time() * 1000)
        enriched = [_cron_enrich_job(j, now_ms) for j in jobs]
        _cron_save_jobs(enriched)
        _cron_scheduler_task = asyncio.create_task(_cron_scheduler_loop())
        print("CronScheduler: task created", flush=True)

    @app.on_event("shutdown")
    async def shutdown_event():
        """Gracefully shuts down ecosystem plugins and cron scheduler."""
        global _cron_scheduler_task
        if _cron_scheduler_task and not _cron_scheduler_task.done():
            _cron_scheduler_task.cancel()
            try:
                await _cron_scheduler_task
            except Exception:
                pass
        from autocrab.core.plugins.loader import stop_all_channels
        await stop_all_channels()

    return app

# The default application instance
app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("AUTOCRAB_GATEWAY_PORT", 5174))
    uvicorn.run(app, host="0.0.0.0", port=port)
