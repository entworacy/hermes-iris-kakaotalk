from __future__ import annotations
import base64
import logging
import os
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, Optional
import httpx
from .kakao_payload import normalize_kakao_url
logger = logging.getLogger(__name__)
IMAGE_EXTENSIONS = frozenset({'.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp'})
TEXT_EXTENSIONS = frozenset({'.txt', '.md', '.csv', '.log', '.json', '.xml', '.yaml', '.yml', '.toml', '.ini', '.cfg'})
MAX_INLINE_TEXT_BYTES = 12000

def is_image_path(path: str) -> bool:
    return Path(path).suffix.lower() in IMAGE_EXTENSIONS

def guess_image_ext(url: str) -> str:
    path = str(url).split('?')[0].lower()
    for ext in ('.jpg', '.jpeg', '.png', '.webp', '.gif'):
        if path.endswith(ext):
            return '.jpg' if ext == '.jpeg' else ext
    return '.jpg'

async def fetch_long_message_text(url: str) -> Optional[str]:
    if not url:
        return None
    target = normalize_kakao_url(url) if not str(url).startswith(('http://', 'https://')) else str(url)
    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            resp = await client.get(target, headers={'User-Agent': 'Mozilla/5.0 (compatible; HermesAgent/1.0)', 'Accept': 'text/plain,*/*;q=0.8'})
            resp.raise_for_status()
            resp.encoding = 'utf-8'
            return resp.text
    except Exception as e:
        logger.warning('Iris: failed to fetch long message text %s: %s', url, e)
        return None

async def download_url_bytes(url: str) -> bytes:
    target = normalize_kakao_url(url) if not str(url).startswith(('http://', 'https://')) else str(url)
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        resp = await client.get(target, headers={'User-Agent': 'Mozilla/5.0 (compatible; HermesAgent/1.0)', 'Accept': 'image/*,*/*;q=0.8'})
        resp.raise_for_status()
        return resp.content

async def cache_inbound_media_url(url: str, *, display_name: str='file', kind: str='auto', content_type: str='application/octet-stream') -> Optional[Dict[str, str]]:
    if not url:
        return None
    target = normalize_kakao_url(url) if not str(url).startswith(('http://', 'https://')) else str(url)
    resolved_kind = kind
    if resolved_kind == 'auto':
        if content_type.startswith('image/'):
            resolved_kind = 'image'
        elif content_type.startswith(('application/', 'text/')):
            resolved_kind = 'file'
        else:
            ext = Path(target.split('?')[0]).suffix.lower()
            resolved_kind = 'image' if ext in IMAGE_EXTENSIONS else 'file'
    if resolved_kind == 'file':
        try:
            data = await download_url_bytes(target)
            safe_name = Path(str(display_name or 'file')).name or 'file'
            try:
                from gateway.platforms.base import cache_document_from_bytes
                path = cache_document_from_bytes(data, safe_name)
            except ImportError:
                cache_dir = Path(os.getenv('HERMES_HOME', os.path.expanduser('~/.hermes'))) / 'cache' / 'documents'
                cache_dir.mkdir(parents=True, exist_ok=True)
                filename = f'doc_{os.urandom(6).hex()}_{safe_name}'
                filepath = cache_dir / filename
                filepath.write_bytes(data)
                path = str(filepath)
            return {'path': path, 'kind': 'file', 'display_name': safe_name, 'media_type': content_type or 'application/octet-stream'}
        except Exception as e:
            logger.warning('Iris: failed to cache inbound file %s: %s', url, e)
            return None
    ext = guess_image_ext(target)
    try:
        from gateway.platforms.base import cache_image_from_url
        path = await cache_image_from_url(target, ext=ext)
        return {'path': path, 'kind': 'image', 'display_name': display_name, 'media_type': 'image/jpeg'}
    except ImportError:
        pass
    except Exception as e:
        logger.debug('Iris: cache_image_from_url failed for %s: %s', url, e)
    try:
        data = await download_url_bytes(target)
        try:
            from gateway.platforms.base import cache_image_from_bytes
            path = cache_image_from_bytes(data, ext=ext)
        except ImportError:
            cache_dir = Path(os.getenv('HERMES_HOME', os.path.expanduser('~/.hermes'))) / 'cache' / 'images'
            cache_dir.mkdir(parents=True, exist_ok=True)
            filename = f'iris_{os.urandom(6).hex()}{ext}'
            filepath = cache_dir / filename
            filepath.write_bytes(data)
            path = str(filepath)
        except ValueError as e:
            logger.warning('Iris: inbound media is not a valid image: %s', e)
            return None
        return {'path': path, 'kind': 'image', 'display_name': display_name, 'media_type': 'image/jpeg'}
    except Exception as e:
        logger.warning('Iris: failed to cache inbound image %s: %s', url, e)
        return None

def attachment_to_base64(att: Any) -> Optional[str]:
    if att is None:
        return None
    try:
        if isinstance(att, (bytes, bytearray)):
            return base64.b64encode(att).decode()
        if isinstance(att, str):
            if att.startswith(('http://', 'https://', '//')):
                if att.startswith('//'):
                    att = 'https:' + att
                r = httpx.get(att, timeout=30)
                r.raise_for_status()
                return base64.b64encode(r.content).decode()
            with open(att, 'rb') as f:
                return base64.b64encode(f.read()).decode()
        if isinstance(att, dict):
            url = att.get('url') or att.get('path')
            if url:
                return attachment_to_base64(url)
            if 'data' in att and isinstance(att.get('data'), str):
                data = att['data']
                if ',' in data:
                    data = data.split(',', 1)[1]
                return data
            if 'bytes' in att:
                return base64.b64encode(att['bytes']).decode()
        if hasattr(att, 'read'):
            data = att.read()
            if isinstance(data, str):
                data = data.encode()
            return base64.b64encode(data).decode()
        try:
            from PIL import Image as PILImage
            if isinstance(att, PILImage.Image):
                buf = BytesIO()
                att = att.convert('RGBA') if hasattr(att, 'convert') else att
                att.save(buf, format='PNG')
                return base64.b64encode(buf.getvalue()).decode()
        except Exception:
            pass
    except Exception as e:
        logger.warning('Iris: failed to convert attachment to base64: %s', e)
    return None
