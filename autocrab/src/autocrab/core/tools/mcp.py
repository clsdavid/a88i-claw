import json
import httpx
from typing import List, Dict, Any
from autocrab.core.models.config import settings
from autocrab.core.models.api import FunctionSpec, ToolDefinition

class McpToolRegistry:
    """
    Connects to the external MCP (Model Context Protocol) provider (e.g., mcp.test)
    by exposing proxy tools (mcp_list, mcp_help, mcp_run) for dynamic discovery.
    """
    def __init__(self):
        self.enabled = settings.features.enable_external_mcp
        self.provider_url = settings.features.mcp_provider_url
        self.remote_schemas: List[ToolDefinition] = []

    async def fetch_schemas(self) -> List[ToolDefinition]:
        """
        Returns the three proxy tools necessary to interact with the MCP server dynamically.
        """
        if not self.enabled or not self.provider_url:
            return []
            
        self.remote_schemas = [
            ToolDefinition(
                type="function",
                function=FunctionSpec(
                    name="mcp_list",
                    description="List all available tools from the external MCP provider.",
                    parameters={"type": "object", "properties": {}}
                )
            ),
            ToolDefinition(
                type="function",
                function=FunctionSpec(
                    name="mcp_help",
                    description="Get the manual and required arguments for a specific MCP tool. Use this before running any new MCP tool.",
                    parameters={
                        "type": "object", 
                        "properties": {
                            "tool_name": {"type": "string", "description": "Name of the tool to get help for"}
                        },
                        "required": ["tool_name"]
                    }
                )
            ),
            ToolDefinition(
                type="function",
                function=FunctionSpec(
                    name="mcp_run",
                    description="Execute a specific MCP tool with the required arguments discovered via mcp_help.",
                    parameters={
                        "type": "object", 
                        "properties": {
                            "tool_name": {"type": "string", "description": "Name of the tool to execute"},
                            "input_data": {"type": "object", "description": "The exact JSON payload required by the tool"}
                        },
                        "required": ["tool_name", "input_data"]
                    }
                )
            )
        ]
        return self.remote_schemas

    async def execute_tool(self, name: str, arguments: Dict[str, Any]) -> str:
        """
        Proxies the execution of the proxy tools to the external provider.
        """
        if not self.enabled or not self.provider_url:
            return "Error: MCP provider disabled."
            
        try:
            async with httpx.AsyncClient() as client:
                if name == "mcp_list":
                    resp = await client.get(f"{self.provider_url}/mcp/tools", timeout=5.0)
                    if resp.status_code == 200:
                        data = resp.json()
                        tools_list = data.get("tools", [])
                        return f"Available MCP Tools ({data.get('count', len(tools_list))}):\n" + ", ".join(tools_list)
                    return f"Error listing MCP tools: {resp.text}"
                    
                elif name == "mcp_help":
                    tool_name = arguments.get("tool_name", "")
                    resp = await client.get(f"{self.provider_url}/mcp/tools/{tool_name}", timeout=5.0)
                    if resp.status_code == 200:
                        return json.dumps(resp.json(), indent=2)
                    return f"Error getting help for {tool_name}: {resp.text}"
                    
                elif name == "mcp_run":
                    tool_name = arguments.get("tool_name", "")
                    input_data = arguments.get("input_data", {})
                    payload = {
                        "tool": tool_name,
                        "input_data": input_data
                    }
                    resp = await client.post(
                        f"{self.provider_url}/mcp/run", 
                        json=payload, 
                        timeout=15.0
                    )
                    if resp.status_code == 200:
                        return json.dumps(resp.json(), indent=2)
                    return f"MCP Provider execution error: {resp.text}"
                    
        except Exception as e:
            return f"MCP Network error during {name}: {str(e)}"
        
        return f"Unknown MCP tool proxy: {name}"
