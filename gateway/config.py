from dataclasses import dataclass
from typing import Any, Optional

@dataclass
class Platform:
    name: str

    def __post_init__(self):
        if not isinstance(self.name, str):
            raise TypeError('Platform name must be str')

    @property
    def value(self) -> str:
        return self.name

@dataclass
class PlatformConfig:
    extra: Optional[dict] = None
