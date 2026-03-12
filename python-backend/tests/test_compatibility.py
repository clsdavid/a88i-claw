import sys
import os
import pytest
import json
import httpx
from unittest.mock import MagicMock, AsyncMock, patch

# Add parent directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from model_client import ModelClient
from config import settings

@pytest.fixture
def mock_httpx_client():
    with patch("httpx.AsyncClient") as mock_client:
        # The instance returned by AsyncClient()
        mock_instance = MagicMock()
        mock_client.return_value = mock_instance
        
        # .post is async
        mock_instance.post = AsyncMock()
        
        # .stream returns a context manager (sync call usually, supports async with)
        mock_instance.stream = MagicMock()
        
        yield mock_instance

@pytest.mark.asyncio
async def test_chat_completion_streaming_tools(mock_httpx_client):
    """Test compatibility with streaming tool calls (OpenAI style)"""
    client = ModelClient()
    
    # Mock streaming response content
    # Use json.dumps to avoid escaping hell
    chunk1 = {"choices": [{"delta": {"content": "Thinking..."}}]}
    chunk2 = {"choices": [{"delta": {"tool_calls": [{"index": 0, "id": "call_123", "type": "function", "function": {"name": "get_weather", "arguments": ""}}]}}]}
    chunk3 = {"choices": [{"delta": {"tool_calls": [{"index": 0, "function": {"arguments": '{"location": "London"}'}}]}}]}
    chunk4 = {"choices": [{"delta": {"tool_calls": [{"index": 0, "function": {"arguments": "}"}}]}}]}
    
    stream_chunks = [
        f"data: {json.dumps(chunk1)}",
        f"data: {json.dumps(chunk2)}",
        f"data: {json.dumps(chunk3)}",
        f"data: {json.dumps(chunk4)}",
        "data: [DONE]"
    ]
    
    # Setup the mock stream
    # response object inside context
    mock_response = MagicMock() 
    mock_response.status_code = 200
    mock_response.read = AsyncMock(return_value=b"")
    
    async def async_iter_lines():
        for line in stream_chunks:
            yield line
            
    mock_response.aiter_lines = async_iter_lines
    
    # Configure mock client to return this response context manager
    mock_context = AsyncMock()
    mock_context.__aenter__.return_value = mock_response
    mock_httpx_client.stream.return_value = mock_context

    # Run the client
    messages = [{"role": "user", "content": "What's the weather?"}]
    tools = [{"type": "function", "function": {"name": "get_weather"}}]
    
    responses = []
    async for chunk in client.chat_completions(messages, stream=True, tools=tools):
        responses.append(chunk)

    # Verify requests passed correctly
    call_kwargs = mock_httpx_client.stream.call_args.kwargs
    payload = call_kwargs['json']
    assert payload['stream'] is True
    assert payload['tools'] == tools
    
    # Verify we got the deltas back
    # The first chunk content is "Thinking..."
    # The second chunk is tool_calls start
    assert len(responses) == 4
    assert responses[0]['content'] == "Thinking..."
    assert responses[1]['tool_calls'][0]['id'] == "call_123"
    assert "location" in responses[2]['tool_calls'][0]['function']['arguments']

@pytest.mark.asyncio
async def test_chat_completion_non_streaming(mock_httpx_client):
    """Test compatibility with non-streaming full response (Pass-through)"""
    client = ModelClient()
    
    # Mock full JSON response
    mock_full_response = {
        "id": "chatcmpl-123",
        "object": "chat.completion",
        "choices": [{
            "index": 0,
            "message": {
                "role": "assistant",
                "content": None,
                "tool_calls": [{
                    "id": "call_456",
                    "type": "function",
                    "function": {
                        "name": "search_web",
                        "arguments": "{\"query\": \"python testing\"}"
                    }
                }]
            },
            "finish_reason": "tool_calls"
        }]
    }

    # Response for .post()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = mock_full_response
    mock_response.text = "" 
    
    mock_httpx_client.post.return_value = mock_response

    # Run client with stream=False
    messages = [{"role": "user", "content": "Search for python testing"}]
    
    # Generator should yield exactly one item
    results = []
    async for res in client.chat_completions(messages, stream=False):
        results.append(res)
    
    assert len(results) == 1
    assert results[0] == mock_full_response
    
    # Verify post was called, not stream
    mock_httpx_client.post.assert_called_once()
    payload = mock_httpx_client.post.call_args.kwargs['json']
    assert payload['stream'] is False
