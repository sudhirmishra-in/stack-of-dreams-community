"""Minimal HTTP client with timeouts, size limits, and exponential backoff with jitter."""

from __future__ import annotations

import json
import random
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Callable

MAX_BYTES = 8 * 1024 * 1024
RETRYABLE = {429, 500, 502, 503, 504}


class HttpError(Exception):
    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


class HttpClient:
    def __init__(
        self,
        user_agent: str,
        *,
        timeout: float = 30.0,
        max_attempts: int = 4,
        base_delay: float = 1.5,
        max_delay: float = 30.0,
        sleep: Callable[[float], None] = time.sleep,
        opener: Callable[..., Any] | None = None,
    ):
        self.user_agent = user_agent
        self.timeout = timeout
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self._sleep = sleep
        self._open = opener or urllib.request.urlopen

    def _request(self, req: urllib.request.Request, *, timeout: float | None = None, max_attempts: int | None = None) -> Any:
        timeout = self.timeout if timeout is None else timeout
        attempts = self.max_attempts if max_attempts is None else max_attempts
        last: Exception | None = None
        for attempt in range(1, attempts + 1):
            try:
                with self._open(req, timeout=timeout) as resp:
                    raw = resp.read(MAX_BYTES + 1)
                    if len(raw) > MAX_BYTES:
                        raise HttpError("response too large")
                    return json.loads(raw)
            except urllib.error.HTTPError as e:
                last = HttpError(f"HTTP {e.code}", e.code)
                if e.code not in RETRYABLE:
                    raise last from e
                retry_after = e.headers.get("Retry-After") if e.headers else None
                delay = float(retry_after) if retry_after and retry_after.isdigit() else None
            except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
                last, delay = HttpError(f"network error: {e}"), None
            except json.JSONDecodeError as e:
                # Overpass returns an HTML/markdown page when overloaded: treat as retryable.
                last, delay = HttpError("response was not valid JSON", 502), None
            if attempt == attempts:
                break
            backoff = min(self.max_delay, self.base_delay * (2 ** (attempt - 1)))
            self._sleep(delay if delay is not None else backoff * (0.5 + random.random() / 2))
        assert last is not None
        raise last

    def get_json(self, url: str, params: dict[str, Any] | None = None) -> Any:
        if params:
            url = f"{url}?{urllib.parse.urlencode(params)}"
        return self._request(urllib.request.Request(url, headers={"User-Agent": self.user_agent, "Accept": "application/json"}))

    def post_form_json(
        self, url: str, form: dict[str, str], *, timeout: float | None = None, max_attempts: int | None = None
    ) -> Any:
        data = urllib.parse.urlencode(form).encode()
        return self._request(
            urllib.request.Request(url, data=data, headers={"User-Agent": self.user_agent, "Accept": "application/json"}),
            timeout=timeout,
            max_attempts=max_attempts,
        )
