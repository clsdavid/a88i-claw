import pytest
from unittest.mock import patch, MagicMock
from autocrab.core.tools.mcp import McpToolRegistry
from autocrab.core.models.config import settings
import httpx

@pytest.fixture
def enable_mcp():
    original_enabled = settings.features.enable_external_mcp
    original_url = settings.features.mcp_provider_url
    
    settings.features.enable_external_mcp = True
    settings.features.mcp_provider_url = "http://mcp.test.mock"
    
    yield
    
    settings.features.enable_external_mcp = original_enabled
    settings.features.mcp_provider_url = original_url

@pytest.mark.asyncio
async def test_mcp_fetch_schemas_disabled():
    # If disabled, should return empty immediately without network requests
    registry = McpToolRegistry()
    registry.enabled = False
    schemas = await registry.fetch_schemas()
    assert len(schemas) == 0

@pytest.mark.asyncio
async def test_mcp_fetch_schemas_success(enable_mcp):
    registry = McpToolRegistry()
    
    # Mock httpx AsyncClient
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": "get_crypto_price",
                    "description": "Fetch live crypto prices",
                    "parameters": {"type": "object", "properties": {"symbol": {"type": "string"}}}
                }
            }
        ]
    }
    
    with patch('httpx.AsyncClient.get', return_value=mock_response):
        schemas = await registry.fetch_schemas()
        
        assert len(schemas) == 1
        assert schemas[0].type == "function"
        assert schemas[0].function.name == "get_crypto_price"
        assert "symbol" in schemas[0].function.parameters["properties"]

@pytest.mark.asyncio
async def test_mcp_execute_tool_success(enable_mcp):
    registry = McpToolRegistry()
    
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"result": "$65,000"}
    
    with patch('httpx.AsyncClient.post', return_value=mock_response):
        result = await registry.execute_tool("get_crypto_price", {"symbol": "BTC"})
        assert result == "$65,000"
