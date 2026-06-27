from __future__ import annotations
import json
import logging
from typing import Any, Dict, List, Optional, Union
from gateway.platforms.base import MessageEvent, MessageType
logger = logging.getLogger(__name__)
FILE_MESSAGE_TYPES = frozenset({18})
IMAGE_MESSAGE_TYPES = frozenset({2, 27, 71})
VIDEO_MESSAGE_TYPES = frozenset({3, 36})
AUDIO_MESSAGE_TYPES = frozenset({5, 16})
KAKAO_TEXT_TYPE = 1
LONG_MESSAGE_MIN_CHARS = 3900
MAX_ATTACHMENT_JSON_CHARS = 2000
CR_COMMAND = '!cr'
ADCR_COMMAND = '!adcr'
REPLY_MESSAGE_TYPES = frozenset({26})
V_SKIP_ORIGINS = frozenset({'SYNCMSG', 'MCHATLOGS'})
V_SELF_ORIGINS = frozenset({'WRITE'})
V_INBOUND_ORIGINS = frozenset({'MSG'})
V_ORIGIN_ACTIONS: Dict[str, str] = {'SYNCMSG': 'SKIP_SYNC', 'MCHATLOGS': 'SKIP_SYNC', 'WRITE': 'SKIP_SELF', 'MSG': 'ROUTE_BY_TYPE'}

def is_cr_command(text: str) -> bool:
    return str(text or '').strip().lower() == CR_COMMAND

def is_adcr_command(text: str) -> bool:
    return str(text or '').strip().lower() == ADCR_COMMAND

def is_self_message(user_id: Union[str, int, None], sender_name: Optional[str], *, bot_id: Union[str, int, None]=None, bot_names: Optional[set]=None) -> bool:
    if bot_id is not None and str(user_id or '').strip() == str(bot_id).strip():
        return True
    sender = str(sender_name or '').strip().casefold()
    if sender and bot_names:
        return sender in {str(n).strip().casefold() for n in bot_names if str(n).strip()}
    return False

def is_system_feed_message(text: str, msg_type: Union[int, str, None]=None) -> bool:
    raw = str(text or '').strip()
    if raw.startswith('{"feedType"'):
        return True
    try:
        t = int(msg_type)
    except (TypeError, ValueError):
        return False
    return normalized_msg_type(t) in {0}

def normalized_msg_type(msg_type: int) -> int:
    try:
        t = int(msg_type)
    except (TypeError, ValueError):
        return 0
    return t % 16384 if t >= 16384 else t

def resolve_message_type(*names: str, fallback: MessageType=MessageType.TEXT) -> MessageType:
    for name in names:
        member = getattr(MessageType, name, None)
        if member is not None:
            return member
    return fallback

def is_reply_message(msg_type: int, attachment: Union[dict, str, None]) -> bool:
    att = parse_attachment_dict(attachment)
    if att and att.get('src_logId') not in (None, ''):
        return True
    return normalized_msg_type(msg_type) in REPLY_MESSAGE_TYPES

def extract_src_log_id(attachment: Union[dict, str, None]) -> Optional[str]:
    att = parse_attachment_dict(attachment)
    if not att:
        return None
    src = att.get('src_logId')
    if src in (None, ''):
        return None
    return str(src)

def append_reply_note(existing: str, note: str) -> str:
    if not note:
        return existing or ''
    if not existing:
        return note
    return f'{existing}\n\n{note}'

def normalize_kakao_url(url: str) -> str:
    u = str(url).strip()
    if not u:
        return ''
    if u.startswith('//'):
        return 'https:' + u
    if u.startswith('/'):
        return 'https://dn-m.talk.kakao.com' + u
    if not u.startswith(('http://', 'https://')):
        return 'https://dn-m.talk.kakao.com/' + u.lstrip('/')
    return u

def is_remote_url(path_or_url: str) -> bool:
    s = str(path_or_url or '').strip()
    return s.startswith(('http://', 'https://', '//'))

def parse_v_dict(v: Union[dict, str, None]) -> Optional[dict]:
    if not v:
        return None
    if isinstance(v, str):
        raw = v.strip()
        if not raw or raw == '{}':
            return None
        try:
            v = json.loads(raw)
        except Exception:
            return None
    return v if isinstance(v, dict) else None

def extract_v_origin(v: Union[dict, str, None]) -> str:
    parsed = parse_v_dict(v)
    if not parsed:
        return ''
    origin = parsed.get('origin')
    return str(origin).strip().upper() if origin not in (None, '') else ''

def extract_v_enc(v: Union[dict, str, None]) -> Optional[int]:
    parsed = parse_v_dict(v)
    if not parsed:
        return None
    try:
        return int(parsed.get('enc'))
    except (TypeError, ValueError):
        return None

def should_skip_by_v_origin(v: Union[dict, str, None]) -> bool:
    return extract_v_origin(v) in V_SKIP_ORIGINS

def should_skip_self_by_v_origin(v: Union[dict, str, None]) -> bool:
    return extract_v_origin(v) in V_SELF_ORIGINS

def predict_action_from_row(v: Union[dict, str, None], msg_type: Union[int, str, None], message: str='', attachment: Union[dict, str, None]=None) -> str:
    origin = extract_v_origin(v)
    origin_action = V_ORIGIN_ACTIONS.get(origin)
    if origin_action in {'SKIP_SYNC', 'SKIP_SELF'}:
        return origin_action
    norm_type = normalized_msg_type(int(msg_type or 0))
    text = str(message or '')
    if is_cr_command(text):
        return 'ROOM_SHOW_ID'
    if is_adcr_command(text):
        return 'ROOM_REGISTER'
    if is_reply_message(norm_type, attachment):
        return 'RESOLVE_REPLY'
    if is_system_feed_message(text, norm_type):
        return 'PARSE_FEED'
    if norm_type == KAKAO_TEXT_TYPE:
        if should_fetch_long_message_text(text, attachment, norm_type):
            return 'FETCH_LONG_TEXT'
        return 'INBOUND_TEXT'
    if is_image_message_type(norm_type):
        return 'ANALYZE_IMAGE'
    if is_file_message_type(norm_type):
        return 'ANALYZE_FILE'
    if is_video_message_type(norm_type):
        return 'ANALYZE_VIDEO'
    if is_audio_message_type(norm_type):
        return 'ANALYZE_AUDIO'
    if origin_action == 'ROUTE_BY_TYPE':
        return 'INBOUND_GENERIC'
    return 'INBOUND_GENERIC'

def parse_attachment_dict(attachment: Union[dict, str, None]) -> Optional[dict]:
    if not attachment:
        return None
    if isinstance(attachment, str):
        try:
            attachment = json.loads(attachment)
        except Exception:
            return None
    return attachment if isinstance(attachment, dict) else None

def is_file_message_type(msg_type: int) -> bool:
    try:
        t = int(msg_type)
    except (TypeError, ValueError):
        return False
    return normalized_msg_type(t) in FILE_MESSAGE_TYPES

def is_image_message_type(msg_type: int) -> bool:
    try:
        t = int(msg_type)
    except (TypeError, ValueError):
        return False
    return normalized_msg_type(t) in IMAGE_MESSAGE_TYPES

def is_video_message_type(msg_type: int) -> bool:
    try:
        t = int(msg_type)
    except (TypeError, ValueError):
        return False
    return normalized_msg_type(t) in VIDEO_MESSAGE_TYPES

def is_audio_message_type(msg_type: int) -> bool:
    try:
        t = int(msg_type)
    except (TypeError, ValueError):
        return False
    return normalized_msg_type(t) in AUDIO_MESSAGE_TYPES

def extract_media_url_from_attachment(attachment: Union[dict, str, None], *, keys: tuple[str, ...]=('url', 'path', 'videoUrl', 'audioUrl')) -> str:
    att = parse_attachment_dict(attachment)
    if not att:
        return ''
    for key in keys:
        raw = att.get(key)
        if raw:
            return normalize_kakao_url(str(raw))
    return ''

def extract_video_attachment(attachment: Union[dict, str, None], msg_type: int=0) -> Optional[dict]:
    if not is_video_message_type(msg_type):
        return None
    url = extract_media_url_from_attachment(attachment)
    if not url:
        return None
    att = parse_attachment_dict(attachment) or {}
    return {'type': 'video', 'url': url, 'content_type': att.get('mimetype') or att.get('content_type') or 'video/mp4'}

def extract_audio_attachment(attachment: Union[dict, str, None], msg_type: int=0) -> Optional[dict]:
    if not is_audio_message_type(msg_type):
        return None
    url = extract_media_url_from_attachment(attachment, keys=('url', 'path', 'audioUrl'))
    if not url:
        return None
    att = parse_attachment_dict(attachment) or {}
    return {'type': 'audio', 'url': url, 'content_type': att.get('mimetype') or att.get('content_type') or 'audio/mpeg'}

def extract_file_attachment(attachment: Union[dict, str, None], msg_type: int=0) -> Optional[dict]:
    if not is_file_message_type(msg_type):
        return None
    att = parse_attachment_dict(attachment)
    if not att:
        return None
    filename = att.get('name') or att.get('filename') or 'file'
    url = att.get('url') or att.get('path') or ''
    if url:
        url = normalize_kakao_url(url)
    return {'type': 'file', 'filename': str(filename), 'url': url, 'size': att.get('size'), 'content_type': att.get('mimetype') or att.get('content_type') or 'application/octet-stream'}

def should_fetch_long_message_text(text: str, attachment: Union[dict, str, None], msg_type: int=0) -> bool:
    if len(str(text or '')) < LONG_MESSAGE_MIN_CHARS:
        return False
    if normalized_msg_type(int(msg_type or 0)) != KAKAO_TEXT_TYPE:
        return False
    att = parse_attachment_dict(attachment)
    if not att:
        return False
    path = att.get('path')
    return bool(path)

def long_message_cdn_url(attachment: Union[dict, str, None]) -> str:
    att = parse_attachment_dict(attachment)
    if not att:
        return ''
    path = att.get('path')
    if not path:
        return ''
    return normalize_kakao_url(str(path))

def extract_image_urls(attachment: Union[dict, str, None], msg_type: int=0) -> List[str]:
    if is_file_message_type(msg_type):
        return []
    att = parse_attachment_dict(attachment)
    if not att:
        return []
    norm_type = normalized_msg_type(int(msg_type)) if msg_type not in (None, '') else 0
    urls: List[str] = []
    try:
        if norm_type == 71:
            thl = att.get('C', {}).get('THL', []) or []
            for item in thl:
                if isinstance(item, dict):
                    thu = item.get('TH', {}).get('THU')
                    if thu:
                        urls.append(thu)
        elif norm_type == 27:
            image_urls = att.get('imageUrls') or []
            for u in image_urls:
                if u:
                    urls.append(u)
        else:
            url = att.get('url')
            if url:
                urls.append(url)
            elif 'path' in att and is_image_message_type(int(msg_type or 0)):
                urls.append(att['path'])
    except Exception as e:
        logger.debug('Iris: failed to extract image urls: %s', e)
    cleaned = []
    for u in urls:
        u = str(u).strip()
        if u.startswith('//'):
            u = 'https:' + u
        if u:
            cleaned.append(u)
    return cleaned

def chat_log_row_to_reply_context(row: dict) -> Dict[str, Any]:
    msg_id = str(row.get('id') or '')
    text = str(row.get('message') or '').strip()
    mtype = row.get('type') or 0
    att = row.get('attachment')
    quoted_media_urls: List[str] = []
    quoted_media_kinds: List[str] = []
    quoted_media_names: List[str] = []
    quoted_media_types: List[str] = []
    file_att = extract_file_attachment(att, mtype)
    if file_att and file_att.get('url'):
        quoted_media_urls.append(file_att['url'])
        quoted_media_kinds.append('file')
        quoted_media_names.append(str(file_att.get('filename') or 'file'))
        quoted_media_types.append(str(file_att.get('content_type') or 'application/octet-stream'))
        if not text:
            text = f"[파일: {file_att.get('filename', 'file')}]"
    else:
        image_urls = extract_image_urls(att, mtype)
        quoted_media_urls.extend(image_urls)
        quoted_media_kinds.extend(['image'] * len(image_urls))
        quoted_media_names.extend([f'image_{i + 1}' for i in range(len(image_urls))])
        quoted_media_types.extend(['image/jpeg'] * len(image_urls))
    return {'reply_to_message_id': msg_id, 'reply_to_text': text or None, 'quoted_media_urls': quoted_media_urls, 'quoted_media_kinds': quoted_media_kinds, 'quoted_media_names': quoted_media_names, 'quoted_media_types': quoted_media_types}

def append_attachment_context_note(event: MessageEvent, json_row: dict, *, cache_failed_urls: Optional[List[str]]=None) -> None:
    try:
        norm = normalized_msg_type(int(json_row.get('type') or 0))
    except (TypeError, ValueError):
        norm = 0
    text_type = getattr(MessageType, 'TEXT', None)
    is_plain_text = norm == KAKAO_TEXT_TYPE and event.message_type == text_type and (not (event.media_urls or [])) and (not cache_failed_urls)
    if is_plain_text:
        return
    notes: List[str] = []
    try:
        from tools.credential_files import to_agent_visible_cache_path
    except ImportError:
        to_agent_visible_cache_path = lambda path: path
    for idx, path in enumerate(event.media_urls or []):
        mtype = event.media_types[idx] if idx < len(event.media_types or []) else ''
        visible = path if is_remote_url(path) else to_agent_visible_cache_path(path)
        label = mtype or str(getattr(event, 'message_type', 'media'))
        notes.append(f'[첨부 #{idx + 1} ({label}): {visible}]')
    for url in cache_failed_urls or []:
        notes.append(f'[첨부 다운로드 실패 — URL: {normalize_kakao_url(url)}]')
    att = parse_attachment_dict(json_row.get('attachment'))
    if att and (not event.media_urls) and (not cache_failed_urls):
        raw = json.dumps(att, ensure_ascii=False)
        if len(raw) > MAX_ATTACHMENT_JSON_CHARS:
            raw = raw[:MAX_ATTACHMENT_JSON_CHARS] + '...(truncated)'
        notes.append(f'[Kakao attachment type={norm}: {raw}]')
    if notes:
        block = '\n'.join(notes)
        existing = str(event.text or '').strip()
        event.text = f'{block}\n\n{existing}' if existing else block
