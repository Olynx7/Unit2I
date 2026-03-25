from __future__ import annotations

import random
import time
from collections.abc import Callable
from typing import Any

import httpx

from ..errors import ErrorInfo, ProviderError


def is_retryable_status(status_code: int) -> bool:
    return status_code in {408, 429, 500, 502, 503, 504}


def _map_status_to_code(status_code: int) -> str:
    if status_code == 429:
        return "RATE_LIMITED"
    if status_code in {408, 504}:
        return "TIMEOUT"
    if status_code in {400, 401, 403, 404, 405, 409, 413, 415, 422}:
        return "INVALID_REQUEST"
    return "PROVIDER_ERROR"


def _extract_error_message(raw: dict[str, Any] | str) -> str:
    if isinstance(raw, str):
        return raw.strip() or "provider request failed"

    for key in ("message", "msg", "error_message", "errorMsg"):
        value = raw.get(key)
        if isinstance(value, str) and value.strip():
            return value

    error = raw.get("error")
    if isinstance(error, dict):
        for key in ("message", "msg", "error_message", "errorMsg"):
            value = error.get(key)
            if isinstance(value, str) and value.strip():
                return value
    elif isinstance(error, str) and error.strip():
        return error

    return "provider request failed"


def request_with_retry(
    request_fn: Callable[[], httpx.Response],
    *,
    max_retries: int,
    provider: str,
) -> httpx.Response:
    delays = [0.5, 1.0, 2.0]
    attempt = 0

    while True:
        try:
            resp = request_fn()
            if resp.status_code < 400:
                return resp
            retryable = is_retryable_status(resp.status_code)
            if attempt >= max_retries or not retryable:
                raw = _safe_json_or_text(resp)
                error_code = _map_status_to_code(resp.status_code)
                raise ProviderError(
                    f"Provider returned HTTP {resp.status_code}",
                    ErrorInfo(
                        code=error_code,
                        message=_extract_error_message(raw),
                        provider=provider,
                        retryable=retryable,
                        raw=raw,
                    ),
                )
        except httpx.TimeoutException as exc:
            if attempt >= max_retries:
                raise ProviderError(
                    "Request timeout",
                    ErrorInfo(
                        code="TIMEOUT",
                        message="Request timed out",
                        provider=provider,
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
                        provider=provider,
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
