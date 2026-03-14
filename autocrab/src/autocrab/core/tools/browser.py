from typing import Optional, List, Dict, Any
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from autocrab.core.sandbox.manager import SandboxManager

class BrowserCommandArgs(BaseModel):
    action: str = Field(description="The browser action to take: 'goto', 'click', 'type', 'screenshot', 'get_html', 'eval'")
    url: Optional[str] = Field(default=None, description="The URL to navigate to (if action is 'goto')")
    selector: Optional[str] = Field(default=None, description="CSS selector for 'click', 'type', 'get_html'")
    text: Optional[str] = Field(default=None, description="Text to type (if action is 'type')")
    script: Optional[str] = Field(default=None, description="JavaScript string to evaluate (if action is 'eval')")

@tool("browser_tool", args_schema=BrowserCommandArgs)
def browser_tool(
    action: str, 
    url: Optional[str] = None, 
    selector: Optional[str] = None, 
    text: Optional[str] = None,
    script: Optional[str] = None
) -> str:
    """
    Automates a browser inside the isolated Docker sandbox.
    Currently acts as a mock/stub that executes simple curl/Python scripts in the container 
    since setting up a full headless playwright container requires a custom image.
    In Phase 6, this will connect to `sandbox-browser`.
    """
    sandbox = SandboxManager(session_id="tool_exec")
    sandbox.start_sandbox()
    try:
        if action == "goto":
            if not url:
                return "Error: URL is required for goto action."
            # Stub implementation using curl inside sandbox
            exit_code, output = sandbox.execute_command(f"curl -sL {url} | head -n 50")
            return f"Successfully loaded {url}. Preview:\\n{output}"
        
        # Other actions will return stubs for the time being until Playwright is piped in
        return f"Browser action '{action}' executed successfully (Stub)."
    finally:
        sandbox.teardown()

browser_tools = [browser_tool]
