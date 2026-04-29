# Xmonitors

Lightweight, configurable stock/product availability monitor with JSON config, JSON state, and Telegram notifications.

## Features
- Explicit statuses: `IN_STOCK`, `OUT_OF_STOCK`, `UNKNOWN`, `ERROR`, `BLOCKED`
- Per-item keyword/regex detection with precedence
- Retry + timeout + backoff + jitter
- Safe JSON state with atomic writes
- `.env` support for Telegram secrets
- CLI modes: `--once`, `--dry-run`, `--check`
- Docker, docker-compose, and systemd support

## Quick start
1. `cp .env.example .env`
2. `cp config.example.json config.json`
3. Fill `.env` with `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`
4. `python -m pip install -r requirements.txt`
5. `python -m xmonitors --once --config config.json`

## Configuration
Use `config.example.json` as template. Main sections:
- `global`: retry/timeout/user-agent/notification defaults
- `telegram`: enable or disable Telegram delivery
- `items`: per-target monitoring rules

Legacy config is still loaded with a migration warning.

## Telegram setup
- Create bot with BotFather.
- Get `chat_id` from updates API.
- Put both values in `.env`.

## Local Python usage
- `python -m xmonitors`
- `python -m xmonitors --config config.json`
- `python -m xmonitors --once`
- `python -m xmonitors --dry-run`
- `python -m xmonitors --check "Example VPS Product"`

## Docker usage
Build and run:
- `docker build -t xmonitors .`
- `docker run --rm --env-file .env -v $(pwd)/config.json:/app/config.json:ro -v $(pwd)/data:/app/data xmonitors`

## docker-compose usage
- `docker compose up -d --build`
- `docker compose logs -f xmonitors`

## systemd usage
Use `systemd/xmonitors.service`, then:
- `sudo systemctl enable --now xmonitors`
- `journalctl -u xmonitors -f`

## CLI options
- `--config`: config path override
- `--once`: single pass
- `--dry-run`: no state write/no notify
- `--check NAME`: check one item

## Status meanings
- `IN_STOCK`: positive rule matched
- `OUT_OF_STOCK`: negative rule matched
- `BLOCKED`: blocked rule or HTTP 403/429
- `ERROR`: request failure or server error
- `UNKNOWN`: no rules matched

## State file explanation
State defaults to `data/state.json` and stores last status, timestamps, error metadata, and last matched rule metadata.

## Troubleshooting
- Missing Telegram env vars: notifications skipped.
- Invalid `state.json`: file is backed up and recreated.
- Bad regex: item handled without crashing process.

## Security notes
- Never commit `.env`, `config.json`, `state.json`, or logs.
- Keep only `config.example.json` and `.env.example` in git.

## Roadmap
- Optional webhook integrations
- Better per-item scheduling
- Optional notification templates
