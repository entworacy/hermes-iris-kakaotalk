from __future__ import annotations
import logging
from typing import Any, Dict, List, Optional, Union
logger = logging.getLogger(__name__)
REAL_PROFILE_USER_THRESHOLD = 10000000000
OPEN_CHAT_MEMBER_TYPE_QUERY = 'SELECT link_member_type FROM db2.open_chat_member WHERE user_id = ?'
BOT_MEMBER_TYPE_QUERY = 'SELECT T2.link_member_type FROM chat_rooms AS T1 INNER JOIN open_profile AS T2 ON T1.link_id = T2.link_id WHERE T1.id = ?'
OPEN_CHAT_AVATAR_QUERY = 'SELECT original_profile_image_url FROM db2.open_chat_member WHERE user_id = ?'
ROOM_PROFILE_AVATAR_QUERY = 'SELECT T2.o_profile_image_url FROM chat_rooms AS T1 JOIN db2.open_profile AS T2 ON T1.link_id = T2.link_id WHERE T1.id = ?'
MEMBER_TYPE_LABELS = {1: 'HOST', 2: 'NORMAL', 4: 'MANAGER', 8: 'BOT'}

def parse_user_id(user_id: Union[str, int, None]) -> Optional[int]:
    if user_id in (None, ''):
        return None
    try:
        return int(str(user_id).strip())
    except (TypeError, ValueError):
        return None

def is_bot_user(user_id: Union[str, int, None], bot_id: Union[str, int, None]) -> bool:
    uid = parse_user_id(user_id)
    bid = parse_user_id(bot_id)
    return uid is not None and bid is not None and (uid == bid)

def is_real_profile_user(user_id: Union[str, int, None]) -> bool:
    uid = parse_user_id(user_id)
    return uid is not None and uid < REAL_PROFILE_USER_THRESHOLD

def map_link_member_type(raw: Any) -> str:
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return 'UNKNOWN'
    return MEMBER_TYPE_LABELS.get(value, 'UNKNOWN')

def member_type_query_for_user(user_id: Union[str, int, None], chat_id: Union[str, int, None], *, bot_id: Union[str, int, None]=None) -> Optional[tuple[str, List[Any]]]:
    if is_bot_user(user_id, bot_id):
        return (BOT_MEMBER_TYPE_QUERY, [str(chat_id)])
    if is_real_profile_user(user_id):
        return None
    return (OPEN_CHAT_MEMBER_TYPE_QUERY, [str(user_id)])

def avatar_query_for_user(user_id: Union[str, int, None], chat_id: Union[str, int, None]) -> tuple[str, List[Any]]:
    if is_real_profile_user(user_id):
        return (ROOM_PROFILE_AVATAR_QUERY, [str(chat_id)])
    return (OPEN_CHAT_AVATAR_QUERY, [str(user_id)])

def resolve_member_type_from_row(row: Optional[dict]) -> Optional[str]:
    if not row:
        return None
    raw = row.get('link_member_type')
    if raw in (None, ''):
        return None
    return map_link_member_type(raw)

def resolve_avatar_url_from_row(row: Optional[dict], *, real_profile: bool) -> Optional[str]:
    if not row:
        return None
    key = 'o_profile_image_url' if real_profile else 'original_profile_image_url'
    url = row.get(key)
    if not url:
        return None
    return str(url).strip() or None

async def query_sender_member_type(query_fn, *, chat_id: str, user_id: str, bot_id: Optional[str]=None) -> Optional[str]:
    query = member_type_query_for_user(user_id, chat_id, bot_id=bot_id)
    if query is None:
        return None
    sql, bind = query
    rows = await query_fn(sql, bind)
    if not rows:
        return None
    return resolve_member_type_from_row(rows[0])

async def query_sender_avatar_url(query_fn, *, chat_id: str, user_id: str) -> Optional[str]:
    real_profile = is_real_profile_user(user_id)
    sql, bind = avatar_query_for_user(user_id, chat_id)
    rows = await query_fn(sql, bind)
    return resolve_avatar_url_from_row(rows[0] if rows else None, real_profile=real_profile)

async def cache_sender_avatar(cache_fn, *, user_id: str, avatar_url: str) -> Optional[Dict[str, str]]:
    if not avatar_url:
        return None
    display_name = f'avatar_{user_id}.jpg'
    return await cache_fn(avatar_url, display_name=display_name, kind='image', content_type='image/jpeg')
