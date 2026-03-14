import pytest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
from autocrab.core.webhooks.celery_app import process_incoming_webhook
from langchain_core.messages import AIMessage

@patch("autocrab.core.agent.memory.HybridMemoryStore")
@patch("autocrab.core.agent.graph.agent_executor")
def test_process_incoming_webhook(mock_agent_executor, mock_hybrid_memory_store):
    # Setup mocks
    mock_store_instance = AsyncMock()
    mock_hybrid_memory_store.return_value = mock_store_instance
    
    mock_agent_executor.ainvoke = AsyncMock(return_value={
        "messages": [AIMessage(content="Hello from AI!")]
    })
    
    payload = {"channel_id": "test_session", "text": "Hello bot"}
    
    # In Celery testing, you can use .apply() to run synchronously
    result = process_incoming_webhook("discord", payload)
    
    assert result == "Hello from AI!"
    mock_agent_executor.ainvoke.assert_called_once()
    mock_store_instance.add_interaction.assert_called_once_with("assistant", "Hello from AI!")

def test_process_incoming_webhook_no_content():
    result = process_incoming_webhook("discord", {"channel_id": "test_session", "text": ""})
    assert result == "No content"
