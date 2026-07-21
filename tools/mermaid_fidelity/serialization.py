"""Stable, deterministic JSON serialization for fidelity observations.

Serialization contract:
- Stable key ordering (alphabetical at each level).
- Deterministic collection ordering (lists preserve semantic order; sets → sorted).
- Floats rounded to FLOAT_PRECISION decimal places.
- UTF-8 encoding.
- Final newline.
- No absolute repository paths (Path objects use as_posix()).
- capture_timestamp is excluded when for_fingerprint=True.
"""
from __future__ import annotations

import json
from dataclasses import fields, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any

FLOAT_PRECISION = 4

_EXCLUDED_FROM_FINGERPRINT: frozenset[str] = frozenset({"capture_timestamp"})


def _normalize_float(v: float) -> float:
    return round(v, FLOAT_PRECISION)


def _to_json_value(obj: Any) -> Any:
    """Recursively convert obj to a JSON-serializable structure."""
    if obj is None:
        return None
    if isinstance(obj, bool):
        return obj
    if isinstance(obj, int):
        return obj
    if isinstance(obj, float):
        return _normalize_float(obj)
    if isinstance(obj, str):
        return obj
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, Path):
        return obj.as_posix()
    if isinstance(obj, (list, tuple)):
        return [_to_json_value(item) for item in obj]
    if isinstance(obj, dict):
        return {str(k): _to_json_value(v) for k, v in sorted(obj.items())}
    if is_dataclass(obj):
        return _dataclass_to_dict(obj)
    raise TypeError(f"Cannot serialize {type(obj)!r}: {obj!r}")


def _dataclass_to_dict(obj: Any) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for f in fields(obj):
        result[f.name] = _to_json_value(getattr(obj, f.name))
    return dict(sorted(result.items()))


def to_json(obj: Any, *, indent: int = 2, for_fingerprint: bool = False) -> str:
    """Serialize obj to a stable JSON string with a trailing newline.

    When for_fingerprint=True, excludes fields in _EXCLUDED_FROM_FINGERPRINT
    from top-level dict objects (typically Observation).
    """
    value = _to_json_value(obj)
    if for_fingerprint and isinstance(value, dict):
        value = {k: v for k, v in value.items() if k not in _EXCLUDED_FROM_FINGERPRINT}
    return json.dumps(value, indent=indent, ensure_ascii=False, sort_keys=True) + "\n"


def load_json(path: Path) -> Any:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_json(obj: Any, path: Path, *, indent: int = 2) -> None:
    """Write obj as stable JSON to path, creating parent dirs as needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(to_json(obj, indent=indent), encoding="utf-8")


def observation_fingerprint(obs: Any) -> str:
    """Return stable SHA256 of the observation excluding capture_timestamp."""
    import hashlib
    data = to_json(obs, for_fingerprint=True)
    return hashlib.sha256(data.encode("utf-8")).hexdigest()
