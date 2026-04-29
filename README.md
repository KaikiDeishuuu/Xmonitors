# stock-monitor

`stock-monitor` is a small Python service that checks product pages on a fixed interval, tracks stock state in JSON, and sends Telegram alerts only when availability changes.

## What it does

- Fetches each product page with `requests`.
- Classifies stock status from the HTML using generic signals such as `Order Now`, `Add to Cart`, `Configure`, `In Stock`, `Available`, and WHMCS-style availability counts.
- Persists product state in `state.json`.
- Sends Telegram messages only on state transitions, with optional first-observation notifications controlled by config.

## Files

- `monitor.py` - the long-running service.
- `config.example.json` - template config.
- `config.json` - active config with placeholder Telegram credentials.
- `state.json` - persisted per-product state.
- `requirements.txt` - runtime dependencies.
- `systemd/stock-monitor.service` - sample service unit.

## Setup

1. Create a virtual environment and install dependencies.
2. Edit `config.json` with your Telegram bot token and chat ID.
3. Start the monitor with `python3 monitor.py`.

## Docker

Build the image and run the service with bind mounts for config, state, and logs:

```bash
docker build -t stock-monitor .
docker run -d --name stock-monitor \
	--restart unless-stopped \
	-v "$PWD/config.json:/app/config.json:ro" \
	-v "$PWD/state.json:/app/state.json" \
	-v "$PWD/logs:/app/logs" \
	stock-monitor
```

Or use Compose:

```bash
docker compose up -d --build
```

## Configuration

The config format uses three sections:

- `telegram` - bot token and chat ID.
- `request` - timeout and user agent.
- `monitor` - default interval, jitter, and first-run notification behavior.
- `products` - the list of pages to monitor.

If `state.json` is missing, the service creates it from `config.json` using each product's `initial_state`.

## systemd

The sample unit assumes the project lives at `/opt/stock-monitor`. Update `WorkingDirectory` and `ExecStart` if you deploy elsewhere.

## Notes

- No database is used.
- Telegram notifications are skipped automatically while the config still contains placeholder credentials.
- Logs are written to `logs/stock-monitor.log`.
- Telegram alerts use HTML formatting with a cleaner status header, product metadata, and a clickable product link.