from typing import Optional, List, Dict, Any
from langchain_core.tools import tool
from pydantic import BaseModel, Field
from autocrab.core.sandbox.manager import SandboxManager

class ReadFileArgs(BaseModel):
    path: str = Field(description="The absolute or relative path to the file to read inside the sandbox.")

class WriteFileArgs(BaseModel):
    path: str = Field(description="The path where the file should be written into the sandbox.")
    content: str = Field(description="The string content to write.")

class ListDirArgs(BaseModel):
    path: str = Field(default=".", description="The directory path to list.")

@tool("fs_read", args_schema=ReadFileArgs)
def fs_read(path: str) -> str:
    """Reads the contents of a file inside the isolated Docker sandbox environment."""
    sandbox = SandboxManager(session_id="tool_exec")
    sandbox.start_sandbox()
    try:
        # Read file using cat via the sandbox bash executor
        exit_code, output = sandbox.execute_command(f"cat '{path}'")
        if exit_code != 0:
            return f"Error reading file {path}: {output}"
        return output
    finally:
        sandbox.teardown()

@tool("fs_write", args_schema=WriteFileArgs)
def fs_write(path: str, content: str) -> str:
    """Writes string content to a file inside the isolated Docker sandbox environment."""
    sandbox = SandboxManager(session_id="tool_exec")
    sandbox.start_sandbox()
    try:
        # We write via a bash heredoc in the sandbox to avoid intense escaping issues
        # Note: For production large files, we'd use docker SDK put_archive, but this aligns
        # with the simple tool bash wrapper implementation for now.
        escaped_content = content.replace("'", "'\\''")
        command = f"cat << 'EOF' > '{path}'\n{content}\nEOF"
        
        exit_code, output = sandbox.execute_command(command)
        if exit_code != 0:
            return f"Error writing file {path}: {output}"
        return f"Successfully wrote to {path}"
    finally:
        sandbox.teardown()

@tool("fs_list", args_schema=ListDirArgs)
def fs_list(path: str = ".") -> str:
    """Lists the contents of a directory inside the isolated Docker sandbox environment."""
    sandbox = SandboxManager(session_id="tool_exec")
    sandbox.start_sandbox()
    try:
        exit_code, output = sandbox.execute_command(f"ls -la '{path}'")
        if exit_code != 0:
            return f"Error listing directory {path}: {output}"
        return output
    finally:
        sandbox.teardown()

# Export the bundle of filesystem tools
fs_tools = [fs_read, fs_write, fs_list]
