from __future__ import annotations
import dataclasses
from enum import Enum
from typing import Any, Optional

class MessageType(str, Enum):
    TEXT = 'text'
    PHOTO = 'photo'
    IMAGE = 'photo'
    DOCUMENT = 'document'
    VIDEO = 'video'
    VOICE = 'voice'
    SYSTEM = 'system'

@dataclasses.dataclass
class MessageEvent:
    text: str = ''
    message_type: MessageType = MessageType.TEXT
    source: Any = None
    message_id: Optional[str] = None
    raw_message: Any = None
    timestamp: Any = None
    media_urls: list[Any] = dataclasses.field(default_factory=list)
    media_types: list[Any] = dataclasses.field(default_factory=list)
    attachments: list[Any] = dataclasses.field(default_factory=list)
    extra: dict[str, Any] = dataclasses.field(default_factory=dict)
    reply_to_message_id: Optional[str] = None
    reply_to_text: Optional[str] = None
    channel_prompt: Optional[str] = None
    auto_skill: Optional[str | list[str]] = None

@dataclasses.dataclass
class SendResult:
    success: bool
    error: Optional[str] = None
    message_id: Optional[str] = None

class BasePlatformAdapter:

    def __init__(self, *, config: Any=None, platform: Any=None, **kwargs: Any):
        self.config = config
        self.platform = platform
        self._message_handler = None
        self._running = False

    @property
    def name(self) -> str:
        return getattr(self.platform, 'value', None) or getattr(self.platform, 'name', 'unknown')

    def build_source(self, chat_id: str, chat_name: Optional[str]=None, chat_type: str='dm', user_id: Optional[str]=None, user_name: Optional[str]=None, **kwargs: Any) -> Any:
        return type('SessionSource', (), {'platform': self.platform, 'chat_id': str(chat_id), 'chat_name': chat_name, 'chat_type': chat_type, 'user_id': user_id, 'user_name': user_name, 'room_id': str(chat_id), 'sender': user_name, **kwargs})()

    def _mark_connected(self) -> None:
        self._running = True

    def _mark_disconnected(self) -> None:
        self._running = False

    async def connect(self) -> bool:
        return False

    async def disconnect(self) -> None:
        self._mark_disconnected()

    async def send(self, chat_id: str, content: str, reply_to: Optional[str]=None, metadata: Optional[dict]=None) -> SendResult:
        return SendResult(success=False, error='not implemented in base stub')

    async def edit_message(self, chat_id: str, message_id: str, content: str, *, finalize: bool=False) -> SendResult:
        return SendResult(success=False, error='not supported in base stub')

    async def handle_message(self, event: MessageEvent) -> None:
        self._emit_message(event)

    def _emit_message(self, event: MessageEvent) -> None:
        pass

def resolve_channel_prompt(config_extra: dict, channel_id: str, parent_id: str | None=None) -> str | None:
    prompts = config_extra.get('channel_prompts') or {}
    if not isinstance(prompts, dict):
        return None
    for key in (channel_id, parent_id):
        if not key:
            continue
        prompt = prompts.get(key)
        if prompt is None:
            continue
        prompt = str(prompt).strip()
        if prompt:
            return prompt
    return None
