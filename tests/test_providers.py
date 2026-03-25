import httpx
import pytest

from unit2i.errors import OutputError, ProviderError
from unit2i.providers import dashscope as dashscope_module
from unit2i.providers import volcengine as volcengine_module
from unit2i.providers.dashscope import DashScopeProvider
from unit2i.providers.volcengine import VolcengineProvider
from unit2i.types import GenerateRequest


class _StubClient:
    response: httpx.Response
    last_endpoint: str | None = None
    last_json: dict | None = None
    last_headers: dict | None = None

    def __init__(self, *, base_url: str, timeout: int) -> None:
        self.base_url = base_url
        self.timeout = timeout

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def post(self, endpoint: str, json: dict, headers: dict) -> httpx.Response:
        _StubClient.last_endpoint = endpoint
        _StubClient.last_json = json
        _StubClient.last_headers = headers
        return _StubClient.response


def _response(
    payload: dict,
    *,
    status_code: int = 200,
    headers: dict | None = None,
) -> httpx.Response:
    req = httpx.Request("POST", "https://example.test/generate")
    return httpx.Response(status_code, json=payload, headers=headers, request=req)


def test_dashscope_request_mapping_and_auto_output(monkeypatch) -> None:
    monkeypatch.setattr(dashscope_module.httpx, "Client", _StubClient)
    _StubClient.response = _response(
        {
            "output": {
                "choices": [
                    {
                        "message": {
                            "content": [
                                {"image": "https://img/1.png"},
                                {"b64_json": "abc"},
                            ]
                        }
                    }
                ]
            },
            "request_id": "rid-1",
        }
    )

    provider = DashScopeProvider(
        api_key="k",
        base_url="https://dashscope.example",
        model="m-default",
    )
    result = provider.generate(
        GenerateRequest(
            prompt="p",
            size=(1024, 768),
            aspect_ratio="4:3",
            num_images=2,
            quality="standard",
            provider_options={
                "transport": {"endpoint": "/custom"},
                "provider_payload": {"parameters": {"style": "photo"}},
            },
            output="auto",
        ),
        timeout=10,
        max_retries=0,
    )

    assert _StubClient.last_endpoint == "/custom"
    assert _StubClient.last_json is not None
    assert _StubClient.last_json["input"]["messages"][0]["content"][0]["text"] == "p"
    assert _StubClient.last_json["parameters"]["size"] == "1024*768"
    assert _StubClient.last_json["parameters"]["response_format"] == "url"
    assert _StubClient.last_json["parameters"]["style"] == "photo"
    assert result.request_id == "rid-1"
    assert result.images[0].url == "https://img/1.png"
    assert result.images[1].b64 == "abc"


def test_dashscope_url_output_without_url_raises(monkeypatch) -> None:
    monkeypatch.setattr(dashscope_module.httpx, "Client", _StubClient)
    _StubClient.response = _response(
        {
            "output": {
                "choices": [{"message": {"content": [{"b64_json": "abc"}]}}]
            }
        }
    )

    provider = DashScopeProvider(api_key=None, base_url="https://dashscope.example", model="m")

    with pytest.raises(OutputError) as exc:
        provider.generate(
            GenerateRequest(prompt="p", size=(1024, 1024), output="url"),
            timeout=10,
            max_retries=0,
        )

    assert exc.value.error is not None
    assert exc.value.error.code == "NO_URL_AVAILABLE"


def test_dashscope_business_error_maps_to_invalid_request(monkeypatch) -> None:
    monkeypatch.setattr(dashscope_module.httpx, "Client", _StubClient)
    _StubClient.response = _response(
        {"error": {"code": "InvalidParameter", "message": "bad"}}
    )

    provider = DashScopeProvider(api_key=None, base_url="https://dashscope.example", model="m")

    with pytest.raises(ProviderError) as exc:
        provider.generate(
            GenerateRequest(prompt="p", size=(1024, 1024), output="auto"),
            timeout=10,
            max_retries=0,
        )

    assert exc.value.error is not None
    assert exc.value.error.code == "INVALID_REQUEST"


def test_volcengine_error_and_b64_output(monkeypatch) -> None:
    monkeypatch.setattr(volcengine_module.httpx, "Client", _StubClient)

    _StubClient.response = _response(
        {
            "error": {"code": "RateLimitExceeded", "message": "rate limit"}
        }
    )
    provider = VolcengineProvider(api_key=None, base_url="https://volc.example", model="m")

    with pytest.raises(ProviderError) as exc:
        provider.generate(
            GenerateRequest(prompt="p", size=(1024, 1024), output="auto"),
            timeout=10,
            max_retries=0,
        )
    assert exc.value.error is not None
    assert exc.value.error.code == "RATE_LIMITED"

    _StubClient.response = _response({"data": [{"url": "https://img/2.png", "b64_json": "xyz"}]})
    result = provider.generate(
        GenerateRequest(prompt="p", size=(1024, 1024), output="b64"),
        timeout=10,
        max_retries=0,
    )

    assert _StubClient.last_json is not None
    assert _StubClient.last_json["size"] == "1024x1024"
    assert _StubClient.last_json["response_format"] == "b64_json"
    assert _StubClient.last_json["stream"] is False
    assert result.images[0].url is None
    assert result.images[0].b64 == "xyz"
