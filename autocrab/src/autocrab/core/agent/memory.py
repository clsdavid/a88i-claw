import os
import json
import time
import httpx
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

from pydantic import BaseModel

from autocrab.core.models.config import settings

logger = logging.getLogger(__name__)


def _resolve_agent_dir(agent_id: str) -> Path:
    """Helper to cleanly resolve agent directory from settings."""
    agent_dir_path = settings.config_root / "agents" / agent_id / "agent"
    if settings.agents and settings.agents.list:
        for ac in settings.agents.list:
            if ac.id == agent_id and getattr(ac, "agentDir", None):
                agent_dir_path = Path(ac.agentDir)
                break
    return agent_dir_path


def _resolve_workspace_dir(agent_id: str) -> Path:
    """Helper to cleanly resolve the persistent memory workspace directory."""
    is_default = (agent_id == "default" or agent_id == "main")
    if settings.agents and settings.agents.list:
        for ac in settings.agents.list:
            if ac.id == agent_id:
                is_default = getattr(ac, "default", is_default)
                if getattr(ac, "workspace", None):
                    return Path(ac.workspace)
                break

    if is_default:
        return settings.config_root / "workspace"
    else:
        return settings.config_root / f"workspace-{agent_id}"


class TranscriptWriter:
    """
    Handles writing agent session transcripts to local markdown/json files.
    This maintains 100% backward compatibility with the Node.js filesystem memory.
    """
    def __init__(self, session_id: str, agent_id: str = "default"):
        self.session_id = session_id
        self.agent_id = agent_id
        
        agent_dir_path = _resolve_agent_dir(self.agent_id)
                    
        self.base_dir = agent_dir_path / "sessions" / self.session_id
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.transcript_path = self.base_dir / "transcript.md"
        self.json_log_path = self.base_dir / "events.jsonl"
        self._ensure_files()

    def _ensure_files(self) -> None:
        if not self.transcript_path.exists():
            self.transcript_path.write_text(f"# Agent Session: {self.session_id}\n\n", encoding="utf-8")
        if not self.json_log_path.exists():
            self.json_log_path.touch()

    def append_message(self, role: str, content: str) -> None:
        """Appends a new conversation block to the flat file and JSON log"""
        timestamp_str = time.strftime("%Y-%m-%d %H:%M:%S")
        ts_ms = int(time.time() * 1000)
        
        # 1. Markdown block
        block = f"## {role.capitalize()} ({timestamp_str})\n{content}\n\n"
        with open(self.transcript_path, "a", encoding="utf-8") as f:
            f.write(block)
            
        # 2. JSONL entry for chat.history
        entry = {
            "role": role,
            "content": content,
            "timestamp": ts_ms
        }
        with open(self.json_log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
            
    def load_messages(self) -> List[Dict[str, Any]]:
        """Reads back the structured JSONL history"""
        messages = []
        if self.json_log_path.exists():
            with open(self.json_log_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        try:
                            messages.append(json.loads(line))
                        except json.JSONDecodeError as e:
                            logger.warning(f"Error decoding JSON transcript line: {e}")
        return messages

    def load_context(self) -> str:
        """Reads back the markdown transcript"""
        if self.transcript_path.exists():
            return self.transcript_path.read_text(encoding="utf-8")
        return ""


class HybridMemoryStore:
    """
    The Brain's memory engine.
    Always uses TranscriptWriter for local state.
    Optionally queries/indexes to an external RAG provider if ENABLE_EXTERNAL_RAG is true.
    """
    def __init__(self, session_id: str, agent_id: str = "default"):
        self.session_id = session_id
        self.agent_id = agent_id
        self.writer = TranscriptWriter(session_id, agent_id)
        
        self.use_rag = settings.features.enable_external_rag
        self.rag_url = getattr(settings.features, "rag_system_url", None)
        
        self.workspace_dir = _resolve_workspace_dir(self.agent_id)
                
    def load_permanent_memory(self) -> str:
        """Recursively loads all .md files from the workspace directory."""
        if not self.workspace_dir or not self.workspace_dir.exists():
            return ""
            
        memories = []
        
        # Legacy mapping for core configuration tags
        legacy_tags = {
            "soul.md": "AGENT_SOUL",
            "memory.md": "PERMANENT_MEMORY",
            "user.md": "USER_PROFILE",
            "agents.md": "AGENTS",
            "tools.md": "TOOLS",
            "identity.md": "IDENTITY",
            "heartbeat.md": "HEARTBEAT",
            "bootstrap.md": "BOOTSTRAP"
        }
        
        # Walk the workspace recursively and load all .md files
        for root, _, files in os.walk(self.workspace_dir):
            for file_name in files:
                if not file_name.lower().endswith(".md"):
                    continue
                    
                file_path = Path(root) / file_name
                try:
                    # Avoid extremely large files
                    if file_path.stat().st_size > 100000:
                        continue
                        
                    content = file_path.read_text(encoding="utf-8").strip()
                    if not content:
                        continue
                        
                    relative_path = file_path.relative_to(self.workspace_dir)
                    
                    # Check if it's a legacy core config file
                    legacy_tag = legacy_tags.get(file_name.lower())
                    if legacy_tag and root == str(self.workspace_dir):
                        memories.append(f"<{legacy_tag}>\n{content}\n</{legacy_tag}>\n\n")
                    else:
                        # Standard file injection similar to Node.js contextFiles
                        memories.append(f'<FILE path="{relative_path}">\n{content}\n</FILE>\n\n')
                        
                except Exception as e:
                    logger.warning(f"Failed to read memory file at {file_path}: {e}")
                    
        return "".join(memories)

    async def add_interaction(self, role: str, content: str) -> None:
        """Records an interaction to both sinks."""
        # 1. Guarantee backward compatibility via flat-file stream
        self.writer.append_message(role, content)

        # 2. Opt-in Advanced Feature: Pushing to RAG
        if self.use_rag and self.rag_url:
            payload = {
                "text": content,
                "doc_id": f"{self.session_id}_{int(time.time())}",
                "user_id": "autocrab",
                "background": False,
                "metadata": {
                    "role": role,
                    "session_id": self.session_id
                }
            }
            try:
                async with httpx.AsyncClient() as client:
                    await client.post(f"{self.rag_url}/api/v1/rag/ingest", json=payload, timeout=2.0)
            except Exception as e:
                logger.debug(f"Failed to ingest interaction to RAG: {e}")

    async def get_context(self, query: str = "") -> str:
        """
        Retrieves working context for the LLM. 
        Prepends permanent memory, then appends local file chunks or RAG semantic search.
        """
        permanent_memory = self.load_permanent_memory()
        dynamic_memory = ""
        
        if self.use_rag and self.rag_url and query:
            try:
                payload = {
                    "query": query,
                    "top_k": 5,
                    "user_id": "autocrab",
                    "session_id": self.session_id
                }
                async with httpx.AsyncClient() as client:
                    resp = await client.post(
                        f"{self.rag_url}/api/v1/rag/query", 
                        json=payload, 
                        timeout=5.0
                    )
                    resp.raise_for_status()
                    data = resp.json()
                    dynamic_memory = "\n".join([item.get("content", "") for item in data.get("results", [])])
            except httpx.HTTPError as e:
                logger.debug(f"Failed to search RAG system: {e}")
            except Exception as e:
                logger.debug(f"Unexpected error in RAG search: {e}")
        
        if not dynamic_memory:
            # Default flat-file read logic
            dynamic_memory = self.writer.load_context()
            
        return permanent_memory + dynamic_memory
