from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
import shutil
import tempfile


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_state(path: str, logger) -> dict:
    state_file = Path(path)
    if not state_file.exists():
        state_file.parent.mkdir(parents=True, exist_ok=True)
        state_file.write_text("{}", encoding="utf-8")
        return {}
    try:
        return json.loads(state_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        backup = state_file.with_suffix(state_file.suffix + ".bak")
        shutil.copy2(state_file, backup)
        logger.error("Invalid state JSON backed up to %s", backup)
        state_file.write_text("{}", encoding="utf-8")
        return {}


def save_state_atomic(path: str, state: dict) -> None:
    state_file = Path(path)
    state_file.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=state_file.parent) as tmp:
        json.dump(state, tmp, indent=2)
        tmp.flush()
        temp_name = tmp.name
    Path(temp_name).replace(state_file)
