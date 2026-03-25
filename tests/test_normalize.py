import pytest

from unit2i.errors import ProviderError
from unit2i.model_catalog import get_model_capability
from unit2i.normalize import normalize_generate_params


def test_normalize_with_size_override_warning() -> None:
    data = normalize_generate_params(
        size="portrait",
        aspect_ratio="1:1",
        quality="standard",
        output="auto",
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
        )


def test_quality_fallback() -> None:
    data = normalize_generate_params(
        size="square",
        aspect_ratio=None,
        quality="ultra",
        output="auto",
    )
    assert data["quality"] == "standard"
    assert "QUALITY_FALLBACK_TO_STANDARD" in data["warnings"]


def test_aspect_ratio_drives_size_when_size_is_default_square() -> None:
    data = normalize_generate_params(
        size="square",
        aspect_ratio="16:9",
        quality="standard",
        output="auto",
    )
    assert data["size"] == (1024, 576)
    assert data["aspect_ratio"] == "16:9"
    assert "SIZE_OVERRIDES_ASPECT_RATIO" not in data["warnings"]


def test_model_capability_changes_default_square_size() -> None:
    cap = get_model_capability("volcengine", "doubao-seedream-4-5")
    assert cap is not None

    data = normalize_generate_params(
        size="square",
        aspect_ratio="16:9",
        quality="standard",
        output="auto",
        capability=cap,
    )
    assert data["size"] == (2560, 1440)
    assert "SIZE_ADJUSTED_FOR_MODEL_LIMITS" in data["warnings"]


def test_model_capability_rejects_oversized_pixels() -> None:
    cap = get_model_capability("dashscope", "wan2.6-t2i")
    assert cap is not None

    with pytest.raises(ProviderError):
        normalize_generate_params(
            size=(2048, 2048),
            aspect_ratio=None,
            quality="standard",
            output="auto",
            capability=cap,
        )
