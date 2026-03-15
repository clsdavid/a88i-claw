from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes
import asyncio
import os
from typing import Optional, Dict, Any, List
from autocrab.core.plugins.base import ChannelPlugin, ChannelEvent
from autocrab.core.models.config import settings

class TelegramPlugin(ChannelPlugin):
    def __init__(self):
        super().__init__()
        self.application: Optional[Any] = None
        self._stop_event: Optional[asyncio.Event] = None
        self._task: Optional[asyncio.Task] = None

    @property
    def id(self) -> str:
        return "telegram"

    @property
    def version(self) -> str:
        return "1.0.0"

    async def start(self):
        token = os.environ.get("AUTOCRAB_TELEGRAM_TOKEN")
        if not token and settings.channels and settings.channels.telegram:
            token = settings.channels.telegram.token

        if not token:
            print("[Telegram] Token not found in ENV or autocrab.json. Skipping.")
            return

        print(f"[Telegram] Initializing plugin...")
        self.application = ApplicationBuilder().token(token).build()

        async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
            await self._handle_message(update, context)

        self.application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), message_handler))

        # Start the application
        await self.application.initialize()
        await self.application.start()
        
        # Start polling in a background task
        print("[Telegram] Starting background polling task...")
        if self.application.updater:
            self._task = asyncio.create_task(self.application.updater.start_polling())
        else:
            print("[Telegram] Error: Updater not initialized.")

    async def _handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Internal handler for incoming Telegram messages."""
        if not update.effective_message or not update.effective_message.text:
            return

        bot_info = await context.bot.get_me()
        account_id = str(bot_info.id)

        if self.on_event:
            try:
                event = ChannelEvent(
                    channel="telegram",
                    account_id=account_id,
                    peer={
                        "kind": "chat", 
                        "id": str(update.effective_chat.id)
                    },
                    text=update.effective_message.text,
                    raw_payload={
                        "message_id": update.effective_message.message_id,
                        "from_user": str(update.effective_user.username) if update.effective_user else "unknown"
                    }
                )
                await self.on_event(event)
            except Exception as e:
                print(f"[Telegram] Error processing message: {e}")

    async def stop(self):
        if self.application:
            print("[Telegram] Stopping plugin...")
            if self.application.updater:
                await self.application.updater.stop()
            await self.application.stop()
            await self.application.shutdown()
        
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def send_message(self, session_key: str, text: str, **kwargs):
        """
        Sends a message back to Telegram.
        session_key format: telegram:accountId:chatId:[...]
        """
        if not self.application or not self.application.bot:
            print("[Telegram] Cannot send message: Bot not initialized.")
            return

        parts = session_key.split(":")
        if len(parts) < 3 or parts[0] != "telegram":
            print(f"[Telegram] Invalid session key for response: {session_key}")
            return

        chat_id = parts[2]
        try:
            await self.application.bot.send_message(chat_id=chat_id, text=text)
        except Exception as e:
            print(f"[Telegram] Failed to send message to {chat_id}: {e}")
