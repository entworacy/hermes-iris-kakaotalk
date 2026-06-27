from __future__ import annotations
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
logger = logging.getLogger(__name__)
CONFIG_ALLOWED_KEY = 'gateway.platforms.iris.extra.allowed_chat_ids'

def resolve_hermes_config_path(explicit: Optional[Union[str, Path]]=None) -> Optional[Path]:
    if explicit:
        return Path(explicit)
    home = Path(os.getenv('HERMES_HOME', os.path.expanduser('~/.hermes')))
    path = home / 'config.yaml'
    return path if path.exists() else None

def persist_allowed_chat_ids(ids: List[str], config_path: Path) -> bool:
    try:
        from utils import atomic_roundtrip_yaml_update
        atomic_roundtrip_yaml_update(config_path, CONFIG_ALLOWED_KEY, ids)
        try:
            os.chmod(config_path, 384)
        except (OSError, NotImplementedError):
            pass
        return True
    except ImportError:
        pass
    except Exception as e:
        logger.error('Iris: failed to persist allowed_chat_ids via utils: %s', e)
        return False
    try:
        import yaml
        config_path.parent.mkdir(parents=True, exist_ok=True)
        data: Dict[str, Any] = {}
        if config_path.exists():
            with open(config_path, encoding='utf-8') as f:
                loaded = yaml.safe_load(f)
                if isinstance(loaded, dict):
                    data = loaded
        gateway = data.setdefault('gateway', {})
        platforms = gateway.setdefault('platforms', {})
        iris = platforms.setdefault('iris', {})
        extra = iris.setdefault('extra', {})
        extra['allowed_chat_ids'] = ids
        with open(config_path, 'w', encoding='utf-8') as f:
            yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)
        return True
    except Exception as e:
        logger.error('Iris: failed to persist allowed_chat_ids: %s', e)
        return False

def register_allowed_chat_id(chat_id: str, *, current_ids: Optional[set]=None, config_path: Optional[Union[str, Path]]=None) -> Tuple[bool, str]:
    cid = str(chat_id or '').strip()
    if not cid:
        return (False, '등록 실패: chat_id가 없습니다.')
    ids = {str(x).strip() for x in current_ids or set() if str(x).strip()}
    if cid in ids:
        return (True, f'이미 등록된 방입니다.\nchat_id: {cid}')
    ids.add(cid)
    sorted_ids = sorted(ids)
    path = resolve_hermes_config_path(config_path)
    if path is not None:
        if not persist_allowed_chat_ids(sorted_ids, path):
            return (False, '등록 실패: 설정 파일 저장에 실패했습니다.')
    return (True, f'등록 완료\nchat_id: {cid}')
