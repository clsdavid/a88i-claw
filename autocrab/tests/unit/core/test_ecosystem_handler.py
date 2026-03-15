import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from autocrab.core.plugins.base import ChannelEvent
from autocrab.core.plugins.handler import handle_channel_event

@pytest.mark.asyncio
async def test_handle_channel_event_routing():
    """
    Test that handle_channel_event correctly resolves a route, 
    invokes the agent, and sends a reply back.
    """
    event = ChannelEvent(
        channel="discord",
        account_id="bot_id",
        peer={"kind": "direct", "id": "user_id"},
        text="hello",
        guild_id=None
    )
    
    # Mock routing and agent
    mock_route = MagicMock()
    mock_route.agent_id = "test_agent"
    
    mock_final_state = {
        "messages": [MagicMock(content="Hello back!")]
    }
    
    mock_plugin = AsyncMock()
    
    with patch("autocrab.core.plugins.handler.resolve_agent_route", return_value=mock_route) as mock_resolve, \
         patch("autocrab.core.plugins.handler.build_agent_session_key", return_value="test_session") as mock_session, \
         patch("autocrab.core.plugins.handler.agent_executor.ainvoke", return_value=mock_final_state) as mock_invoke, \
         patch("autocrab.core.plugins.handler.get_channel_plugin", return_value=mock_plugin):
        
        await handle_channel_event(event)
        
        # Verify routing was called
        mock_resolve.assert_called_once()
        mock_session.assert_called_once()
        
        # Verify agent was invoked
        mock_invoke.assert_called_once()
        args = mock_invoke.call_args[0][0]
        assert args["session_id"] == "test_session"
        assert args["agent_id"] == "test_agent"
        
        # Verify reply was sent back to the plugin
        mock_plugin.send_message.assert_called_once_with("test_session", "Hello back!")

@pytest.mark.asyncio
async def test_handle_channel_event_failure():
    """Test resilience when agent execution fails."""
    event = ChannelEvent(
        channel="discord",
        account_id="bot_id",
        peer={"kind": "direct", "id": "user_id"},
        text="fail",
        guild_id=None
    )
    
    mock_route = MagicMock(agent_id="test_agent")
    
    with patch("autocrab.core.plugins.handler.resolve_agent_route", return_value=mock_route), \
         patch("autocrab.core.plugins.handler.agent_executor.ainvoke", side_effect=Exception("Brain crash")):
        
        # Should not raise exception (it's caught and printed)
        await handle_channel_event(event)
