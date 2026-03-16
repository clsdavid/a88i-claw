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
    def __init__(self, session_id: str, agent_id: str = "default"):
        self.session_id = session_id
        self.agent_id = agent_id
        
        from autocrab.core.models.config import settings
        agent_dir_path = settings.config_root / "agents" / self.agent_id / "agent"
        if settings.agents and settings.agents.list:
            for ac in settings.agents.list:
                if ac.id == self.agent_id and ac.agentDir:
                    agent_dir_path = Path(ac.agentDir)
                    break
                    
        self.base_dir = agent_dir_path / "sessions" / self.session_id
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
        """Appends a new conversation block to the flat file and JSON log"""
        timestamp_str = time.strftime("%Y-%m-%d %H:%M:%S")
        ts_ms = int(time.time() * 1000)
        
        # 1. Markdown block
        block = f"## {role.capitalize()} ({timestamp_str})\n{content}\n\n"
        with open(self.transcript_path, "a", encoding="utf-8") as f:
            f.write(block)
            
        # 2. JSONL entry for chat.history
        import json
        entry = {
            "role": role,
            "content": content,
            "timestamp": ts_ms
        }
        with open(self.json_log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
            
    def load_messages(self) -> List[Dict[str, Any]]:
        """Reads back the structured JSONL history"""
        import json
        messages = []
        if self.json_log_path.exists():
            with open(self.json_log_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        try:
                            messages.append(json.loads(line))
                        except:
                            pass
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
        
        from autocrab.core.models.config import settings
        
        self.use_rag = settings.features.enable_external_rag
        self.rag_url = settings.features.rag_system_url
        
        # 1. Resolve Workspace Directory for Permanent Memory
        from pathlib import Path
        
        self.workspace_dir = None
        is_default = False
        if settings.agents and settings.agents.list:
            for ac in settings.agents.list:
                if ac.id == self.agent_id:
                    is_default = ac.default
                    if ac.workspace:
                        self.workspace_dir = Path(ac.workspace)
                    break
                    
        if not self.workspace_dir:
            # Fallback path logic
            if is_default or self.agent_id == "default":
                # Default agents use the global workspace in the config root
                self.workspace_dir = settings.config_root / "workspace"
            else:
                self.workspace_dir = settings.config_root / f"workspace-{self.agent_id}"
                
    def load_permanent_memory(self) -> str:
        """Looks for MEMORY.md and SOUL.md variants in the workspace directory."""
        if not self.workspace_dir:
            return ""
            
        search_configs = [
            {"filename": "MEMORY.md", "tag": "PERMANENT_MEMORY"},
            {"filename": "memory.md", "tag": "PERMANENT_MEMORY"},
            {"filename": "SOUL.md", "tag": "AGENT_SOUL"},
            {"filename": "soul.md", "tag": "AGENT_SOUL"},
            {"filename": "instructions/SOUL.md", "tag": "AGENT_SOUL"},
            {"filename": "instructions/soul.md", "tag": "AGENT_SOUL"},
            {"filename": "memory/MEMORY.md", "tag": "PERMANENT_MEMORY"},
            {"filename": "memory/memory.md", "tag": "PERMANENT_MEMORY"},
        ]
        
        memories = []
        seen_tags = set()
        
        for cfg in search_configs:
            # Skip if we already found a better variant for this tag (e.g. found SOUL.md, skip soul.md)
            if cfg["tag"] in seen_tags:
                continue
                
            mem_path = self.workspace_dir / cfg["filename"]
            if mem_path.exists():
                try:
                    content = mem_path.read_text(encoding="utf-8").strip()
                    if content:
                        memories.append(f"<{cfg['tag']}>\n{content}\n</{cfg['tag']}>\n\n")
                        seen_tags.add(cfg["tag"])
                except Exception as e:
                    print(f"Warning: Failed to read permanent memory at {mem_path}: {e}")
                    
        return "".join(memories)

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
        Prepend permanent memory, then appends local file chunks or RAG semantic search.
        """
        permanent_memory = self.load_permanent_memory()
        dynamic_memory = ""
        
        if self.use_rag and self.rag_url and query:
            try:
                async with httpx.AsyncClient() as client:
                    resp = await client.get(f"{self.rag_url}/search", params={"session_id": self.session_id, "q": query}, timeout=2.0)
                    if resp.status_code == 200:
                        data = resp.json()
                        dynamic_memory = "\\n".join([item["content"] for item in data.get("results", [])])
            except Exception:
                pass
        
        if not dynamic_memory:
            # Default flat-file read logic
            dynamic_memory = self.writer.load_context()
            
        return permanent_memory + dynamic_memory
