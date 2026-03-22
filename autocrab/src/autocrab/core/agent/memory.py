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
        """Looks for specific context .md configuration files in the workspace directory."""
        if not self.workspace_dir or not self.workspace_dir.exists():
            return ""
            
        memories = []
        seen_tags = set()
        
        # We only load these explicit bootstrap configuration files to prevent
        # flooding the context and mimicking Node.js exact dynamic loading.
        target_files = [
            ("memory.md", "PERMANENT_MEMORY"),
            ("soul.md", "AGENT_SOUL"),
            ("user.md", "USER_PROFILE"),
            ("agents.md", "AGENTS"),
            ("tools.md", "TOOLS"),
            ("identity.md", "IDENTITY"),
            ("heartbeat.md", "HEARTBEAT"),
            ("bootstrap.md", "BOOTSTRAP")
        ]
        
        for file_name, tag in target_files:
            if tag in seen_tags:
                continue
                
            # Check lowercase and uppercase versions
            candidates = [self.workspace_dir / file_name, self.workspace_dir / file_name.upper()]
            
            for md_file in candidates:
                if md_file.exists() and md_file.is_file():
                    if md_file.stat().st_size > 50000:
                        break  # Skip this tag if file is too large
                        
                    try:
                        content = md_file.read_text(encoding="utf-8").strip()
                        if content:
                            memories.append(f"<{tag}>\n{content}\n</{tag}>\n\n")
                            seen_tags.add(tag)
                    except Exception as e:
                        logger.warning(f"Failed to read permanent memory at {md_file}: {e}")
                    break  # Don't load uppercase if lowercase was already found
                    
        return "".join(memories)

    async def add_interaction(self, role: str, content: str) -> None:
        """Records an interaction to both sinks."""
        # 1. Guarantee backward compatibility via flat-file stream
        self.writer.append_message(role, content)

        # 2. Opt-in Advanced Feature: Pushing to RAG
        if self.use_rag and self.rag_url:
            payload = {
                "session_id": self.session_id,
                "role": role,
                "content": content,
                "timestamp": int(time.time()),
            }
            try:
                async with httpx.AsyncClient() as client:
                    await client.post(f"{self.rag_url}/ingest", json=payload, timeout=2.0)
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
                async with httpx.AsyncClient() as client:
                    resp = await client.get(
                        f"{self.rag_url}/search", 
                        params={"session_id": self.session_id, "q": query}, 
                        timeout=2.0
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
