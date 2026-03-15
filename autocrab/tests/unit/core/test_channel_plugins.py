import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from autocrab.plugins.channels.discord.plugin import DiscordPlugin
from autocrab.plugins.channels.telegram.plugin import TelegramPlugin
from autocrab.core.models.config import settings

@pytest.mark.asyncio
async def test_discord_plugin_mention_gating():
    """Test that DiscordPlugin correctly filters messages based on mentions."""
    plugin = DiscordPlugin()
    plugin.on_event = AsyncMock()
    plugin.client = MagicMock()
    plugin.client.user.id = 123
    plugin.client.user.mentioned_in.return_value = False
    
    # Mock settings to require mention
    with patch("autocrab.plugins.channels.discord.plugin.settings") as mock_settings:
        mock_settings.channels.discord.requireMention = True
        mock_settings.channels.discord.groupPolicy = "allowlist"
        mock_settings.channels.discord.guilds = {}
        
        # Test 1: Guild message without mention (should be ignored)
        mock_message = MagicMock()
        mock_message.guild = MagicMock()
        mock_message.guild.id = 456
        mock_message.author.id = 789
        mock_message.content = "hello"
        
        await plugin._handle_message(mock_message)
        plugin.on_event.assert_not_called()
        
        # Test 2: Guild message WITH mention (should pass)
        plugin.client.user.mentioned_in.return_value = True
        await plugin._handle_message(mock_message)
        plugin.on_event.assert_called_once()
        
        # Test 3: DM message (should pass regardless of mention)
        plugin.on_event.reset_mock()
        mock_message.guild = None
        plugin.client.user.mentioned_in.return_value = False
        await plugin._handle_message(mock_message)
        plugin.on_event.assert_called_once()

@pytest.mark.asyncio
async def test_telegram_plugin_account_id():
    """Test that TelegramPlugin correctly resolves account_id."""
    plugin = TelegramPlugin()
    plugin.on_event = AsyncMock()
    
    # Mock telegram structures
    mock_bot = AsyncMock()
    mock_bot.id = 12345
    mock_bot.get_me.return_value = MagicMock(id=12345, username="test_bot")
    
    mock_update = MagicMock()
    mock_update.effective_message.text = "hello"
    mock_update.effective_chat.id = 67890
    mock_update.effective_user.username = "user"
    
    mock_context = MagicMock()
    mock_context.bot = mock_bot
    
    await plugin._handle_message(mock_update, mock_context)
    
    plugin.on_event.assert_called_once()
    event = plugin.on_event.call_args[0][0]
    assert event.account_id == "12345"
    assert event.text == "hello"

def test_loader_discovery_and_registry():
    """Test that loader correctly identifies and registers plugins."""
    from autocrab.core.plugins.loader import _CHANNEL_PLUGINS, _INSTALLED_PLUGINS, load_plugins_from_directory, get_channel_plugin
    import os
    
    # Verify registries work
    _CHANNEL_PLUGINS["test"] = MagicMock()
    assert get_channel_plugin("test") is not None
    assert get_channel_plugin("nonexistent") is None
    
    # Verify stop_all call logic
    with patch.object(_CHANNEL_PLUGINS["test"], "stop", new_callable=AsyncMock) as mock_stop:
        from autocrab.core.plugins.loader import stop_all_channels
        import asyncio
        asyncio.run(stop_all_channels())
        mock_stop.assert_called_once()
