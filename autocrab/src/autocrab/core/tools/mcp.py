import httpx
from typing import List, Dict, Any, Optional
from autocrab.core.models.config import settings
from autocrab.core.models.api import FunctionSpec, ToolDefinition

class McpToolRegistry:
    """
    Connects to the external MCP (Model Context Protocol) provider (e.g., mcp.test)
    to dynamically fetch live data schemas (Forex, Stock, Crypto).
    
    This replaces the bundled Node.js plugins and shifts maintenance to external providers.
    """
    def __init__(self):
        self.enabled = settings.features.enable_external_mcp
        self.provider_url = settings.features.mcp_provider_url
        self.remote_schemas: List[ToolDefinition] = []

    async def fetch_schemas(self) -> List[ToolDefinition]:
        """
        Pulls the available JSON schemas from the MCP provider.
        Returns empty list if the feature flag is disabled or unreachable.
        """
        if not self.enabled or not self.provider_url:
            return []
            
        try:
            async with httpx.AsyncClient() as client:
                # Query the canonical MCP tools endpoint
                resp = await client.get(f"{self.provider_url}/v1/tools", timeout=3.0)
                if resp.status_code == 200:
                    data = resp.json()
                    schemas = []
                    # Map the MCP format to our precise API ToolDefinition format
                    for tool in data.get("tools", []):
                        if tool.get("type") == "function":
                            fn_data = tool.get("function", {})
                            spec = FunctionSpec(
                                name=fn_data.get("name"),
                                description=fn_data.get("description"),
                                parameters=fn_data.get("parameters")
                            )
                            schemas.append(ToolDefinition(type="function", function=spec))
                    
                    self.remote_schemas = schemas
                    return self.remote_schemas
        except Exception as e:
            # Silently fail on network issues to prevent Agent loop crashes
            print(f"[Warning] Failed to fetch MCP tools: {e}")
            
        return []

    async def execute_tool(self, name: str, arguments: Dict[str, Any]) -> str:
        """
        Proxies theological execution of the tool to the external provider.
        """
        if not self.enabled or not self.provider_url:
            return "Error: MCP provider disabled."
            
        payload = {
            "name": name,
            "arguments": arguments
        }
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{self.provider_url}/v1/execute", 
                    json=payload, 
                    timeout=10.0 # Tools may take time to calculate
                )
                if resp.status_code == 200:
                    return resp.json().get("result", "Success")
                else:
                    return f"MCP Provider execution error: {resp.text}"
        except Exception as e:
            return f"MCP Network error during tool execution: {str(e)}"
