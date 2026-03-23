from unit2i import ConfigError, Unit2I
from unit2i.errors import ErrorInfo
from unit2i.types import BatchItemResult, GenerateResult, ImageArtifact


class _FakeProvider:
    def __init__(self, *, api_key: str | None, base_url: str, model: str) -> None:
        self.api_key = api_key
        self.base_url = base_url
        self.default_model = model

    def generate(self, req, *, timeout: int, max_retries: int) -> GenerateResult:
        if req.prompt == "fail":
            raise RuntimeError("boom")
        return GenerateResult(
            images=[ImageArtifact(url="https://example.com/a.png")],
            provider="dashscope",
            request_id="req-test",
            metadata={"warnings": [], "size": "1024x1024"},
        )


def test_invalid_provider() -> None:
    try:
        Unit2I(provider="unknown")
        raise AssertionError("expected ConfigError")
    except ConfigError:
        assert True


def test_batch_generate_keeps_order(monkeypatch) -> None:
    from unit2i import client as client_module

    monkeypatch.setitem(client_module.PROVIDERS, "dashscope", _FakeProvider)
    sdk = Unit2I(provider="dashscope")

    batch = sdk.batch_generate(
        [
            {"prompt": "ok1"},
            {"prompt": "fail"},
            {"prompt": "ok2"},
        ],
        concurrency=2,
    )

    assert len(batch) == 3
    assert isinstance(batch[0], BatchItemResult)
    assert batch[0].success is True
    assert batch[1].success is False
    assert isinstance(batch[1].error, ErrorInfo)
    assert batch[2].success is True
