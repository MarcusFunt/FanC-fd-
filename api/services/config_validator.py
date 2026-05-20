from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from fan_cfd.config import FanCFDConfig, _convert_legacy_config

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = PROJECT_ROOT / "configs"
CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def list_configs() -> list[dict[str, Any]]:
    configs: list[dict[str, Any]] = []
    for path in sorted(CONFIG_DIR.glob("*.yaml")):
        detail = _metadata_for_path(path)
        configs.append(detail)
    return configs


def get_config(config_id: str) -> dict[str, Any] | None:
    path = _config_path(config_id)
    if path is None or not path.exists():
        return None
    return _detail_for_path(path)


def create_config(
    config_id: str | None,
    yaml_text: str | None,
    data: dict[str, Any] | None,
) -> dict[str, Any] | None:
    payload = _payload_to_yaml(yaml_text, data)
    if payload is None:
        return None

    validation = validate_config_payload(payload, None)
    if not validation["valid"]:
        raise ValueError("Config is not valid.")

    parsed = validation["data"] or {}
    target_id = _slugify(config_id or parsed.get("fan", {}).get("name") or "fan_config")
    path = _unique_config_path(target_id)
    path.write_text(payload, encoding="utf-8")
    return _detail_for_path(path)


def update_config(
    config_id: str,
    yaml_text: str | None,
    data: dict[str, Any] | None,
) -> dict[str, Any] | None:
    path = _config_path(config_id)
    if path is None or not path.exists():
        return None
    payload = _payload_to_yaml(yaml_text, data)
    if payload is None:
        raise ValueError("Config payload is required.")

    validation = validate_config_payload(payload, None)
    if not validation["valid"]:
        raise ValueError("Config is not valid.")

    path.write_text(payload, encoding="utf-8")
    return _detail_for_path(path)


def delete_config(config_id: str) -> bool:
    path = _config_path(config_id)
    if path is None or not path.exists():
        return False
    path.unlink()
    return True


def validate_config_payload(
    yaml_text: str | None,
    data: dict[str, Any] | None,
) -> dict[str, Any]:
    try:
        raw = _payload_to_raw(yaml_text, data)
        if raw is None:
            return {
                "valid": False,
                "errors": [
                    {
                        "loc": [],
                        "path": "",
                        "msg": "Provide yaml_text or data.",
                        "type": "missing_payload",
                    }
                ],
                "data": None,
            }
        raw = _convert_legacy_config(raw)
        config = FanCFDConfig.model_validate(raw)
        return {
            "valid": True,
            "errors": [],
            "data": config.model_dump(mode="json"),
        }
    except yaml.YAMLError as exc:
        return {
            "valid": False,
            "errors": [
                {
                    "loc": [],
                    "path": "",
                    "msg": str(exc),
                    "type": "yaml_error",
                }
            ],
            "data": None,
        }
    except ValidationError as exc:
        return {
            "valid": False,
            "errors": [_format_validation_error(err) for err in exc.errors()],
            "data": None,
        }
    except Exception as exc:
        return {
            "valid": False,
            "errors": [
                {
                    "loc": [],
                    "path": "",
                    "msg": str(exc),
                    "type": exc.__class__.__name__,
                }
            ],
            "data": None,
        }


def config_path_for_id(config_id: str) -> Path:
    path = _config_path(config_id)
    if path is None or not path.exists():
        raise FileNotFoundError(f"Config not found: {config_id}")
    return path


def _detail_for_path(path: Path) -> dict[str, Any]:
    metadata = _metadata_for_path(path)
    yaml_text = path.read_text(encoding="utf-8")
    validation = validate_config_payload(yaml_text, None)
    return {
        **metadata,
        "yaml_text": yaml_text,
        "data": validation["data"],
        "validation_errors": validation["errors"],
    }


def _metadata_for_path(path: Path) -> dict[str, Any]:
    stat = path.stat()
    validation = validate_config_payload(path.read_text(encoding="utf-8"), None)
    fan_name = None
    stages = None
    if validation["valid"] and validation["data"]:
        fan = validation["data"].get("fan", {})
        fan_name = fan.get("name")
        stages = len(fan.get("stages") or [])
    return {
        "id": path.stem,
        "name": path.name,
        "path": str(path),
        "size_bytes": stat.st_size,
        "updated_at": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
        "fan_name": fan_name,
        "stages": stages,
        "valid": validation["valid"],
    }


def _payload_to_raw(
    yaml_text: str | None,
    data: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if data is not None:
        return data
    if yaml_text is None:
        return None
    raw = yaml.safe_load(yaml_text)
    if raw is None:
        raise ValueError("Config YAML is empty.")
    if not isinstance(raw, dict):
        raise ValueError("Config YAML must contain an object at the root.")
    return raw


def _payload_to_yaml(
    yaml_text: str | None,
    data: dict[str, Any] | None,
) -> str | None:
    if yaml_text is not None:
        return yaml_text
    if data is not None:
        return yaml.safe_dump(data, sort_keys=False)
    return None


def _format_validation_error(err: dict[str, Any]) -> dict[str, Any]:
    loc = list(err.get("loc") or [])
    return {
        "loc": loc,
        "path": ".".join(str(item) for item in loc),
        "msg": err.get("msg", "Validation error"),
        "type": err.get("type"),
    }


def _config_path(config_id: str) -> Path | None:
    if not config_id:
        return None
    slug = _slugify(config_id)
    path = (CONFIG_DIR / f"{slug}.yaml").resolve()
    config_root = CONFIG_DIR.resolve()
    if path.parent != config_root:
        return None
    return path


def _unique_config_path(base_id: str) -> Path:
    base_id = _slugify(base_id)
    path = CONFIG_DIR / f"{base_id}.yaml"
    if not path.exists():
        return path
    idx = 2
    while True:
        candidate = CONFIG_DIR / f"{base_id}_{idx}.yaml"
        if not candidate.exists():
            return candidate
        idx += 1


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "_", value.strip()).strip("_").lower()
    return slug or "fan_config"
