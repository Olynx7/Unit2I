from unit2i import ConfigError, Unit2I
from unit2i.errors import ErrorInfo, ProviderError
from unit2i.types import BatchItemResult, GenerateResult, ImageArtifact


class _FakeProvider:
    calls: list[str] = []

    def __init__(self, *, api_key: str | None, base_url: str, model: str) -> None:
        self.api_key = api_key
        self.base_url = base_url
        self.default_model = model

    def generate(self, req, *, timeout: int, max_retries: int) -> GenerateResult:
        _FakeProvider.calls.append(req.prompt)
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


def test_num_images_exceeds_model_limit() -> None:
    sdk = Unit2I(provider="dashscope", api_key="test")
    try:
        sdk.generate(prompt="test", num_images=10, size="1024*1024")
        raise AssertionError("expected ProviderError")
    except ProviderError as exc:
        assert exc.error is not None
        assert exc.error.code == "INVALID_REQUEST"
        assert "exceeds model limit" in exc.error.message


def test_num_images_within_model_limit_ok() -> None:
    sdk = Unit2I(provider="dashscope", api_key="test")
    try:
        sdk.generate(prompt="test", num_images=4, size="1024*1024")
    except ProviderError as exc:
        if "exceeds model limit" in str(exc):
            raise AssertionError("num_images=4 should be allowed for wan2.6-t2i")


def test_batch_generate_keeps_order(monkeypatch) -> None:
    from unit2i import client as client_module

    monkeypatch.setitem(client_module.PROVIDERS, "dashscope", _FakeProvider)
    sdk = Unit2I(provider="dashscope")

    batch = sdk.batch_generate(
        [
            {"prompt": "ok1", "aspect_ratio": "1:1"},
            {"prompt": "fail", "aspect_ratio": "1:1"},
            {"prompt": "ok2", "aspect_ratio": "1:1"},
        ],
        concurrency=2,
    )

    assert len(batch) == 3
    assert isinstance(batch[0], BatchItemResult)
    assert batch[0].success is True
    assert batch[1].success is False
    assert isinstance(batch[1].error, ErrorInfo)
    assert batch[2].success is True


def test_batch_generate_fail_fast_marks_unsubmitted(monkeypatch) -> None:
    from unit2i import client as client_module

    monkeypatch.setitem(client_module.PROVIDERS, "dashscope", _FakeProvider)
    _FakeProvider.calls = []
    sdk = Unit2I(provider="dashscope")

    batch = sdk.batch_generate(
        [
            {"prompt": "fail", "aspect_ratio": "1:1"},
            {"prompt": "ok1", "aspect_ratio": "1:1"},
            {"prompt": "ok2", "aspect_ratio": "1:1"},
        ],
        concurrency=1,
        fail_fast=True,
    )

    assert _FakeProvider.calls == ["fail"]
    assert batch[0].success is False
    assert batch[1].success is False
    assert batch[1].error is not None
    assert "not executed" in batch[1].error.message
    assert batch[2].success is False


def test_generate_size_keeps_priority_when_not_empty(monkeypatch) -> None:
    from unit2i import client as client_module

    class _InspectProvider(_FakeProvider):
        def generate(self, req, *, timeout: int, max_retries: int) -> GenerateResult:
            return GenerateResult(
                images=[
                    ImageArtifact(
                        url="https://example.com/a.png",
                        width=req.size[0],
                        height=req.size[1],
                    )
                ],
                provider="dashscope",
                request_id="req-test",
                metadata={
                    "warnings": [],
                    "size": f"{req.size[0]}x{req.size[1]}",
                    "aspect_ratio": req.aspect_ratio,
                },
            )

    monkeypatch.setitem(client_module.PROVIDERS, "dashscope", _InspectProvider)
    sdk = Unit2I(provider="dashscope")
    result = sdk.generate(prompt="ok", size="1280*1280", aspect_ratio="16:9")

    assert result.images[0].width == 1280
    assert result.images[0].height == 1280
    assert result.metadata["aspect_ratio"] == "1:1"
    assert "SIZE_OVERRIDES_ASPECT_RATIO" in result.metadata["warnings"]
