import pytest

from unit2i.errors import ProviderError
from unit2i.normalize import normalize_generate_params


def test_normalize_with_size_override_warning() -> None:
    data = normalize_generate_params(
        size="portrait",
        aspect_ratio="1:1",
        quality="standard",
        output="auto",
        size_overrides_aspect=True,
    )
    assert data["size"] == (768, 1024)
    assert "SIZE_OVERRIDES_ASPECT_RATIO" in data["warnings"]


def test_invalid_output_raises() -> None:
    with pytest.raises(ProviderError):
        normalize_generate_params(
            size="square",
            aspect_ratio=None,
            quality="standard",
            output="invalid",
            size_overrides_aspect=False,
        )


def test_quality_fallback() -> None:
    data = normalize_generate_params(
        size="square",
        aspect_ratio=None,
        quality="ultra",
        output="auto",
        size_overrides_aspect=False,
    )
    assert data["quality"] == "standard"
    assert "QUALITY_FALLBACK_TO_STANDARD" in data["warnings"]
