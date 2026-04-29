from __future__ import annotations

import argparse
import random
import time
from .config import load_config
from .detector import detect_status
from .fetcher import fetch_with_retries
from .logging_setup import setup_logging
from .models import Status
from .notifier import build_message, send_telegram, should_notify
from .state import load_state, now_iso, save_state_atomic


def run_once(config_path: str | None = None, dry_run: bool = False, check_name: str | None = None) -> None:
    logger = setup_logging()
    cfg = load_config(config_path)
    state = load_state(cfg.state_path, logger)
    logger.info("config_loaded items=%s", len(cfg.items))

    for item in cfg.items:
        if not item.enabled:
            continue
        if check_name and item.name != check_name:
            continue

        logger.info('item_check_started item="%s"', item.name)
        response, error = fetch_with_retries(
            item.url,
            cfg.global_config.request_timeout_seconds,
            cfg.global_config.max_retries,
            cfg.global_config.retry_backoff_seconds,
            cfg.global_config.user_agent,
            logger,
        )

        if response is None:
            result_status = Status.ERROR
            reason = f"HTTP request failed after retries: {error}"
            matched_rule_type = "request_error"
            matched_value = None
        else:
            content = response.text or ""
            det = detect_status(content, item.positive_keywords, item.negative_keywords, item.blocked_keywords, item.regex)
            result_status = det.status
            reason = det.reason
            matched_rule_type = det.matched_rule_type
            matched_value = det.matched_value
            if response.status_code in (403, 429):
                result_status = Status.BLOCKED
                reason = f"HTTP {response.status_code} indicates blocking"
            elif response.status_code >= 500:
                result_status = Status.ERROR
                reason = f"HTTP {response.status_code} server error"

        previous = state.get(item.name, {})
        old_status = previous.get("last_status")
        old_status_enum = Status(old_status) if old_status in Status._value2member_map_ else None
        checked_at = now_iso()

        notify = should_notify(
            old_status_enum,
            result_status,
            item.notify_on_error if item.notify_on_error is not None else cfg.global_config.notify_on_error,
            cfg.global_config.notify_on_recovery,
        )

        if notify and not dry_run and cfg.telegram.enabled:
            message = build_message(item.name, old_status, result_status.value, checked_at, reason, item.url, error)
            send_telegram(message, logger)

        new_item_state = {
            "last_status": result_status.value,
            "last_checked_at": checked_at,
            "last_changed_at": checked_at if old_status != result_status.value else previous.get("last_changed_at", checked_at),
            "last_error": error if result_status == Status.ERROR else None,
            "consecutive_errors": (previous.get("consecutive_errors", 0) + 1) if result_status == Status.ERROR else 0,
            "last_matched_rule_type": matched_rule_type,
            "last_matched_value": matched_value,
        }
        state[item.name] = new_item_state
        logger.info('item_result item="%s" status=%s reason="%s" notify=%s', item.name, result_status.value, reason, notify)

        if not dry_run:
            save_state_atomic(cfg.state_path, state)

        time.sleep(random.uniform(0, cfg.global_config.jitter_seconds))


def run_forever(config_path: str | None = None, dry_run: bool = False, check_name: str | None = None) -> None:
    while True:
        run_once(config_path, dry_run, check_name)


def cli() -> None:
    parser = argparse.ArgumentParser(description="Xmonitors availability monitor")
    parser.add_argument("--config", help="Path to config file")
    parser.add_argument("--once", action="store_true", help="Check once and exit")
    parser.add_argument("--dry-run", action="store_true", help="Do not write state or send notifications")
    parser.add_argument("--check", help="Check only one item by exact name")
    args = parser.parse_args()

    if args.once:
        run_once(args.config, args.dry_run, args.check)
    else:
        run_forever(args.config, args.dry_run, args.check)
