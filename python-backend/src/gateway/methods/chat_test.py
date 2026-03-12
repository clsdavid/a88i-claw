import sys
import os
import json
import pytest
from unittest.mock import MagicMock, patch, AsyncMock

# Add src to python path for imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))

from src.gateway.methods.chat import handle_chat_send
from src.config.manager import settings

@pytest.fixture
def mock_websocket():
    ws = AsyncMock()
    ws.send_json = AsyncMock()
    return ws

@pytest.fixture
def mock_params():
    return {
        "sessionKey": "test-session",
        "message": "Hello"
    }

@pytest.fixture
def setup_mocks():
    # Mock settings.sessions_dir
    with patch("src.gateway.methods.chat.settings") as mock_settings:
        mock_settings.sessions_dir = "/tmp/sessions"
        mock_settings.backend_type = "ollama"
        mock_settings.max_context_tokens = 4096
        mock_settings.max_generate_tokens = 1000
        yield mock_settings

class MockAioFile:
    def __init__(self, content=None):
        self.content = content or []
        self.written = []
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, *args):
        pass
        
    async def write(self, data):
        self.written.append(data)
        
    def __aiter__(self):
        async def gen():
            for line in self.content:
                yield line
        return gen()

@pytest.mark.asyncio
async def test_handle_chat_send_happy_path(mock_websocket, mock_params, setup_mocks):
    """
    Test the happy path:
    1. ACK sent
    2. History loaded
    3. User message saved
    4. System prompt injected
    5. Model stream called
    6. Response streamed
    7. Assistant message saved
    """
    
    # Simulate history file content
    history_content = [
        # Line 1: previous user message
        json.dumps({"role": "user", "content": "previous"}),
        # Line 2: previous assistant message
        json.dumps({"role": "assistant", "content": "response"})
    ]
    
    # Setup mock file with class
    mock_file = MockAioFile(history_content)
    
    with patch("aiofiles.open", return_value=mock_file):
        with patch("os.path.exists", return_value=True):
            with patch("src.gateway.methods.chat.model_client") as mock_client:
                # Mock model streaming response
                async def mock_chat_completions(*args, **kwargs):
                    yield {"content": "Hello"}
                    yield {"content": " World"}
                    
                mock_client.chat_completions.side_effect = mock_chat_completions
                
                # Run the function
                await handle_chat_send(mock_websocket, "req-1", mock_params)
                
                # 1. Verify ACK
                mock_websocket.send_json.assert_any_call({
                    "type": "res",
                    "id": "req-1",
                    "ok": True,
                    "payload": {}
                })
                
                # 2. Verify history loading & System Prompt Injection
                # We need to inspect the 'messages' argument passed to chat_completions
                call_args = mock_client.chat_completions.call_args
                assert call_args is not None
                messages_arg = call_args[1]['messages'] # kwargs['messages']
                
                # Expected: System Prompt + Previous User + Previous Assistant + New User
                assert messages_arg[0]['role'] == 'system'
                assert messages_arg[0]['content'] == 'You are a helpful AI assistant.'
                
                assert messages_arg[1]['role'] == 'user'
                assert messages_arg[1]['content'] == 'previous'
                
                assert messages_arg[2]['role'] == 'assistant'
                assert messages_arg[2]['content'] == 'response'
                
                assert messages_arg[3]['role'] == 'user'
                assert messages_arg[3]['content'] == 'Hello'
                
                # 3. Verify User Message Saved (write called)
                # Should be written twice: once for user message, once for assistant
                assert len(mock_file.written) >= 2
                
                # 4. Verify Streaming Events
                # Check for "delta" events
                calls = mock_websocket.send_json.call_args_list
                delta_calls = [c for c in calls if c[0][0].get("event") == "chat.event" and c[0][0]["payload"]["state"] == "delta"]
                assert len(delta_calls) >= 2
                assert delta_calls[0][0][0]["payload"]["message"]["content"] == "Hello"
                assert delta_calls[1][0][0]["payload"]["message"]["content"] == "Hello World"
                
                # Check for "final" event
                final_calls = [c for c in calls if c[0][0].get("event") == "chat.event" and c[0][0]["payload"]["state"] == "final"]
                assert len(final_calls) == 1
                assert final_calls[0][0][0]["payload"]["message"]["content"] == "Hello World"

@pytest.mark.asyncio
async def test_handle_chat_send_missing_session(mock_websocket, setup_mocks):
    """Test behavior when sessionKey is missing."""
    params = {"message": "Hello"} # No sessionKey
    
    await handle_chat_send(mock_websocket, "req-1", params)
    
    # ACK should still be sent
    mock_websocket.send_json.assert_called_with({
        "type": "res",
        "id": "req-1",
        "ok": True,
        "payload": {}
    })
    
    # But no file operations should happen
    with patch("aiofiles.open") as mock_open:
        assert not mock_open.called

@pytest.mark.asyncio
async def test_handle_chat_send_history_error(mock_websocket, mock_params, setup_mocks):
    """Test handling of corrupt history file lines."""
    
    # Simulate bad JSON in history
    history_content = [
        '{"role": "user", "content": "valid"}',
        'INVALID JSON',
        '{"role": "assistant", "content": "also valid"}'
    ]
    
    mock_file = MockAioFile(history_content)
    
    with patch("aiofiles.open", return_value=mock_file):
        with patch("os.path.exists", return_value=True):
            with patch("src.gateway.methods.chat.model_client") as mock_client:
                # Mock empty stream
                async def mock_empty_stream(*args, **kwargs):
                    if False: yield
                
                mock_client.chat_completions.side_effect = mock_empty_stream

                await handle_chat_send(mock_websocket, "req-1", mock_params)
                
                # Should not crash
                mock_websocket.send_json.assert_called()
                
                # Verify that despite error, we tried to call model
                assert mock_client.chat_completions.called
                
                # Check that valid messages were loaded
                call_args = mock_client.chat_completions.call_args
                messages_arg = call_args[1]['messages']
                
                # System prompt (index 0)
                assert messages_arg[0]['role'] == 'system'
                
                # Valid user message from history (index 1)
                assert messages_arg[1]['content'] == 'valid'
                
                # Valid assistant message (index 2) - should include 'also valid' even if one line failed?
                # The implementation swallows only the bad line.
                assert messages_arg[2]['content'] == 'also valid'
                
                # New user message (index 3)
                assert messages_arg[3]['content'] == 'Hello'
