from autocrab.core.plugins.base import ChannelPlugin
import asyncio

class SignalPlugin(ChannelPlugin):
    @property
    def id(self) -> str:
        return "signal"

    @property
    def version(self) -> str:
        return "1.0.0"

    async def start(self):
        print(f"Starting Signal Channel Plugin (Stub)...")
        await asyncio.sleep(0.1)

    async def stop(self):
        print(f"Stopping Signal Channel Plugin...")

    async def send_message(self, session_key: str, text: str, **kwargs):
        print(f"Signal -> SEND [{session_key}]: {text}")
