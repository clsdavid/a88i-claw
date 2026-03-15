from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any, Union, Callable, Coroutine
from pydantic import BaseModel

class ChannelEvent(BaseModel):
    channel: str
    account_id: str
    peer: Dict[str, str] # {"kind": "direct", "id": "..."}
    text: str
    raw_payload: Optional[Dict[str, Any]] = None
    guild_id: Optional[str] = None
    team_id: Optional[str] = None
    member_role_ids: Optional[List[str]] = None

class BasePlugin(ABC):
    @property
    @abstractmethod
    def id(self) -> str:
        """Unique ID of the plugin."""
        pass

    @property
    @abstractmethod
    def version(self) -> str:
        """Version of the plugin."""
        pass

class ChannelPlugin(BasePlugin, ABC):
    on_event: Optional[Callable[[ChannelEvent], Coroutine[Any, Any, None]]] = None

    @abstractmethod
    async def start(self):
        """Start the channel (connect to WS, register webhooks, etc.)"""
        pass

    @abstractmethod
    async def stop(self):
        """Stop the channel."""
        pass

    @abstractmethod
    async def send_message(self, session_key: str, text: str, **kwargs):
        """Send a message back to the channel."""
        pass
