from unit2i import ConfigError, Unit2I
from unit2i.errors import ErrorInfo
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


def test_batch_generate_fail_fast_marks_unsubmitted(monkeypatch) -> None:
    from unit2i import client as client_module

    monkeypatch.setitem(client_module.PROVIDERS, "dashscope", _FakeProvider)
    _FakeProvider.calls = []
    sdk = Unit2I(provider="dashscope")

    batch = sdk.batch_generate(
        [
            {"prompt": "fail"},
            {"prompt": "ok1"},
            {"prompt": "ok2"},
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


def test_generate_uses_aspect_ratio_when_size_default(monkeypatch) -> None:
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
    result = sdk.generate(prompt="ok", aspect_ratio="16:9")

    assert result.images[0].width == 1707
    assert result.images[0].height == 960
    assert result.metadata["aspect_ratio"] == "16:9"
