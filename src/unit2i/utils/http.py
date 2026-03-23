from __future__ import annotations

import random
import time
from collections.abc import Callable
from typing import Any

import httpx

from ..errors import ErrorInfo, ProviderError


def is_retryable_status(status_code: int) -> bool:
    return status_code in {429, 500, 502, 503, 504}


def request_with_retry(
    request_fn: Callable[[], httpx.Response],
    *,
    max_retries: int,
) -> httpx.Response:
    delays = [0.5, 1.0, 2.0]
    attempt = 0

    while True:
        try:
            resp = request_fn()
            if resp.status_code < 400:
                return resp
            if attempt >= max_retries or not is_retryable_status(resp.status_code):
                raise ProviderError(
                    f"Provider returned HTTP {resp.status_code}",
                    ErrorInfo(
                        code="PROVIDER_ERROR",
                        message=f"HTTP {resp.status_code}",
                        provider="",
                        retryable=is_retryable_status(resp.status_code),
                        raw=_safe_json_or_text(resp),
                    ),
                )
        except httpx.TimeoutException as exc:
            if attempt >= max_retries:
                raise ProviderError(
                    "Request timeout",
                    ErrorInfo(
                        code="TIMEOUT",
                        message="Request timed out",
                        provider="",
                        retryable=True,
                        raw=str(exc),
                    ),
                ) from exc
        except httpx.HTTPError as exc:
            if attempt >= max_retries:
                raise ProviderError(
                    "HTTP transport error",
                    ErrorInfo(
                        code="PROVIDER_ERROR",
                        message=str(exc),
                        provider="",
                        retryable=True,
                        raw=str(exc),
                    ),
                ) from exc

        sleep_s = delays[min(attempt, len(delays) - 1)] + random.uniform(0, 0.3)
        time.sleep(sleep_s)
        attempt += 1


def _safe_json_or_text(resp: httpx.Response) -> dict[str, Any] | str:
    try:
        data = resp.json()
        if isinstance(data, dict):
            return data
        return {"data": data}
    except Exception:
        return resp.text
