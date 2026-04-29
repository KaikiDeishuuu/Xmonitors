from __future__ import annotations

import re
from .models import DetectionResult, Status


def _find_keyword(text: str, keywords: list[str]) -> str | None:
    lowered = text.lower()
    for keyword in keywords:
        if keyword.lower() in lowered:
            return keyword
    return None


def detect_status(
    content: str,
    positive_keywords: list[str],
    negative_keywords: list[str],
    blocked_keywords: list[str],
    regex: str | None = None,
) -> DetectionResult:
    blocked = _find_keyword(content, blocked_keywords)
    if blocked:
        return DetectionResult(Status.BLOCKED, "blocked_keyword", blocked, f"Matched blocked keyword: {blocked}")

    negative = _find_keyword(content, negative_keywords)
    if negative:
        return DetectionResult(Status.OUT_OF_STOCK, "negative_keyword", negative, f"Matched negative keyword: {negative}")

    positive = _find_keyword(content, positive_keywords)
    if positive:
        return DetectionResult(Status.IN_STOCK, "positive_keyword", positive, f"Matched positive keyword: {positive}")

    if regex:
        try:
            if re.search(regex, content, flags=re.IGNORECASE):
                return DetectionResult(Status.IN_STOCK, "regex", regex, f"Matched regex: {regex}")
        except re.error as exc:
            return DetectionResult(Status.ERROR, "regex_error", regex, f"Invalid regex: {exc}")

    return DetectionResult(Status.UNKNOWN, None, None, "No rules matched")
