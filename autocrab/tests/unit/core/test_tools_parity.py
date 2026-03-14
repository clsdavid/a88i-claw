import pytest
from unittest.mock import patch, MagicMock
from autocrab.core.tools.fs import fs_read, fs_write, fs_list
from autocrab.core.tools.browser import browser_tool

@pytest.fixture
def mock_sandbox():
    with patch("autocrab.core.tools.fs.SandboxManager") as mock_fs_class, \
         patch("autocrab.core.tools.browser.SandboxManager") as mock_browser_class:
        
        mock_mgr = MagicMock()
        mock_fs_class.return_value = mock_mgr
        mock_browser_class.return_value = mock_mgr
        yield mock_mgr

def test_fs_read_success(mock_sandbox):
    mock_sandbox.execute_command.return_value = (0, "file content")
    
    result = fs_read.invoke({"path": "/tmp/test.txt"})
    
    assert result == "file content"
    mock_sandbox.execute_command.assert_called_with("cat '/tmp/test.txt'")

def test_fs_read_failure(mock_sandbox):
    mock_sandbox.execute_command.return_value = (1, "No such file")
    
    result = fs_read.invoke({"path": "/tmp/missing.txt"})
    
    assert result == "Error reading file /tmp/missing.txt: No such file"

def test_fs_write_success(mock_sandbox):
    mock_sandbox.execute_command.return_value = (0, "")
    
    result = fs_write.invoke({"path": "/tmp/out.txt", "content": "hello world"})
    
    assert result == "Successfully wrote to /tmp/out.txt"
    called_cmd = mock_sandbox.execute_command.call_args[0][0]
    assert "cat << 'EOF' > '/tmp/out.txt'" in called_cmd
    assert "hello world" in called_cmd

def test_fs_list_success(mock_sandbox):
    mock_sandbox.execute_command.return_value = (0, "file1.txt\nfile2.txt")
    
    result = fs_list.invoke({"path": "/tmp"})
    
    assert result == "file1.txt\nfile2.txt"
    mock_sandbox.execute_command.assert_called_with("ls -la '/tmp'")

def test_browser_goto(mock_sandbox):
    mock_sandbox.execute_command.return_value = (0, "<html>Mock Page</html>")
    
    result = browser_tool.invoke({"action": "goto", "url": "http://example.com"})
    
    assert "Successfully loaded http://example.com" in result
    assert "<html>Mock Page</html>" in result
    mock_sandbox.execute_command.assert_called_with("curl -sL http://example.com | head -n 50")

def test_browser_other_action(mock_sandbox):
    result = browser_tool.invoke({"action": "click", "selector": "#btn"})
    
    assert "Browser action 'click' executed successfully (Stub)." in result
