from autocrab.core.plugins.base import ChannelPlugin
import asyncio

class DiscordPlugin(ChannelPlugin):
    @property
    def id(self) -> str:
        return "discord"

    @property
    def version(self) -> str:
        return "1.0.0"

    async def start(self):
        print(f"Starting Discord Channel Plugin (Stub)...")
        # In a real implementation, this would connect to Discord's Gateway or set up a webhook
        await asyncio.sleep(0.1)

    async def stop(self):
        print(f"Stopping Discord Channel Plugin...")

    async def send_message(self, session_key: str, text: str, **kwargs):
        print(f"Discord -> SEND [{session_key}]: {text}")
