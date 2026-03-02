from __future__ import annotations

import hashlib
import json
from pathlib import Path


def stable_hash(data: object) -> str:
    blob = json.dumps(data, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def load_json(path: Path) -> object:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def detect_credential_change(previous_hash: str | None, state: object) -> tuple[bool, str]:
    current = stable_hash(state)
    changed = previous_hash is not None and previous_hash != current
    return changed, current
