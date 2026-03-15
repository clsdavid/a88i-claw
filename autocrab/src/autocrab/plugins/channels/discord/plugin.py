import discord
import asyncio
import os
from typing import Optional, Dict, Any, List
from autocrab.core.plugins.base import ChannelPlugin, ChannelEvent
from autocrab.core.models.config import settings

class DiscordPlugin(ChannelPlugin):
    def __init__(self):
        super().__init__()
        self.client: Optional[discord.Client] = None
        self._task: Optional[asyncio.Task] = None

    @property
    def id(self) -> str:
        return "discord"

    @property
    def version(self) -> str:
        return "1.0.0"

    async def start(self):
        if not settings.channels or not settings.channels.discord:
            print("[Discord] No configuration found in autocrab.json. Skipping.")
            return

        # Handle token resolution (env or config)
        token = os.environ.get("AUTOCRAB_DISCORD_TOKEN")
        if not token:
            if settings.channels.discord.token:
                token = settings.channels.discord.token
            elif settings.channels.discord.accounts:
                acc_name = settings.channels.discord.defaultAccount or list(settings.channels.discord.accounts.keys())[0]
                token = settings.channels.discord.accounts[acc_name].token

        if not token or (isinstance(token, dict)):
            # If it's a secret reference dict, we might need a secret resolver
            # For now, expect a string
            print("[Discord] Token not found or invalid.")
            return

        intents = discord.Intents.default()
        intents.message_content = True
        intents.guilds = True
        intents.members = True # May requires privileged intent in portal

        self.client = discord.Client(intents=intents)

        @self.client.event
        async def on_ready():
            print(f"[Discord] Logged in as {self.client.user} (ID: {self.client.user.id})")

        @self.client.event
        async def on_message(message: discord.Message):
            # 1. Ignore own messages
            if message.author == self.client.user:
                return

            # 2. Basic Filtering (Parity with Node.js monitor)
            # Todo: Implement more complex allowlist/denylist checks here
            
            # 3. Dispatch to internal event handler if registered
            if self.on_event:
                try:
                    event = ChannelEvent(
                        channel="discord",
                        account_id=str(self.client.user.id),
                        peer={
                            "kind": "channel" if message.guild else "direct", 
                            "id": str(message.channel.id)
                        },
                        text=message.content,
                        raw_payload={
                            "message_id": str(message.id),
                            "author_id": str(message.author.id),
                            "author_tag": str(message.author)
                        },
                        guild_id=str(message.guild.id) if message.guild else None,
                        member_role_ids=[str(r.id) for r in message.author.roles] if hasattr(message.author, 'roles') else []
                    )
                    await self.on_event(event)
                except Exception as e:
                    print(f"[Discord] Error dispatching event: {e}")

        # Run client in background task to not block the main process
        print("[Discord] Starting background client task...")
        self._task = asyncio.create_task(self.client.start(token))

    async def stop(self):
        if self.client:
            print("[Discord] Closing client...")
            await self.client.close()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def send_message(self, session_key: str, text: str, **kwargs):
        """
        Sends a message back to Discord.
        session_key format: discord:accountId:channelId:authorId:[scope]
        """
        if not self.client or not self.client.is_ready():
            print("[Discord] Cannot send message: Client not ready.")
            return

        parts = session_key.split(":")
        if len(parts) < 3 or parts[0] != "discord":
            print(f"[Discord] Invalid session key for response: {session_key}")
            return

        channel_id_str = parts[2]
        try:
            channel_id = int(channel_id_str)
            channel = self.client.get_channel(channel_id)
            if not channel:
                channel = await self.client.fetch_channel(channel_id)
            
            if channel:
                await channel.send(text)
            else:
                print(f"[Discord] Channel {channel_id} not found.")
        except Exception as e:
            print(f"[Discord] Failed to send message to {channel_id_str}: {e}")
