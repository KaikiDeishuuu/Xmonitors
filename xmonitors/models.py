from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class Status(str, Enum):
    IN_STOCK = "IN_STOCK"
    OUT_OF_STOCK = "OUT_OF_STOCK"
    UNKNOWN = "UNKNOWN"
    ERROR = "ERROR"
    BLOCKED = "BLOCKED"


@dataclass
class DetectionResult:
    status: Status
    matched_rule_type: Optional[str] = None
    matched_value: Optional[str] = None
    reason: str = "No matching rule"


@dataclass
class GlobalConfig:
    default_interval_seconds: int = 60
    request_timeout_seconds: int = 15
    max_retries: int = 3
    retry_backoff_seconds: int = 5
    jitter_seconds: int = 5
    user_agent: str = "Xmonitors/1.0"
    notify_on_error: bool = False
    notify_on_recovery: bool = True


@dataclass
class ItemConfig:
    name: str
    url: str
    enabled: bool = True
    interval_seconds: Optional[int] = None
    positive_keywords: list[str] = field(default_factory=list)
    negative_keywords: list[str] = field(default_factory=list)
    blocked_keywords: list[str] = field(default_factory=list)
    regex: Optional[str] = None
    expected_status: str = "auto"
    notify_on_error: Optional[bool] = None


@dataclass
class TelegramConfig:
    enabled: bool = True


@dataclass
class AppConfig:
    global_config: GlobalConfig
    telegram: TelegramConfig
    items: list[ItemConfig]
    state_path: str = "data/state.json"
