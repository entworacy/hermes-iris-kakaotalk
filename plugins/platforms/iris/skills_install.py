from __future__ import annotations
import logging
import shutil
from pathlib import Path
from typing import Iterable, List
logger = logging.getLogger(__name__)
PLUGIN_ROOT = Path(__file__).resolve().parent
BUNDLED_SKILLS_DIR = PLUGIN_ROOT / 'skills'
DEFAULT_AUTO_SKILLS = ('iris-chat-assistant',)

def bundled_skill_names() -> List[str]:
    if not BUNDLED_SKILLS_DIR.is_dir():
        return []
    names: List[str] = []
    for child in sorted(BUNDLED_SKILLS_DIR.iterdir()):
        if child.is_dir() and (child / 'SKILL.md').is_file():
            names.append(child.name)
    return names

def _hermes_skills_dir() -> Path:
    import os
    home = Path(os.getenv('HERMES_HOME', os.path.expanduser('~/.hermes')))
    skills = home / 'skills'
    skills.mkdir(parents=True, exist_ok=True)
    return skills

def install_bundled_skills(*, force: bool=False) -> List[str]:
    installed: List[str] = []
    target_root = _hermes_skills_dir()
    for name in bundled_skill_names():
        src = BUNDLED_SKILLS_DIR / name
        dest = target_root / name
        if dest.exists() and (not force):
            logger.debug("Iris: skill '%s' already present at %s", name, dest)
            continue
        if dest.exists() and force:
            shutil.rmtree(dest)
        shutil.copytree(src, dest)
        installed.append(name)
        logger.info("Iris: installed skill '%s' -> %s", name, dest)
    return installed

def register_plugin_skills(ctx) -> None:
    for name in bundled_skill_names():
        skill_md = BUNDLED_SKILLS_DIR / name / 'SKILL.md'
        ctx.register_skill(name, skill_md)

def parse_auto_skills(raw: str | Iterable[str] | None) -> List[str]:
    if raw is None:
        return list(DEFAULT_AUTO_SKILLS)
    if isinstance(raw, str):
        items = [part.strip() for part in raw.split(',') if part.strip()]
        return items or list(DEFAULT_AUTO_SKILLS)
    try:
        items = [str(x).strip() for x in raw if str(x).strip()]
    except TypeError:
        return list(DEFAULT_AUTO_SKILLS)
    return items or list(DEFAULT_AUTO_SKILLS)
