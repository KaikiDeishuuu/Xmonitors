#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import logging
import random
import re
import signal
import sys
import time
from html import escape
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Tuple

import requests
from bs4 import BeautifulSoup


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_CONFIG_PATH = BASE_DIR / "config.json"
DEFAULT_STATE_PATH = BASE_DIR / "state.json"
LOG_DIR = BASE_DIR / "logs"
LOG_FILE = LOG_DIR / "stock-monitor.log"

STATE_IN_STOCK = "IN_STOCK"
STATE_OUT_OF_STOCK = "OUT_OF_STOCK"

STATE_LABELS = {
    STATE_IN_STOCK: "In stock",
    STATE_OUT_OF_STOCK: "Out of stock",
}

POSITIVE_PHRASES = (
    "order now",
    "configure",
    "add to cart",
    "in stock",
    "available",
)

NEGATIVE_PHRASES = (
    "sold out",
    "out of stock",
    "unavailable",
    "coming soon",
    "temporarily unavailable",
    "no stock",
)


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def setup_logging() -> logging.Logger:
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("stock-monitor")
    logger.setLevel(logging.INFO)
    logger.propagate = False

    if not logger.handlers:
        formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")

        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)

        file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


def load_json_file(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def atomic_write_json(path: Path, payload: Any) -> None:
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False, sort_keys=True)
        handle.write("\n")
    tmp_path.replace(path)


def state_label(state: str) -> str:
    return STATE_LABELS.get(state, state.replace("_", " ").title())


def normalize_product(product: Dict[str, Any], monitor_cfg: Dict[str, Any]) -> Dict[str, Any]:
    normalized = dict(product)
    normalized["interval_seconds"] = int(
        normalized.get("interval_seconds") or monitor_cfg.get("default_interval_seconds", 10)
    )
    normalized["jitter_seconds"] = int(monitor_cfg.get("jitter_seconds", 0))
    normalized["initial_state"] = normalized.get("initial_state", STATE_OUT_OF_STOCK)
    return normalized


def initialize_state(config: Dict[str, Any], state_path: Path, logger: logging.Logger) -> Dict[str, Any]:
    current_state = load_json_file(state_path)
    if isinstance(current_state, dict) and isinstance(current_state.get("products"), dict):
        products_state = current_state["products"]
    else:
        products_state = {}

    changed = False
    seed_time = now_iso()
    for product in config.get("products", []):
        product_id = product["id"]
        if product_id not in products_state:
            initial_state = product.get("initial_state", STATE_OUT_OF_STOCK)
            products_state[product_id] = {
                "state": initial_state,
                "status_label": state_label(initial_state),
                "last_checked_at": None,
                "last_changed_at": seed_time,
                "last_notified_at": None,
                "evidence": "Initialized from config",
                "url": product.get("primary_url", ""),
            }
            changed = True

    state = {"products": products_state}
    if not state_path.exists() or changed:
        atomic_write_json(state_path, state)
        logger.info("State file initialized at %s", state_path)
    return state


def extract_visible_text(soup: BeautifulSoup) -> str:
    pieces = [piece.strip() for piece in soup.stripped_strings if piece.strip()]
    return " ".join(pieces)


def normalize_text(text: str) -> str:
    return " ".join(text.split()).lower()


def element_texts(soup: BeautifulSoup) -> Iterable[str]:
    for tag_name in ("button", "a", "input", "strong", "span"):
        for node in soup.find_all(tag_name):
            if tag_name == "input":
                value = node.get("value") or node.get("aria-label") or ""
                if value:
                    yield str(value)
            else:
                text = node.get_text(" ", strip=True)
                if text:
                    yield text


def classify_stock(html: str, product: Dict[str, Any]) -> Tuple[str, str]:
    soup = BeautifulSoup(html, "html.parser")
    visible_text = extract_visible_text(soup)
    normalized_text = normalize_text(visible_text)

    for match in re.finditer(r"\b([1-9]\d*)\s+available\b", normalized_text):
        amount = int(match.group(1))
        if amount > 0:
            return STATE_IN_STOCK, f"WHMCS-style availability count found: {amount} Available"

    for snippet in element_texts(soup):
        normalized_snippet = normalize_text(snippet)
        for phrase in POSITIVE_PHRASES:
            if phrase in normalized_snippet:
                return STATE_IN_STOCK, f'Positive stock evidence found: "{snippet.strip()}"'

    for phrase in POSITIVE_PHRASES:
        if phrase in normalized_text:
            return STATE_IN_STOCK, f'Positive stock evidence found: "{phrase}"'

    for phrase in NEGATIVE_PHRASES:
        if phrase in normalized_text:
            return STATE_OUT_OF_STOCK, f'Negative stock evidence found: "{phrase}"'

    return STATE_OUT_OF_STOCK, "No strong positive stock evidence found"


def fetch_product_html(session: requests.Session, product: Dict[str, Any], request_cfg: Dict[str, Any]) -> str:
    headers = {"User-Agent": request_cfg.get("user_agent", "Mozilla/5.0 stock-monitor/1.0")}
    timeout = int(request_cfg.get("timeout_seconds", 6))
    response = session.get(product["primary_url"], headers=headers, timeout=timeout)
    response.raise_for_status()
    return response.text


def telegram_enabled(config: Dict[str, Any]) -> bool:
    telegram_cfg = config.get("telegram", {})
    token = str(telegram_cfg.get("bot_token", ""))
    chat_id = str(telegram_cfg.get("chat_id", ""))
    if not token or not chat_id:
        return False
    if token.startswith("PUT_YOUR_") or chat_id.startswith("PUT_YOUR_"):
        return False
    return True


def send_telegram_notification(session: requests.Session, config: Dict[str, Any], message: str, logger: logging.Logger) -> bool:
    if not telegram_enabled(config):
        logger.info("Telegram credentials are placeholders; notification skipped.")
        return False

    telegram_cfg = config["telegram"]
    endpoint = f"https://api.telegram.org/bot{telegram_cfg['bot_token']}/sendMessage"
    payload = {
        "chat_id": telegram_cfg["chat_id"],
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    try:
        response = session.post(endpoint, json=payload, timeout=int(config.get("request", {}).get("timeout_seconds", 6)))
        response.raise_for_status()
    except requests.RequestException as exc:
        logger.warning("Telegram notification failed: %s", exc)
        return False
    return True


def html_value(value: Any) -> str:
    return escape(str(value), quote=True)


def build_notification_message(
    product: Dict[str, Any],
    status: str,
    evidence: str,
    checked_at: str,
    previous_state: str | None = None,
) -> str:
    display_name = html_value(product.get("display_name", product["id"]))
    provider = html_value(product.get("provider", "stock-monitor"))
    category = html_value(product.get("category", "-"))
    product_title = html_value(product.get("product_title", "-"))
    price_line = html_value(product.get("price_line", "-"))
    spec_line = html_value(product.get("spec_line", "-"))
    region_line = html_value(product.get("region_line", "-"))
    evidence_line = html_value(evidence)
    status_label_html = html_value(state_label(status))
    checked_at_html = html_value(checked_at)
    url = html_value(product.get("primary_url", ""))

    header = f"<b>stock-monitor</b> | <b>{display_name}</b>"
    state_line = f"<b>Status:</b> <code>{html_value(status)}</code> ({status_label_html})"
    lines = [
        header,
        state_line,
        f"<b>Provider:</b> {provider}",
        f"<b>Category:</b> {category}",
        f"<b>Product:</b> {product_title}",
        f"<b>Price:</b> {price_line}",
        f"<b>Spec:</b> {spec_line}",
        f"<b>Region:</b> {region_line}",
    ]

    if previous_state:
        lines.append(
            f"<b>Changed:</b> <code>{html_value(previous_state)}</code> -> <code>{html_value(status)}</code>"
        )

    lines.extend(
        [
            f"<b>Evidence:</b> {evidence_line}",
            f"<b>Checked:</b> {checked_at_html}",
            f'<b>URL:</b> <a href="{url}">Open product page</a>' if url else "<b>URL:</b> -",
        ]
    )
    return "\n".join(lines)


def update_product_state(
    state: Dict[str, Any],
    product: Dict[str, Any],
    new_state: str,
    evidence: str,
    checked_at: str,
) -> Tuple[bool, Dict[str, Any]]:
    product_state = state["products"].setdefault(
        product["id"],
        {
            "state": product.get("initial_state", STATE_OUT_OF_STOCK),
            "status_label": state_label(product.get("initial_state", STATE_OUT_OF_STOCK)),
            "last_checked_at": None,
            "last_changed_at": checked_at,
            "last_notified_at": None,
            "evidence": "Initialized from config",
            "url": product.get("primary_url", ""),
        },
    )

    previous_state = product_state.get("state")
    product_state["last_checked_at"] = checked_at
    product_state["status_label"] = state_label(new_state)
    product_state["evidence"] = evidence
    product_state["url"] = product.get("primary_url", "")

    changed = previous_state != new_state
    if changed:
        product_state["state"] = new_state
        product_state["last_changed_at"] = checked_at

    return changed, product_state


def should_notify_first_observation(config: Dict[str, Any], new_state: str) -> bool:
    monitor_cfg = config.get("monitor", {})
    if new_state == STATE_IN_STOCK:
        return bool(monitor_cfg.get("notify_on_first_in_stock", True))
    if new_state == STATE_OUT_OF_STOCK:
        return bool(monitor_cfg.get("notify_on_first_out_of_stock", False))
    return False


def check_product(
    session: requests.Session,
    config: Dict[str, Any],
    state: Dict[str, Any],
    state_path: Path,
    product: Dict[str, Any],
    logger: logging.Logger,
) -> None:
    previous_record = state["products"].get(product["id"], {})
    first_observation = previous_record.get("last_checked_at") is None
    previous_state = previous_record.get("state")
    checked_at = now_iso()

    try:
        html = fetch_product_html(session, product, config.get("request", {}))
    except requests.RequestException as exc:
        logger.warning("Fetch failed for %s: %s", product["id"], exc)
        return

    new_state, evidence = classify_stock(html, product)
    changed, product_state = update_product_state(state, product, new_state, evidence, checked_at)
    atomic_write_json(state_path, state)

    logger.info("Checked %s -> %s (%s)", product["id"], product_state["status_label"], evidence)

    notify = changed or (first_observation and should_notify_first_observation(config, new_state))
    if not notify:
        return

    message = build_notification_message(product, new_state, evidence, checked_at, previous_state)
    if send_telegram_notification(session, config, message, logger):
        product_state["last_notified_at"] = now_iso()
        atomic_write_json(state_path, state)


def compute_next_run(now_monotonic: float, product: Dict[str, Any]) -> float:
    interval = int(product.get("interval_seconds", 10))
    jitter = int(product.get("jitter_seconds", 0))
    jitter_offset = random.uniform(-jitter, jitter) if jitter > 0 else 0.0
    return now_monotonic + max(1.0, interval + jitter_offset)


def run_monitor(config: Dict[str, Any], state: Dict[str, Any], state_path: Path, logger: logging.Logger) -> None:
    session = requests.Session()
    products = [normalize_product(product, config.get("monitor", {})) for product in config.get("products", [])]
    next_runs = {product["id"]: time.monotonic() for product in products}

    stop_requested = {"value": False}

    def handle_stop(signum: int, frame: Any) -> None:
        stop_requested["value"] = True
        logger.info("Stop signal received, shutting down after current cycle.")

    signal.signal(signal.SIGINT, handle_stop)
    signal.signal(signal.SIGTERM, handle_stop)

    logger.info("Stock monitor started with %d products.", len(products))

    while not stop_requested["value"]:
        now_monotonic = time.monotonic()
        due_products = [product for product in products if now_monotonic >= next_runs[product["id"]]]

        if not due_products:
            sleep_for = min(1.0, max(0.1, min(next_runs.values()) - now_monotonic)) if next_runs else 1.0
            time.sleep(sleep_for)
            continue

        for product in due_products:
            check_product(session, config, state, state_path, product, logger)
            next_runs[product["id"]] = compute_next_run(time.monotonic(), product)

    logger.info("Stock monitor stopped.")


def load_config(config_path: Path) -> Dict[str, Any]:
    config = load_json_file(config_path)
    if not isinstance(config, dict):
        raise ValueError(f"Config file is invalid: {config_path}")
    return config


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the stock monitor service.")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="Path to config.json")
    parser.add_argument("--state", default=str(DEFAULT_STATE_PATH), help="Path to state.json")
    args = parser.parse_args()

    logger = setup_logging()
    config_path = Path(args.config)
    state_path = Path(args.state)

    try:
        config = load_config(config_path)
    except Exception as exc:  # pragma: no cover - fatal startup path
        logger.error("Failed to load config: %s", exc)
        return 1

    state = initialize_state(config, state_path, logger)

    try:
        run_monitor(config, state, state_path, logger)
    except KeyboardInterrupt:
        logger.info("Interrupted by user.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())