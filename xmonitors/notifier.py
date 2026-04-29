from __future__ import annotations

import os
import requests
from .models import Status


EMOJI = {
    Status.IN_STOCK: "🟢",
    Status.OUT_OF_STOCK: "🔴",
    Status.UNKNOWN: "⚪",
    Status.ERROR: "🟠",
    Status.BLOCKED: "🚫",
}


def should_notify(old: Status | None, new: Status, notify_on_error: bool, notify_on_recovery: bool) -> bool:
    if old is None:
        return False
    if old == new:
        return False
    if {old, new} == {Status.OUT_OF_STOCK, Status.IN_STOCK}:
        return True
    if old in (Status.ERROR, Status.BLOCKED) and new == Status.IN_STOCK and notify_on_recovery:
        return True
    if new in (Status.ERROR, Status.BLOCKED):
        return notify_on_error
    return False


def send_telegram(message: str, logger) -> bool:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        logger.warning("Telegram credentials are not set; skipping notification")
        return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        resp = requests.post(url, json={"chat_id": chat_id, "text": message}, timeout=10)
        resp.raise_for_status()
        return True
    except requests.RequestException as exc:
        logger.error("Telegram notification failed: %s", exc)
        return False


def build_message(item_name: str, old, new, checked_at: str, reason: str, url: str, error: str | None = None) -> str:
    title = f"{EMOJI.get(new, 'ℹ️')} Xmonitors: Stock status changed"
    parts = [
        title,
        "",
        f"Item: {item_name}",
        f"Old status: {old}",
        f"New status: {new}",
        f"Checked at: {checked_at}",
        f"Reason: {reason}",
        f"URL: {url}",
    ]
    if error:
        parts.append(f"Error details: {error}")
    return "\n".join(parts)
