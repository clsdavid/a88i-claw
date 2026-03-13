import docker
import os
import uuid
from typing import Dict, Any, Tuple

class SandboxManager:
    """
    Manages isolated Docker containers for Agent Tool execution, replacing `setup-podman.sh`.
    Ensures safe, ephemeral execution of bash commands and python scripts.
    """
    def __init__(self, session_id: str, image_name: str = "ubuntu:22.04"):
        self.session_id = session_id
        self.image_name = image_name
        self.client = docker.from_env()
        self.container_id = None
        self.container = None
        
        # Workspace binding
        self.workspace_dir = f"/tmp/autocrab_workspaces/{self.session_id}"
        os.makedirs(self.workspace_dir, exist_ok=True)

    def start_sandbox(self):
        """Spins up the ephemeral container."""
        # Ensure image exists
        try:
            self.client.images.get(self.image_name)
        except docker.errors.ImageNotFound:
            print(f"Pulling sandbox image {self.image_name}...")
            self.client.images.pull(self.image_name)

        self.container = self.client.containers.run(
            self.image_name,
            command="tail -f /dev/null", # Keep alive
            detach=True,
            volumes={self.workspace_dir: {'bind': '/workspace', 'mode': 'rw'}},
            working_dir="/workspace",
            name=f"autocrab_sandbox_{self.session_id}_{uuid.uuid4().hex[:6]}",
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
