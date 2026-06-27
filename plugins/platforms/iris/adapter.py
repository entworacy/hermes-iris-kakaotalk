from __future__ import annotations
import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
from urllib.parse import unquote as _unquote
import httpx
from gateway.config import Platform
try:
    from gateway.config import PlatformConfig
except ImportError:
    PlatformConfig = Any
from gateway.platforms.base import BasePlatformAdapter, MessageEvent, MessageType, SendResult, resolve_channel_prompt
from .kakao_payload import append_attachment_context_note, append_reply_note, chat_log_row_to_reply_context, extract_audio_attachment, extract_file_attachment, extract_image_urls, extract_src_log_id, extract_video_attachment, long_message_cdn_url, should_fetch_long_message_text, is_adcr_command, is_cr_command, is_image_message_type, is_reply_message, is_remote_url, is_system_feed_message, should_skip_self_by_v_origin, resolve_message_type
from .iris_config import fetch_iris_config
from .kakao_reaction import AOT_CACHE_TTL_SECONDS, DEFAULT_OKHTTP_VERSION, DEFAULT_TALK_VERSION, REACTION_CHECK, fetch_aot_credentials, send_kakao_reaction
from .media import MAX_INLINE_TEXT_BYTES, TEXT_EXTENSIONS, attachment_to_base64, cache_inbound_media_url, fetch_long_message_text, is_image_path
from .participant import cache_sender_avatar, query_sender_avatar_url, query_sender_member_type
from .room_registry import register_allowed_chat_id, resolve_hermes_config_path
from .skills_install import parse_auto_skills
logger = logging.getLogger(__name__)

def ensure_message_event_extra(event: MessageEvent) -> Dict[str, Any]:
    extra = getattr(event, 'extra', None)
    if not isinstance(extra, dict):
        extra = {}
        setattr(event, 'extra', extra)
    return extra
DEFAULT_WS_PATH = '/ws'
CHAT_LOG_BY_ID_QUERY = 'select * from chat_logs where id = ?'
CHAT_LINK_ID_QUERY = 'select link_id from chat_rooms where id = ?'
try:
    import websockets
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False
    websockets = None
_TRUTHY_ENV_VALUES = frozenset({'1', 'true', 'yes', 'on'})

def _env_flag_enabled(name: str, *, default: bool=False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return str(raw).strip().lower() in _TRUTHY_ENV_VALUES

def _ensure_iris_allow_all_users_default() -> None:
    """Gateway user auth for Iris defaults to open; room gating stays on allowed_chat_ids."""
    raw = os.getenv('IRIS_ALLOW_ALL_USERS')
    if raw is None or not str(raw).strip():
        os.environ['IRIS_ALLOW_ALL_USERS'] = 'true'

def iris_allow_all_users_enabled() -> bool:
    _ensure_iris_allow_all_users_default()
    return _env_flag_enabled('IRIS_ALLOW_ALL_USERS', default=True)

def check_requirements() -> bool:
    host = os.getenv('IRIS_HOST') or ''
    port = os.getenv('IRIS_PORT') or ''
    base = os.getenv('IRIS_BASE_URL') or ''
    return bool(host and port) or bool(base)

def validate_config(config) -> bool:
    extra = getattr(config, 'extra', {}) or {}
    host = extra.get('host') or os.getenv('IRIS_HOST')
    port = extra.get('port') or os.getenv('IRIS_PORT')
    base = extra.get('base_url') or os.getenv('IRIS_BASE_URL')
    return bool(host and port or base)

def is_connected(config) -> bool:
    return validate_config(config)

def _env_enablement() -> Optional[dict]:
    host = os.getenv('IRIS_HOST', '').strip()
    port = os.getenv('IRIS_PORT', '').strip()
    base = os.getenv('IRIS_BASE_URL', '').strip()
    if not (host and port or base):
        return None
    seed: Dict[str, Any] = {}
    if base:
        seed['base_url'] = base
    else:
        seed['host'] = host
        if port:
            seed['port'] = port
    allowed = os.getenv('IRIS_ALLOWED_CHAT_IDS', '').strip()
    if allowed:
        seed['allowed_chat_ids'] = [c.strip() for c in allowed.split(',') if c.strip()]
    bot_id = os.getenv('IRIS_BOT_ID', '').strip()
    if bot_id:
        seed['bot_id'] = bot_id
    bot_name = os.getenv('IRIS_BOT_NAME', '').strip()
    if bot_name:
        seed['bot_name'] = bot_name
    if _env_flag_enabled('IRIS_USER_ID_FILTER', default=False):
        seed['user_id_filter_enabled'] = True
    allowed_users = os.getenv('IRIS_ALLOWED_USER_IDS', '').strip()
    if allowed_users:
        seed['allowed_user_ids'] = [u.strip() for u in allowed_users.split(',') if u.strip()]
    home = os.getenv('IRIS_HOME_CHANNEL', '').strip() or allowed.split(',')[0].strip() if allowed else ''
    if home:
        seed['home_channel'] = {'chat_id': home, 'name': os.getenv('IRIS_HOME_CHANNEL_NAME', home)}
    return seed

async def _post_reply_standalone(base_url: str, payload: Dict[str, Any]) -> Optional[str]:
    url = f'{base_url}/reply'
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, json=payload)
        if resp.status_code >= 300:
            return f'Iris HTTP {resp.status_code}: {resp.text[:200]}'
        return None
    except Exception as e:
        return f'Iris standalone send failed: {e}'

async def _standalone_send(pconfig, chat_id: str, message: str, *, thread_id: Optional[str]=None, media_files: Optional[List[str]]=None, force_document: bool=False) -> Dict[str, Any]:
    extra = getattr(pconfig, 'extra', {}) or {}
    host = extra.get('host') or os.getenv('IRIS_HOST', '')
    port = extra.get('port') or os.getenv('IRIS_PORT', '')
    base = extra.get('base_url') or os.getenv('IRIS_BASE_URL', '')
    if base:
        base_url = str(base).rstrip('/')
    elif host and port:
        base_url = f'http://{host}:{port}'
    else:
        return {'error': 'Iris standalone send: IRIS_HOST+IRIS_PORT or IRIS_BASE_URL required'}
    room = chat_id or extra.get('home_channel', {}).get('chat_id', '')
    if not room:
        return {'error': 'Iris standalone send: chat_id (room) required'}
    if message and str(message).strip():
        payload: Dict[str, Any] = {'type': 'text', 'room': str(room), 'data': str(message)}
        if thread_id:
            payload['threadId'] = str(thread_id)
        err = await _post_reply_standalone(base_url, payload)
        if err:
            return {'error': err}
    for media_path in media_files or []:
        path = str(media_path)
        if not Path(path).exists():
            return {'error': f'Iris standalone send: file not found: {path}'}
        if is_image_path(path) and (not force_document):
            b64 = attachment_to_base64(path)
            if not b64:
                return {'error': f'Iris standalone send: failed to encode image: {path}'}
            img_payload: Dict[str, Any] = {'type': 'image', 'room': str(room), 'data': b64}
            if thread_id:
                img_payload['threadId'] = str(thread_id)
            err = await _post_reply_standalone(base_url, img_payload)
            if err:
                return {'error': err}
        else:
            name = Path(path).name
            doc_payload: Dict[str, Any] = {'type': 'text', 'room': str(room), 'data': f'📎 {name}'}
            if thread_id:
                doc_payload['threadId'] = str(thread_id)
            err = await _post_reply_standalone(base_url, doc_payload)
            if err:
                return {'error': err}
    return {'success': True, 'platform': 'iris', 'chat_id': str(room)}

class IrisAdapter(BasePlatformAdapter):
    MAX_MESSAGE_LENGTH = 4000
    SUPPORTS_MESSAGE_EDITING = False

    def __init__(self, config: PlatformConfig):
        platform = Platform('iris')
        super().__init__(config=config, platform=platform)
        extra = getattr(config, 'extra', {}) or {}
        self._host = str(extra.get('host') or os.getenv('IRIS_HOST', '') or '').strip()
        port_raw = extra.get('port') or os.getenv('IRIS_PORT') or ''
        try:
            self._port = int(port_raw) if port_raw not in (None, '', 0) else 3000
        except (ValueError, TypeError):
            self._port = 3000
        base = extra.get('base_url') or os.getenv('IRIS_BASE_URL') or ''
        if base:
            self._base_url = str(base).rstrip('/')
        elif self._host and self._port:
            self._base_url = f'http://{self._host}:{self._port}'
        else:
            self._base_url = None
        if self._base_url:
            bu = self._base_url
            if bu.startswith('https://'):
                self._ws_url = 'wss://' + bu[8:] + DEFAULT_WS_PATH
            elif bu.startswith('http://'):
                self._ws_url = 'ws://' + bu[7:] + DEFAULT_WS_PATH
            else:
                self._ws_url = bu + DEFAULT_WS_PATH
        else:
            self._ws_url = None
        allowed_raw = extra.get('allowed_chat_ids') or os.getenv('IRIS_ALLOWED_CHAT_IDS') or []
        if isinstance(allowed_raw, str):
            items = [x.strip() for x in allowed_raw.split(',') if x.strip()]
        else:
            try:
                items = [str(x).strip() for x in allowed_raw if str(x).strip()]
            except Exception:
                items = []
        self._allowed_chat_ids = set(items)
        self._config_path = resolve_hermes_config_path(extra.get('config_path'))
        users_raw = extra.get('allowed_user_ids') or os.getenv('IRIS_ALLOWED_USER_IDS') or []
        if isinstance(users_raw, str):
            user_items = [x.strip() for x in users_raw.split(',') if x.strip()]
        else:
            try:
                user_items = [str(x).strip() for x in users_raw if str(x).strip()]
            except Exception:
                user_items = []
        self._allowed_user_ids = set(user_items)
        filter_raw = extra.get('user_id_filter_enabled')
        if filter_raw is None:
            self._user_id_filter_enabled = _env_flag_enabled('IRIS_USER_ID_FILTER', default=False)
        else:
            self._user_id_filter_enabled = bool(filter_raw)
        bot_id_raw = extra.get('bot_id') or os.getenv('IRIS_BOT_ID') or ''
        self._bot_id = str(bot_id_raw).strip() or None
        bot_name_raw = extra.get('bot_name') or os.getenv('IRIS_BOT_NAME') or 'Iris'
        self._bot_names = {str(bot_name_raw).strip(), 'Iris', 'iris'}
        self._bot_names = {n for n in self._bot_names if n}
        self._check_reaction_enabled = _env_flag_enabled('IRIS_CHECK_REACTION', default=False)
        self._talk_version = str(extra.get('talk_version') or os.getenv('IRIS_TALK_VERSION') or DEFAULT_TALK_VERSION).strip() or DEFAULT_TALK_VERSION
        self._okhttp_version = str(extra.get('okhttp_version') or os.getenv('IRIS_OKHTTP_VERSION') or DEFAULT_OKHTTP_VERSION).strip() or DEFAULT_OKHTTP_VERSION
        self._aot_cache: Optional[Tuple[str, str, float]] = None
        self._link_id_cache: Dict[str, Optional[int]] = {}
        self._ws_task: Optional[asyncio.Task] = None
        self._outbound_msg_seq = 0
        self._progress_last_sent: Dict[str, str] = {}
        auto_raw = extra.get('auto_skills') or os.getenv('IRIS_AUTO_SKILLS')
        self._auto_skills = parse_auto_skills(auto_raw)

    def _allocate_message_id(self) -> str:
        self._outbound_msg_seq += 1
        return f'iris-out-{self._outbound_msg_seq}'

    def _truncate_outbound(self, content: str) -> str:
        text = str(content or '')
        limit = int(getattr(self, 'MAX_MESSAGE_LENGTH', 4000) or 4000)
        if len(text) <= limit:
            return text
        return text[:max(0, limit - 20)] + '\n...(truncated)'

    def _should_ignore_inbound(self, event: MessageEvent, payload: Optional[dict]=None) -> bool:
        json_row = (payload or {}).get('json') or payload or {}
        if isinstance(event.raw_message, dict):
            json_row = event.raw_message.get('json') or event.raw_message
        v = json_row.get('v') if isinstance(json_row, dict) else None
        if should_skip_self_by_v_origin(v):
            logger.debug('[%s] ignoring self message v.origin=WRITE', self.name)
            return True
        msg_type = json_row.get('type') if isinstance(json_row, dict) else None
        if is_system_feed_message(event.text, msg_type):
            logger.debug('[%s] ignoring system/feed message type=%s', self.name, msg_type)
            return True
        return False

    def _is_allowed_chat(self, chat_id: str) -> bool:
        return bool(chat_id) and str(chat_id) in self._allowed_chat_ids

    def _is_allowed_user(self, user_id: str) -> bool:
        if not self._user_id_filter_enabled:
            return True
        if not self._allowed_user_ids:
            return True
        return bool(user_id) and str(user_id) in self._allowed_user_ids

    def _is_allowed_inbound(self, chat_id: str, user_id: str) -> bool:
        return self._is_allowed_chat(chat_id) and self._is_allowed_user(user_id)

    async def _ensure_bot_id(self) -> None:
        if self._bot_id or not self._base_url:
            return
        bot_id, bot_name = await fetch_iris_config(self._base_url)
        if bot_id:
            self._bot_id = bot_id
            extra = getattr(self.config, 'extra', None)
            if isinstance(extra, dict):
                extra['bot_id'] = bot_id
            logger.info('[%s] auto-resolved bot_id from GET /config: %s', self.name, bot_id)
        if bot_name:
            self._bot_names.add(bot_name)

    async def _get_aot_credentials(self, *, force_refresh: bool=False) -> Tuple[Optional[str], Optional[str]]:
        now = datetime.now(tz=timezone.utc).timestamp()
        if not force_refresh and self._aot_cache is not None and (now < self._aot_cache[2]):
            return (self._aot_cache[0], self._aot_cache[1])
        if not self._base_url:
            return (None, None)
        token, device_uuid = await fetch_aot_credentials(self._base_url)
        if token and device_uuid:
            self._aot_cache = (token, device_uuid, now + AOT_CACHE_TTL_SECONDS)
        return (token, device_uuid)

    async def _get_link_id(self, chat_id: str) -> Optional[int]:
        cid = str(chat_id or '').strip()
        if not cid:
            return None
        if cid in self._link_id_cache:
            return self._link_id_cache[cid]
        link_id: Optional[int] = None
        rows = await self._iris_query(CHAT_LINK_ID_QUERY, [cid])
        if rows:
            raw = rows[0].get('link_id')
            if raw not in (None, '', '0', 0):
                try:
                    link_id = int(raw)
                except (TypeError, ValueError):
                    link_id = None
        self._link_id_cache[cid] = link_id
        return link_id

    async def _leave_check_reaction(self, chat_id: str, log_id: str) -> None:
        if not self._check_reaction_enabled or not chat_id or (not log_id):
            return
        token, device_uuid = await self._get_aot_credentials()
        if not token or not device_uuid:
            logger.debug('[%s] skip check reaction: missing /aot credentials', self.name)
            return
        link_id = await self._get_link_id(chat_id)
        ok = await send_kakao_reaction(str(chat_id), str(log_id), token, device_uuid, reaction_type=REACTION_CHECK, link_id=link_id, talk_version=self._talk_version, okhttp_version=self._okhttp_version)
        if ok:
            logger.debug('[%s] left CHECK reaction chat=%s log=%s', self.name, chat_id, log_id)
        else:
            token, device_uuid = await self._get_aot_credentials(force_refresh=True)
            if token and device_uuid:
                await send_kakao_reaction(str(chat_id), str(log_id), token, device_uuid, reaction_type=REACTION_CHECK, link_id=link_id, talk_version=self._talk_version, okhttp_version=self._okhttp_version)

    def _schedule_check_reaction(self, chat_id: str, log_id: str) -> None:
        if not self._check_reaction_enabled or not chat_id or (not log_id):
            return

        async def _run() -> None:
            try:
                await self._leave_check_reaction(chat_id, log_id)
            except Exception as e:
                logger.debug('[%s] check reaction task failed: %s', self.name, e)
        try:
            asyncio.create_task(_run())
        except RuntimeError:
            logger.debug('[%s] no running loop for check reaction', self.name)

    async def _register_chat(self, chat_id: str) -> Tuple[bool, str]:
        ok, msg = register_allowed_chat_id(chat_id, current_ids=self._allowed_chat_ids, config_path=self._config_path)
        if ok and chat_id and (str(chat_id) not in self._allowed_chat_ids):
            self._allowed_chat_ids.add(str(chat_id))
            extra = getattr(self.config, 'extra', None)
            if isinstance(extra, dict):
                existing = extra.get('allowed_chat_ids') or []
                merged = sorted({str(x).strip() for x in existing if str(x).strip()} | {str(chat_id)})
                extra['allowed_chat_ids'] = merged
        return (ok, msg)

    async def _handle_inbound_event(self, event: MessageEvent, payload: Optional[dict]=None) -> bool:
        if self._should_ignore_inbound(event, payload):
            return False
        chat_id = str(event.source.chat_id) if event.source and event.source.chat_id else ''
        log_id = str(event.message_id or '').strip()
        if chat_id and log_id:
            self._schedule_check_reaction(chat_id, log_id)
        if is_adcr_command(event.text):
            _ok, msg = await self._register_chat(chat_id)
            await self.send(chat_id, msg)
            return True
        if is_cr_command(event.text):
            await self.send(chat_id, chat_id)
            return True
        user_id = str(getattr(event.source, 'user_id', '') or '') if event.source else ''
        if self._is_allowed_inbound(chat_id, user_id):
            if self._auto_skills:
                event.auto_skill = self._auto_skills[0] if len(self._auto_skills) == 1 else list(self._auto_skills)
            await self.handle_message(event)
            return True
        if self._is_allowed_chat(chat_id) and (not self._is_allowed_user(user_id)):
            logger.debug('[%s] ignoring inbound from disallowed user_id=%s chat=%s', self.name, user_id, chat_id)
        return False

    async def connect(self) -> bool:
        if not self._ws_url:
            logger.error('[%s] no ws_url configured', self.name)
            return False
        if not WEBSOCKETS_AVAILABLE:
            logger.error("[%s] requires 'websockets' package. Install with: pip install websockets", self.name)
            return False
        try:
            await self._ensure_bot_id()
            self._ws_task = asyncio.create_task(self._ws_receive_loop())
            self._mark_connected()
            logger.info('[%s] connecting WS to %s', self.name, self._ws_url)
            return True
        except Exception as e:
            logger.error('[%s] failed to connect: %s', self.name, e)
            return False

    async def _process_ws_payload(self, data: dict) -> None:
        try:
            event = await self._build_message_event(data)
            if not event:
                return
            await self._handle_inbound_event(event, data)
        except Exception as e:
            logger.warning('[%s] WS inbound processing error: %s', self.name, e)

    async def _ws_receive_loop(self) -> None:
        backoff = 1
        while self._running:
            try:
                async with websockets.connect(self._ws_url, ping_interval=20, ping_timeout=10) as ws:
                    logger.info('[%s] WS connected', self.name)
                    backoff = 1
                    async for raw in ws:
                        if not self._running:
                            return
                        try:
                            data = json.loads(raw) if isinstance(raw, (str, bytes)) else raw
                            if not isinstance(data, dict):
                                continue
                            asyncio.create_task(self._process_ws_payload(data))
                        except Exception as e:
                            logger.warning('[%s] WS message parse error: %s', self.name, e)
            except asyncio.CancelledError:
                return
            except Exception as e:
                if not self._running:
                    return
                logger.warning('[%s] WS error: %s (reconnect in %ss)', self.name, e, backoff)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 30)
        logger.info('[%s] WS loop ended', self.name)

    async def disconnect(self) -> None:
        self._mark_disconnected()
        if self._ws_task:
            self._ws_task.cancel()
            try:
                await self._ws_task
            except asyncio.CancelledError:
                pass
            self._ws_task = None

    async def _iris_query(self, query: str, bind: Optional[List[Any]]=None) -> List[Dict[str, Any]]:
        if not self._base_url:
            return []
        url = f'{self._base_url}/query'
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(url, json={'query': query, 'bind': bind or []})
            if resp.status_code >= 300:
                logger.warning('Iris /query failed: %s %s', resp.status_code, resp.text[:200])
                return []
            body = resp.json()
            data = body.get('data') if isinstance(body, dict) else None
            return data if isinstance(data, list) else []
        except Exception as e:
            logger.warning('Iris /query error: %s', e)
            return []

    async def _attach_reply_context(self, event: MessageEvent, json_row: dict) -> None:
        att = json_row.get('attachment')
        mtype = json_row.get('type') or 0
        if not is_reply_message(mtype, att):
            return
        src_log_id = extract_src_log_id(att)
        if not src_log_id:
            return
        rows = await self._iris_query(CHAT_LOG_BY_ID_QUERY, [src_log_id])
        if not rows:
            logger.debug('Iris: reply source not found for src_logId=%s', src_log_id)
            return
        ctx = chat_log_row_to_reply_context(rows[0])
        event.reply_to_message_id = ctx.get('reply_to_message_id')
        event.reply_to_text = ctx.get('reply_to_text')
        quoted_urls = ctx.get('quoted_media_urls') or []
        quoted_kinds = ctx.get('quoted_media_kinds') or []
        quoted_names = ctx.get('quoted_media_names') or []
        quoted_types = ctx.get('quoted_media_types') or []
        cached_paths: List[str] = []
        cached_types: List[str] = []
        for idx, url in enumerate(quoted_urls):
            display = quoted_names[idx] if idx < len(quoted_names) else f'quoted_{idx + 1}'
            kind = quoted_kinds[idx] if idx < len(quoted_kinds) else 'image'
            content_type = quoted_types[idx] if idx < len(quoted_types) else 'application/octet-stream'
            cached = await cache_inbound_media_url(url, display_name=display, kind=kind, content_type=content_type)
            if cached:
                cached_paths.append(cached['path'])
                cached_types.append(cached.get('media_type', content_type))
                event.text = append_reply_note(event.text, f"[Replied-to {cached['kind']} '{cached['display_name']}' saved at: {cached['path']}]")
            else:
                logger.debug('Iris: could not cache quoted media url=%s', url)
        if cached_paths:
            existing_paths = list(event.media_urls or [])
            existing_types = list(event.media_types or [])
            event.media_urls = cached_paths + existing_paths
            event.media_types = cached_types + existing_types
            if not existing_paths:
                event.message_type = getattr(MessageType, 'PHOTO', event.message_type)

    async def _cache_inbound_media(self, event: MessageEvent, json_row: dict) -> List[str]:
        failed_urls: List[str] = []
        if not event.media_urls:
            return failed_urls
        att = json_row.get('attachment')
        mtype = json_row.get('type') or 0
        file_att = extract_file_attachment(att, mtype)
        doc_type = resolve_message_type('DOCUMENT')
        video_type = resolve_message_type('VIDEO')
        voice_type = resolve_message_type('VOICE', 'AUDIO')
        cached_paths: List[str] = []
        cached_types: List[str] = []
        for idx, url in enumerate(event.media_urls):
            if not is_remote_url(url):
                cached_paths.append(url)
                if idx < len(event.media_types or []):
                    cached_types.append(event.media_types[idx])
                continue
            content_type = event.media_types[idx] if idx < len(event.media_types or []) else 'application/octet-stream'
            if file_att:
                display_name = str(file_att.get('filename') or f'file_{idx + 1}')
                kind = 'file'
            elif event.message_type in {doc_type, video_type, voice_type}:
                display_name = f'media_{idx + 1}'
                kind = 'file'
            else:
                display_name = f'image_{idx + 1}'
                kind = 'image'
            cached = await cache_inbound_media_url(url, display_name=display_name, kind=kind, content_type=content_type)
            if cached:
                cached_paths.append(cached['path'])
                cached_types.append(cached.get('media_type', content_type))
            else:
                logger.warning('Iris: could not cache inbound media url=%s', url)
                failed_urls.append(url)
                cached_paths.append(url)
                cached_types.append(content_type)
        if cached_paths:
            event.media_urls = cached_paths
            if cached_types:
                event.media_types = cached_types
        return failed_urls

    async def _resolve_long_message_text(self, event: MessageEvent, json_row: dict) -> None:
        att = json_row.get('attachment')
        mtype = json_row.get('type') or 0
        if not should_fetch_long_message_text(event.text, att, mtype):
            return
        url = long_message_cdn_url(att)
        if not url:
            return
        full_text = await fetch_long_message_text(url)
        if full_text is not None:
            event.text = full_text

    async def _build_message_event(self, payload: dict) -> Optional[MessageEvent]:
        event = self._payload_to_message_event(payload)
        if not event:
            return None
        json_row = payload.get('json') or payload
        await self._resolve_long_message_text(event, json_row)
        failed_urls = await self._cache_inbound_media(event, json_row)
        await self._attach_reply_context(event, json_row)
        await self._attach_sender_context(event, json_row)
        append_attachment_context_note(event, json_row, cache_failed_urls=failed_urls)
        chat_id = str(json_row.get('chat_id') or '')
        if chat_id:
            event.channel_prompt = self._resolve_iris_channel_prompt(chat_id)
        return event

    def _resolve_iris_channel_prompt(self, chat_id: str) -> Optional[str]:
        if not chat_id:
            return None
        extra = getattr(self.config, 'extra', None) or {}
        prompt = resolve_channel_prompt(extra, chat_id)
        if prompt:
            return prompt
        return resolve_channel_prompt(extra, '_default')

    async def _attach_sender_context(self, event: MessageEvent, json_row: dict) -> None:
        chat_id = str(json_row.get('chat_id') or '')
        user_id = str(json_row.get('user_id') or '')
        if not chat_id or not user_id:
            return
        await self._ensure_bot_id()
        member_type = await query_sender_member_type(self._iris_query, chat_id=chat_id, user_id=user_id, bot_id=self._bot_id)
        avatar_url = await query_sender_avatar_url(self._iris_query, chat_id=chat_id, user_id=user_id)
        extra = ensure_message_event_extra(event)
        if member_type:
            extra['sender_member_type'] = member_type
        if avatar_url:
            extra['sender_avatar_url'] = avatar_url
            cached = await cache_sender_avatar(cache_inbound_media_url, user_id=user_id, avatar_url=avatar_url)
            if cached:
                extra['sender_avatar_path'] = cached['path']
                if getattr(event.source, 'user_id', None):
                    try:
                        event.source.avatar_url = avatar_url
                        event.source.avatar_path = cached['path']
                        if member_type:
                            event.source.member_type = member_type
                    except Exception:
                        pass

    def _payload_to_message_event(self, payload: dict) -> Optional[MessageEvent]:
        try:
            json_row = payload.get('json') or payload
            text = payload.get('msg') or json_row.get('message') or ''
            room_name = payload.get('room') or json_row.get('room') or ''
            sender_name = payload.get('sender') or ''
            chat_id = str(json_row.get('chat_id') or json_row.get('id') or payload.get('chat_id') or '')
            user_id = str(json_row.get('user_id') or payload.get('user_id') or '')
            msg_id = str(json_row.get('id') or payload.get('id') or '')
            att = json_row.get('attachment')
            mtype = json_row.get('type') or 0
            message_type = MessageType.TEXT
            media_urls: List[str] = []
            media_types: List[str] = []
            reply_to_message_id: Optional[str] = None
            file_att = extract_file_attachment(att, mtype)
            video_att = extract_video_attachment(att, mtype)
            audio_att = extract_audio_attachment(att, mtype)
            if file_att:
                message_type = getattr(MessageType, 'DOCUMENT', MessageType.TEXT)
                if file_att.get('url'):
                    media_urls.append(file_att['url'])
                    media_types.append(file_att.get('content_type') or 'application/octet-stream')
                if not text:
                    text = f"[파일: {file_att.get('filename', 'file')}]"
            elif video_att:
                message_type = resolve_message_type('VIDEO')
                media_urls.append(video_att['url'])
                media_types.append(video_att.get('content_type') or 'video/mp4')
                if not text:
                    text = '[동영상]'
            elif audio_att:
                message_type = resolve_message_type('VOICE', 'AUDIO')
                media_urls.append(audio_att['url'])
                media_types.append(audio_att.get('content_type') or 'audio/mpeg')
                if not text:
                    text = '[음성 메시지]'
            else:
                image_urls = extract_image_urls(att, mtype)
                if image_urls:
                    message_type = getattr(MessageType, 'PHOTO', MessageType.TEXT)
                    media_urls = list(image_urls)
                    media_types = ['image/jpeg'] * len(image_urls)
                elif is_image_message_type(mtype):
                    message_type = getattr(MessageType, 'PHOTO', MessageType.TEXT)
                    if not text:
                        text = '[이미지]'
            source = self.build_source(chat_id=chat_id, chat_name=room_name or chat_id, chat_type='group', user_id=user_id or sender_name, user_name=sender_name, message_id=msg_id)
            if is_reply_message(mtype, att):
                src_id = extract_src_log_id(att)
                if src_id:
                    reply_to_message_id = src_id
            return MessageEvent(text=text or '', message_type=message_type, source=source, message_id=msg_id, raw_message=payload, timestamp=datetime.now(tz=timezone.utc), media_urls=media_urls, media_types=media_types, reply_to_message_id=reply_to_message_id)
        except Exception as e:
            logger.warning('Iris: failed to parse payload to MessageEvent: %s', e)
            return None

    async def _post_reply(self, payload: dict) -> bool:
        if not self._base_url:
            logger.error('Iris: no base_url configured')
            return False
        url = f'{self._base_url}/reply'
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(url, json=payload)
            if resp.status_code >= 300:
                logger.warning('Iris /reply failed: %s %s', resp.status_code, resp.text[:200])
                return False
            return True
        except Exception as e:
            logger.error('Iris /reply error: %s', e)
            return False

    async def send(self, chat_id: str, content: str, reply_to: Optional[str]=None, metadata: Optional[Dict[str, Any]]=None) -> SendResult:
        metadata = metadata or {}
        if not chat_id:
            return SendResult(success=False, error='chat_id required')
        if not content or not str(content).strip():
            return SendResult(success=True)
        body = self._truncate_outbound(str(content))
        if metadata and metadata.get('verbose'):
            body = '처리중...\n\n' + body
        payload: Dict[str, Any] = {'type': 'text', 'room': str(chat_id), 'data': body}
        thread_id = metadata.get('thread_id')
        if thread_id:
            payload['threadId'] = str(thread_id)
        ok = await self._post_reply(payload)
        if ok:
            return SendResult(success=True, message_id=self._allocate_message_id())
        return SendResult(success=False, error='Iris text send failed')

    async def edit_message(self, chat_id: str, message_id: str, content: str, *, finalize: bool=False) -> SendResult:
        del finalize
        body = self._truncate_outbound(str(content))
        if not body.strip():
            return SendResult(success=True, message_id=message_id)
        dedupe_key = f'{chat_id}:{message_id}'
        if self._progress_last_sent.get(dedupe_key) == body:
            return SendResult(success=True, message_id=message_id)
        result = await self.send(chat_id, body)
        if result.success and result.message_id:
            self._progress_last_sent[dedupe_key] = body
            return SendResult(success=True, message_id=result.message_id)
        return result

    async def send_image(self, chat_id: str, image_url: str, caption: Optional[str]=None, reply_to: Optional[str]=None, metadata: Optional[Dict[str, Any]]=None) -> SendResult:
        metadata = metadata or {}
        b64 = attachment_to_base64(image_url)
        if not b64:
            return SendResult(success=False, error='failed to encode image for Iris')
        payload: Dict[str, Any] = {'type': 'image', 'room': str(chat_id), 'data': b64}
        thread_id = metadata.get('thread_id')
        if thread_id:
            payload['threadId'] = str(thread_id)
        ok = await self._post_reply(payload)
        if not ok:
            return SendResult(success=False, error='Iris image send failed')
        if caption and str(caption).strip():
            return await self.send(chat_id, str(caption), reply_to=reply_to, metadata=metadata)
        return SendResult(success=True)

    async def send_image_file(self, chat_id: str, image_path: str, caption: Optional[str]=None, reply_to: Optional[str]=None, metadata: Optional[Dict[str, Any]]=None) -> SendResult:
        return await self.send_image(chat_id, image_path, caption=caption, reply_to=reply_to, metadata=metadata)

    async def send_multiple_images(self, chat_id: str, images: List[Tuple[str, str]], metadata: Optional[Dict[str, Any]]=None, human_delay: float=0.0) -> None:
        metadata = metadata or {}
        b64_list: List[str] = []
        for image_url, _alt_text in images:
            if human_delay > 0:
                await asyncio.sleep(human_delay)
            source = image_url
            if image_url.startswith('file://'):
                source = _unquote(image_url[7:])
            b64 = attachment_to_base64(source)
            if b64:
                b64_list.append(b64)
        if not b64_list:
            logger.warning('Iris: no images encoded for send_multiple_images')
            return
        if len(b64_list) == 1:
            payload: Dict[str, Any] = {'type': 'image', 'room': str(chat_id), 'data': b64_list[0]}
        else:
            payload = {'type': 'image_multiple', 'room': str(chat_id), 'data': b64_list}
        thread_id = metadata.get('thread_id')
        if thread_id:
            payload['threadId'] = str(thread_id)
        await self._post_reply(payload)

    async def send_document(self, chat_id: str, file_path: str, caption: Optional[str]=None, file_name: Optional[str]=None, reply_to: Optional[str]=None, metadata: Optional[Dict[str, Any]]=None, **kwargs) -> SendResult:
        metadata = metadata or {}
        path = Path(file_path)
        if not path.exists():
            return SendResult(success=False, error='file not found')
        force_document = bool(kwargs.get('force_document'))
        if is_image_path(file_path) and (not force_document):
            return await self.send_image_file(chat_id, file_path, caption=caption, reply_to=reply_to, metadata=metadata)
        name = file_name or path.name
        lines: List[str] = []
        if caption and str(caption).strip():
            lines.append(str(caption))
        if path.suffix.lower() in TEXT_EXTENSIONS and path.stat().st_size <= MAX_INLINE_TEXT_BYTES:
            try:
                content = path.read_text(encoding='utf-8', errors='replace').strip()
                if content:
                    if len(content) > MAX_INLINE_TEXT_BYTES:
                        content = content[:MAX_INLINE_TEXT_BYTES] + '\n...(truncated)'
                    lines.append(f'📎 {name}')
                    lines.append(content)
                    return await self.send(chat_id, '\n'.join(lines), reply_to=reply_to, metadata=metadata)
            except OSError as e:
                logger.debug('Iris: could not read text file %s: %s', path, e)
        lines.append(f'📎 {name}')
        lines.append('(Iris/KakaoTalk API는 이미지 외 파일 전송을 지원하지 않아 파일명만 전달합니다.)')
        return await self.send(chat_id, '\n'.join(lines), reply_to=reply_to, metadata=metadata)

    async def send_typing(self, chat_id: str, metadata=None) -> None:
        pass

    async def get_chat_info(self, chat_id: str) -> Dict[str, Any]:
        return {'name': chat_id, 'type': 'group'}

def _enable_iris_platform_in_config() -> None:
    path = resolve_hermes_config_path()
    if path is None:
        return
    try:
        from utils import atomic_roundtrip_yaml_update
        atomic_roundtrip_yaml_update(path, 'gateway.platforms.iris.enabled', True)
    except Exception:
        try:
            import yaml
            path.parent.mkdir(parents=True, exist_ok=True)
            data: Dict[str, Any] = {}
            if path.exists():
                loaded = yaml.safe_load(path.read_text(encoding='utf-8'))
                if isinstance(loaded, dict):
                    data = loaded
            gateway = data.setdefault('gateway', {})
            platforms = gateway.setdefault('platforms', {})
            iris = platforms.setdefault('iris', {})
            iris['enabled'] = True
            path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding='utf-8')
        except Exception as e:
            logger.warning('Iris: failed to enable platform in config.yaml: %s', e)

def interactive_setup() -> None:
    from hermes_cli.setup import get_env_value, print_header, print_info, print_success, print_warning, prompt, save_env_value
    print_header('Iris (KakaoTalk)')
    print_info('루팅 Android의 Iris 서버에 연결합니다. WS 수신에는 pip install websockets 가 필요합니다.')
    host = prompt('Iris host IP', default=get_env_value('IRIS_HOST') or '')
    if not str(host).strip():
        print_warning('IRIS_HOST가 필요합니다. 설정을 건너뜁니다.')
        return
    save_env_value('IRIS_HOST', str(host).strip())
    port = prompt('Iris port', default=get_env_value('IRIS_PORT') or '3000')
    port_text = str(port).strip() or '3000'
    try:
        save_env_value('IRIS_PORT', str(int(port_text)))
    except ValueError:
        print_warning(f'잘못된 포트입니다. 기본값 3000을 사용합니다.')
        save_env_value('IRIS_PORT', '3000')
    allowed = prompt('Allowed chat IDs (comma-separated, optional)', default=get_env_value('IRIS_ALLOWED_CHAT_IDS') or '')
    if str(allowed).strip():
        save_env_value('IRIS_ALLOWED_CHAT_IDS', str(allowed).strip())
    if not str(get_env_value('IRIS_ALLOW_ALL_USERS') or '').strip():
        save_env_value('IRIS_ALLOW_ALL_USERS', 'true')
    _enable_iris_platform_in_config()
    print_success('Iris 설정 완료. 게이트웨이 재시작: hermes gateway restart')

def register_platform(ctx) -> None:
    _ensure_iris_allow_all_users_default()
    ctx.register_platform(name='iris', label='Iris (KakaoTalk)', adapter_factory=lambda cfg: IrisAdapter(cfg), check_fn=check_requirements, validate_config=validate_config, is_connected=is_connected, required_env=['IRIS_HOST', 'IRIS_PORT'], install_hint='Iris on rooted Android required. For WS receive: pip install websockets. See https://github.com/dolidolih/Iris and irispy-client for image formats.', env_enablement_fn=_env_enablement, cron_deliver_env_var='IRIS_HOME_CHANNEL', standalone_sender_fn=_standalone_send, allowed_users_env='IRIS_ALLOWED_USER_IDS', allow_all_env='IRIS_ALLOW_ALL_USERS', emoji='💬', platform_hint='카카오톡(Iris)에서 사용자의 개인 비서로 응답합니다. 정중한 해요체, 친근하지만 프로페셔널하게. 답변은 핵심→필요 시 부연→(선택)다음 행동 제안 순으로. 짧은 인사에도 성의 있게 응대하고 "네." 한 줄로 끝내지 않습니다. 마크다운·코드블록·이모지 남용 없이 카톡 순수 텍스트로.', pii_safe=False, allow_update_command=True, setup_fn=interactive_setup)
register = register_platform
from .kakao_payload import append_reply_note as _append_reply_note, chat_log_row_to_reply_context, extract_src_log_id, is_adcr_command, is_cr_command, is_reply_message, is_self_message
from .media import attachment_to_base64 as _attachment_to_base64, cache_inbound_media_url
from .room_registry import register_allowed_chat_id
