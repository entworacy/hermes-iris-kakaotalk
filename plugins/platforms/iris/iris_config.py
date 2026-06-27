from __future__ import annotations
import logging
from typing import Any, Dict, Optional, Tuple
import httpx
logger = logging.getLogger(__name__)

def parse_iris_config(body: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
    if not isinstance(body, dict):
        return (None, None)
    bot_id_raw = body.get('bot_id')
    bot_id: Optional[str] = None
    if bot_id_raw not in (None, '', 0):
        bot_id = str(bot_id_raw).strip() or None
    bot_name_raw = body.get('bot_name')
    bot_name: Optional[str] = None
    if bot_name_raw not in (None, ''):
        bot_name = str(bot_name_raw).strip() or None
    return (bot_id, bot_name)

async def fetch_iris_config(base_url: str, *, client: Optional[httpx.AsyncClient]=None) -> Tuple[Optional[str], Optional[str]]:
    url = f"{base_url.rstrip('/')}/config"
    try:
        if client is None:
            async with httpx.AsyncClient(timeout=15) as owned:
                resp = await owned.get(url)
        else:
            resp = await client.get(url)
        resp.raise_for_status()
        data = resp.json()
        return parse_iris_config(data if isinstance(data, dict) else {})
    except Exception as e:
        logger.warning('Iris /config fetch failed: %s', e)
        return (None, None)
