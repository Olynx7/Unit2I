import httpx
import pytest

from unit2i.errors import ProviderError
from unit2i.utils.http import request_with_retry


def _response(status_code: int, payload: dict) -> httpx.Response:
    req = httpx.Request("POST", "https://example.test/generate")
    return httpx.Response(status_code, json=payload, request=req)


def test_http_429_maps_to_rate_limited() -> None:
    with pytest.raises(ProviderError) as exc:
        request_with_retry(
            lambda: _response(429, {"message": "too many requests"}),
            max_retries=0,
            provider="dashscope",
        )

    assert exc.value.error is not None
    assert exc.value.error.code == "RATE_LIMITED"
    assert exc.value.error.retryable is True
    assert exc.value.error.provider == "dashscope"


def test_http_400_maps_to_invalid_request() -> None:
    with pytest.raises(ProviderError) as exc:
        request_with_retry(
            lambda: _response(400, {"message": "invalid prompt"}),
            max_retries=0,
            provider="volcengine",
        )

    assert exc.value.error is not None
    assert exc.value.error.code == "INVALID_REQUEST"
    assert exc.value.error.retryable is False
    assert exc.value.error.provider == "volcengine"


def test_timeout_maps_to_timeout_error() -> None:
    def _raise_timeout() -> httpx.Response:
        req = httpx.Request("POST", "https://example.test/generate")
        raise httpx.ReadTimeout("read timeout", request=req)

    with pytest.raises(ProviderError) as exc:
        request_with_retry(_raise_timeout, max_retries=0, provider="dashscope")

    assert exc.value.error is not None
    assert exc.value.error.code == "TIMEOUT"
    assert exc.value.error.retryable is True
