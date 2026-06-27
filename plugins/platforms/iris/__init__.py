from pathlib import Path
from .adapter import register as _register_platform
from .skills_install import install_bundled_skills, register_plugin_skills

def register(ctx) -> None:
    install_bundled_skills()
    register_plugin_skills(ctx)
    _register_platform(ctx)
