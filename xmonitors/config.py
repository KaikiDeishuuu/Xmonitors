from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from .models import AppConfig, GlobalConfig, ItemConfig, TelegramConfig


def _load_env_file(path: str = ".env") -> None:
    env_path = Path(path)
    if not env_path.exists():
        return
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def load_config(config_path: str | None = None) -> AppConfig:
    _load_env_file()
    logger = logging.getLogger("xmonitors")
    resolved_path = config_path or os.getenv("XMONITORS_CONFIG", "config.json")
    raw = json.loads(Path(resolved_path).read_text(encoding="utf-8"))

    if "items" not in raw:
        logger.warning("Legacy config format detected; please migrate to new schema")
        item = ItemConfig(
            name=raw.get("name", "Legacy Item"),
            url=raw["url"],
            positive_keywords=raw.get("in_stock_keywords", []),
            negative_keywords=raw.get("out_of_stock_keywords", []),
            blocked_keywords=raw.get("blocked_keywords", []),
        )
        return AppConfig(GlobalConfig(), TelegramConfig(enabled=True), [item])

    g = raw.get("global", {})
    global_cfg = GlobalConfig(**{k: v for k, v in g.items() if k in GlobalConfig.__dataclass_fields__})
    telegram = TelegramConfig(**raw.get("telegram", {}))
    items = [ItemConfig(**item) for item in raw.get("items", [])]
    state_path = raw.get("state_path", "data/state.json")
    return AppConfig(global_cfg, telegram, items, state_path)
