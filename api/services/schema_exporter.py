from __future__ import annotations

from functools import lru_cache
from typing import Any

from fan_cfd.config import FanCFDConfig


@lru_cache(maxsize=1)
def get_config_schema() -> dict[str, Any]:
    return FanCFDConfig.model_json_schema()

