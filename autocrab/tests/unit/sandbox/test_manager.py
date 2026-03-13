import pytest
from unittest.mock import MagicMock, patch
from autocrab.core.sandbox.manager import SandboxManager

@pytest.fixture
def mock_docker_env():
    # Mock the entire docker.from_env() chain so tests run instantly without Docker daemon
    with patch('docker.from_env') as mock_from_env:
        mock_client = MagicMock()
        mock_from_env.return_value = mock_client
        
        # Mock the run container
        mock_container = MagicMock()
        mock_container.id = "mock_container_123"
        mock_client.containers.run.return_value = mock_container
        
        # Mock the exec_run
        mock_exec_result = MagicMock()
        mock_exec_result.exit_code = 0
        mock_exec_result.output = b"hello test workspace\\n"
        mock_container.exec_run.return_value = mock_exec_result
        
        yield mock_client, mock_container

def test_sandbox_start_and_teardown(mock_docker_env):
    mock_client, mock_container = mock_docker_env
    manager = SandboxManager(session_id="test_session_tools")
    
    # Test start
    cid = manager.start_sandbox()
    assert cid == "mock_container_123"
    assert manager.container is not None
    mock_client.containers.run.assert_called_once()
    
    # Test teardown
    manager.teardown()
    mock_container.stop.assert_called_once()
    assert manager.container is None

def test_sandbox_execute_bash(mock_docker_env):
    mock_client, mock_container = mock_docker_env
    manager = SandboxManager(session_id="test_session_tools")
    manager.start_sandbox()
    
    # Test executing a command
    code, output = manager.execute_command("echo 'hello test workspace'")
    
    assert code == 0
    assert "hello test workspace" in output
    mock_container.exec_run.assert_called_with(
        cmd=["/bin/bash", "-c", "echo 'hello test workspace'"],
        workdir="/workspace"
    )
