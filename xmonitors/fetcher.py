from __future__ import annotations

import random
import time
import requests
from requests import Response


def fetch_with_retries(url: str, timeout: int, max_retries: int, backoff_seconds: int, user_agent: str, logger):
    headers = {"User-Agent": user_agent}
    last_error = None
    for attempt in range(1, max_retries + 1):
        start = time.time()
        try:
            response: Response = requests.get(url, headers=headers, timeout=timeout)
            elapsed = time.time() - start
            logger.info('http_result url=%s status=%s elapsed=%.2fs', url, response.status_code, elapsed)
            return response, None
        except requests.RequestException as exc:
            last_error = str(exc)
            logger.warning("request_failed url=%s attempt=%s/%s error=%s", url, attempt, max_retries, last_error)
            if attempt < max_retries:
                time.sleep(backoff_seconds * (2 ** (attempt - 1)) + random.uniform(0, 1))
    return None, last_error
