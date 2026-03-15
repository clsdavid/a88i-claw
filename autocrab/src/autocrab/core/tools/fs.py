from typing import Dict, Any
from langchain_core.tools import tool
from pydantic import BaseModel, Field
from autocrab.core.models.api import FunctionSpec
from autocrab.core.sandbox.manager import SandboxManager

FS_READ_TOOL_SPEC = FunctionSpec(
    name="fs_read",
    description="Reads the contents of a file inside the isolated Docker sandbox environment.",
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "The absolute or relative path to the file to read inside the sandbox."}
        },
        "required": ["path"]
    }
)

FS_WRITE_TOOL_SPEC = FunctionSpec(
    name="fs_write",
    description="Writes string content to a file inside the isolated Docker sandbox environment.",
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "The path where the file should be written into the sandbox."},
            "content": {"type": "string", "description": "The string content to write."}
        },
        "required": ["path", "content"]
    }
)

FS_LIST_TOOL_SPEC = FunctionSpec(
    name="fs_list",
    description="Lists the contents of a directory inside the isolated Docker sandbox environment.",
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "The directory path to list. Defaults to current directory."}
        }
    }
)

class FsReadArgs(BaseModel):
    path: str = Field(description="The absolute or relative path to the file to read inside the sandbox.")

@tool("fs_read", args_schema=FsReadArgs)
def fs_read(path: str) -> str:
    """Reads the contents of a file inside the isolated Docker sandbox environment."""
    sandbox = SandboxManager(session_id="tool_exec")
    sandbox.start_sandbox()
    try:
        return execute_fs_read(sandbox, {"path": path})
    finally:
        sandbox.teardown()

class FsWriteArgs(BaseModel):
    path: str = Field(description="The path where the file should be written into the sandbox.")
    content: str = Field(description="The string content to write.")

@tool("fs_write", args_schema=FsWriteArgs)
def fs_write(path: str, content: str) -> str:
    """Writes string content to a file inside the isolated Docker sandbox environment."""
    sandbox = SandboxManager(session_id="tool_exec")
    sandbox.start_sandbox()
    try:
        return execute_fs_write(sandbox, {"path": path, "content": content})
    finally:
        sandbox.teardown()

class FsListArgs(BaseModel):
    path: str = Field(default=".", description="The directory path to list. Defaults to current directory.")

@tool("fs_list", args_schema=FsListArgs)
def fs_list(path: str = ".") -> str:
    """Lists the contents of a directory inside the isolated Docker sandbox environment."""
    sandbox = SandboxManager(session_id="tool_exec")
    sandbox.start_sandbox()
    try:
        return execute_fs_list(sandbox, {"path": path})
    finally:
        sandbox.teardown()

fs_tool_specs = [FS_READ_TOOL_SPEC, FS_WRITE_TOOL_SPEC, FS_LIST_TOOL_SPEC]
fs_tools = [fs_read, fs_write, fs_list]


def execute_fs_read(sandbox: SandboxManager, args: Dict[str, Any]) -> str:
    path = args.get("path")
    if not path:
        return "Error: Missing path argument"
    exit_code, output = sandbox.execute_command(f"cat '{path}'")
    if exit_code != 0:
        return f"Error reading file {path}: {output}"
    return output

def execute_fs_write(sandbox: SandboxManager, args: Dict[str, Any]) -> str:
    path = args.get("path")
    content = args.get("content")
    if not path or not content:
        return "Error: Missing path or content argument"
    escaped_content = content.replace("'", "'\\''")
    command = f"cat << 'EOF' > '{path}'\n{content}\nEOF"
    exit_code, output = sandbox.execute_command(command)
    if exit_code != 0:
        return f"Error writing file {path}: {output}"
    return f"Successfully wrote to {path}"

def execute_fs_list(sandbox: SandboxManager, args: Dict[str, Any]) -> str:
    path = args.get("path", ".")
    exit_code, output = sandbox.execute_command(f"ls -la '{path}'")
    if exit_code != 0:
        return f"Error listing directory {path}: {output}"
    return output

