from autocrab.core.plugins.base import ChannelPlugin
import asyncio

class ImessagePlugin(ChannelPlugin):
    @property
    def id(self) -> str:
        return "imessage"

    @property
    def version(self) -> str:
        return "1.0.0"

    async def start(self):
        print(f"Starting Imessage Channel Plugin (Stub)...")
        await asyncio.sleep(0.1)

    async def stop(self):
        print(f"Stopping Imessage Channel Plugin...")

    async def send_message(self, session_key: str, text: str, **kwargs):
        print(f"Imessage -> SEND [{session_key}]: {text}")
