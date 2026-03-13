from typing import Any, Dict
from autocrab.core.models.api import FunctionSpec
from autocrab.core.sandbox.manager import SandboxManager

# The JSON schema definition for the LLM
BASH_TOOL_SPEC = FunctionSpec(
    name="bash",
    description="Execute a bash command within a secure, isolated Linux container sandbox. The sandbox has access to a dedicated /workspace directory.",
    parameters={
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "The shell command to execute."
            }
        },
        "required": ["command"]
    }
)

def execute_bash_tool(sandbox: SandboxManager, arguments: Dict[str, Any]) -> str:
    """
    Executes the bash command parsed from the Agent via LangGraph 
    inside the active Docker Sandbox.
    """
    if "command" not in arguments:
        return "Error: arguments missing 'command'"
        
    command = arguments["command"]
    try:
        exit_code, output = sandbox.execute_command(command)
        
        result_str = f"Exit Code: {exit_code}\\n"
        result_str += f"Output:\\n{output if output else '<no output>'}"
        return result_str
    except Exception as e:
        return f"System Error executing sandbox command: {str(e)}"
