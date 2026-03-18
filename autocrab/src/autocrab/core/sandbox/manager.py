import docker
import os
import re
import uuid
from typing import Dict, Any, Tuple

class SandboxManager:
    """
    Manages isolated Docker containers for Agent Tool execution, replacing `setup-podman.sh`.
    Ensures safe, ephemeral execution of bash commands and python scripts.
    """
    def __init__(self, session_id: str, agent_id: str = "default", image_name: str = "ubuntu:22.04"):
        self.session_id = session_id
        self.agent_id = agent_id
        self.image_name = image_name
        self.client = docker.from_env()
        self.container_id = None
        self.container = None
        
        # Workspace binding reflecting Node.js path parity
        from autocrab.core.models.config import settings
        from pathlib import Path
        
        self.agent_workspace_dir = None
        self.workspace_access = "none"
        agent_dir_path_base = Path.home() / ".autocrab" / "agents" / self.agent_id / "agent"
        
        is_default = False
        if settings.agents and settings.agents.list:
            for ac in settings.agents.list:
                if ac.id == self.agent_id:
                    is_default = ac.default
                    if ac.agentDir:
                        agent_dir_path_base = Path(ac.agentDir)
                    if ac.workspace:
                        self.agent_workspace_dir = Path(ac.workspace)
                    if ac.sandbox and ac.sandbox.workspaceAccess:
                        self.workspace_access = ac.sandbox.workspaceAccess
                    break
                    
        if not self.agent_workspace_dir:
            # Fallback path logic matching the original JS resolver
            if is_default or self.agent_id == "default":
                self.agent_workspace_dir = Path(os.getcwd()) / "autocrab" / "workspace"
            else:
                self.agent_workspace_dir = Path.home() / ".autocrab" / f"workspace-{self.agent_id}"

        self.agent_workspace_dir.mkdir(parents=True, exist_ok=True)
        self.session_workspace_dir = agent_dir_path_base / "sessions" / self.session_id
        self.session_workspace_dir.mkdir(parents=True, exist_ok=True)

    def start_sandbox(self):
        """Spins up the ephemeral container."""
        # Ensure image exists
        try:
            self.client.images.get(self.image_name)
        except docker.errors.ImageNotFound:
            print(f"Pulling sandbox image {self.image_name}...")
            self.client.images.pull(self.image_name)

        volumes = {}
        # Emulating Node.js workspace mounts
        if self.workspace_access == "rw":
            volumes[str(self.agent_workspace_dir)] = {'bind': '/workspace', 'mode': 'rw'}
        else:
            volumes[str(self.session_workspace_dir)] = {'bind': '/workspace', 'mode': 'rw'}
            if self.workspace_access == "ro":
                volumes[str(self.agent_workspace_dir)] = {'bind': '/agent_workspace', 'mode': 'ro'}

        # Docker container names only allow [a-zA-Z0-9_.-]; strip colons,
        # spaces, and other illegal chars that session IDs may contain.
        safe_sid = re.sub(r"[^a-zA-Z0-9_.-]", "_", self.session_id)[:48]
        self.container = self.client.containers.run(
            self.image_name,
            command="tail -f /dev/null", # Keep alive
            detach=True,
            volumes=volumes,
            working_dir="/workspace",
            name=f"autocrab_sandbox_{safe_sid}_{uuid.uuid4().hex[:6]}",
            # Security limits matching original architecture
            mem_limit="512m",
            network_mode="bridge",
            remove=True # Auto clean up on exit
        )
        self.container_id = self.container.id
        return self.container_id

    def execute_command(self, command: str, timeout: int = 60) -> Tuple[int, str]:
        """
        Executes a command inside the running sandbox.
        Returns (exit_code, output_string)
        """
        if not self.container:
            raise RuntimeError("Sandbox not started. Call start_sandbox() first.")
            
        # Using docker-py exec_run
        exec_log = self.container.exec_run(
            cmd=["/bin/bash", "-c", command],
            workdir="/workspace"
        )
        
        exit_code = exec_log.exit_code
        output = exec_log.output.decode('utf-8')
        
        return exit_code, output

    def teardown(self):
        """Stops and removes the container."""
        if self.container:
            try:
                self.container.stop(timeout=1)
            except Exception:
                pass
            self.container = None
            self.container_id = None
