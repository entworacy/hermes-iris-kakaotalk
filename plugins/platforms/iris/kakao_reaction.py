from __future__ import annotations
import logging
import time
from typing import Any, Dict, Optional, Tuple
import httpx
logger = logging.getLogger(__name__)
KAKAO_REACT_HOST = 'talk-pilsner.kakao.com'
REACTION_CHECK = 3
DEFAULT_TALK_VERSION = '26.1.0'
DEFAULT_OKHTTP_VERSION = '4.10.0'
AOT_CACHE_TTL_SECONDS = 300

def parse_aot_payload(body: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
    if not isinstance(body, dict):
        return (None, None)
    aot = body.get('aot')
    if not isinstance(aot, dict):
        aot = body
    token = str(aot.get('access_token') or '').strip() or None
    device_uuid = str(aot.get('d_id') or aot.get('deviceUUID') or '').strip() or None
    return (token, device_uuid)

def build_reaction_authorization(access_token: str, device_uuid: str) -> str:
    return f'{access_token}-{device_uuid}'

def build_reaction_headers(access_token: str, device_uuid: str, *, talk_version: str=DEFAULT_TALK_VERSION, okhttp_version: str=DEFAULT_OKHTTP_VERSION) -> Dict[str, str]:
    return {'Authorization': build_reaction_authorization(access_token, device_uuid), 'talk-agent': f'android/{talk_version}', 'talk-language': 'ko', 'Content-Type': 'application/json; charset=UTF-8', 'User-Agent': f'okhttp/{okhttp_version}', 'Host': KAKAO_REACT_HOST}

def build_reaction_body(log_id: str, *, reaction_type: int=REACTION_CHECK, link_id: Optional[int]=None, req_id: Optional[int]=None) -> Dict[str, Any]:
    body: Dict[str, Any] = {'logId': int(log_id), 'reqId': int(req_id if req_id is not None else time.time() * 1000), 'type': int(reaction_type)}
    if link_id is not None:
        body['linkId'] = int(link_id)
    return body

async def fetch_aot_credentials(base_url: str, *, client: Optional[httpx.AsyncClient]=None) -> Tuple[Optional[str], Optional[str]]:
    url = f"{base_url.rstrip('/')}/aot"
    try:
        if client is None:
            async with httpx.AsyncClient(timeout=15) as owned:
                resp = await owned.get(url)
        else:
            resp = await client.get(url)
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, dict) and data.get('success') is False:
            logger.warning('Iris /aot returned success=false')
            return (None, None)
        return parse_aot_payload(data if isinstance(data, dict) else {})
    except Exception as e:
        logger.warning('Iris /aot fetch failed: %s', e)
        return (None, None)

async def send_kakao_reaction(channel_id: str, log_id: str, access_token: str, device_uuid: str, *, reaction_type: int=REACTION_CHECK, link_id: Optional[int]=None, talk_version: str=DEFAULT_TALK_VERSION, okhttp_version: str=DEFAULT_OKHTTP_VERSION, client: Optional[httpx.AsyncClient]=None) -> bool:
    if not channel_id or not log_id or (not access_token) or (not device_uuid):
        return False
    path = f'/messaging/chats/{channel_id}/bubble/reactions'
    headers = build_reaction_headers(access_token, device_uuid, talk_version=talk_version, okhttp_version=okhttp_version)
    payload = build_reaction_body(log_id, reaction_type=reaction_type, link_id=link_id)
    url = f'https://{KAKAO_REACT_HOST}{path}'
    try:
        if client is None:
            async with httpx.AsyncClient(timeout=15) as owned:
                resp = await owned.post(url, headers=headers, json=payload)
        else:
            resp = await client.post(url, headers=headers, json=payload)
        if resp.status_code >= 300:
            logger.warning('Kakao reaction failed: chat=%s log=%s status=%s body=%s', channel_id, log_id, resp.status_code, resp.text[:200])
            return False
        data = resp.json() if resp.content else {}
        if isinstance(data, dict) and data.get('result') is True:
            return True
        if isinstance(data, dict) and data.get('status'):
            logger.warning('Kakao reaction rejected: chat=%s log=%s body=%s', channel_id, log_id, resp.text[:200])
            return False
        return True
    except Exception as e:
        logger.warning('Kakao reaction error chat=%s log=%s: %s', channel_id, log_id, e)
        return False
