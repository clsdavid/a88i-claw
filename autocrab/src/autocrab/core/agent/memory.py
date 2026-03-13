import os
import httpx
import time
from pathlib import Path
from typing import Dict, Any, List
from autocrab.core.models.config import settings
from pydantic import BaseModel

class TranscriptWriter:
    """
    Handles writing agent session transcripts to local markdown/json files.
    This maintains 100% backward compatibility with the Node.js filesystem memory.
    """
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.base_dir = Path(settings.session_dir) / session_id
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.transcript_path = self.base_dir / "transcript.md"
        self.json_log_path = self.base_dir / "events.jsonl"
        self._ensure_files()

    def _ensure_files(self):
        if not self.transcript_path.exists():
            self.transcript_path.write_text(f"# Agent Session: {self.session_id}\n\n", encoding="utf-8")
        if not self.json_log_path.exists():
            self.json_log_path.touch()

    def append_message(self, role: str, content: str):
        """Appends a new conversation block to the flat file"""
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        block = f"## {role.capitalize()} ({timestamp})\n{content}\n\n"
        with open(self.transcript_path, "a", encoding="utf-8") as f:
            f.write(block)
            
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
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.writer = TranscriptWriter(session_id)
        self.use_rag = settings.features.enable_external_rag
        self.rag_url = settings.features.rag_system_url

    async def add_interaction(self, role: str, content: str):
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
                # Silently fail RAG ingestions to prevent breaking the ReAct loop
                pass

    async def get_context(self, query: str = "") -> str:
        """
        Retrieves working context for the LLM. 
        Defaults to local file chunks, but falls back to RAG semantic search if toggled.
        """
        if self.use_rag and self.rag_url and query:
            try:
                async with httpx.AsyncClient() as client:
                    resp = await client.get(f"{self.rag_url}/search", params={"session_id": self.session_id, "q": query}, timeout=2.0)
                    if resp.status_code == 200:
                        data = resp.json()
                        return "\\n".join([item["content"] for item in data.get("results", [])])
            except Exception:
                pass
        
        # Default flat-file read logic
        return self.writer.load_context()
