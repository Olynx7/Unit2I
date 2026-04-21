import pytest

from unit2i.errors import ProviderError
from unit2i.normalize import normalize_generate_params
from unit2i.providers.model_catalog import ModelCapability, get_model_capability


def test_normalize_with_size_override_warning() -> None:
    data = normalize_generate_params(
        size="768*1024",
        aspect_ratio="1:1",
        quality="standard",
        output="auto",
    )
    assert data["size"] == (768, 1024)
    assert data["aspect_ratio"] == "3:4"
    assert "SIZE_OVERRIDES_ASPECT_RATIO" in data["warnings"]


def test_invalid_output_raises() -> None:
    with pytest.raises(ProviderError):
        normalize_generate_params(
            size="1024*1024",
            aspect_ratio=None,
            quality="standard",
            output="invalid",
        )


def test_invalid_size_type_raises() -> None:
    with pytest.raises(ProviderError):
        normalize_generate_params(
            size=123,  # type: ignore[arg-type]
            aspect_ratio=None,
            quality="standard",
            output="auto",
        )


def test_both_size_and_aspect_ratio_missing_raises() -> None:
    with pytest.raises(ProviderError):
        normalize_generate_params(
            size=None,
            aspect_ratio=None,
            quality=None,
            output="auto",
        )


def test_quality_fallback_when_invalid_in_aspect_branch() -> None:
    data = normalize_generate_params(
        size=None,
        aspect_ratio="1:1",
        quality="bad-quality",
        output="auto",
    )
    assert data["quality"] == "standard"
    assert "QUALITY_FALLBACK_TO_STANDARD" in data["warnings"]


def test_size_has_higher_priority_than_aspect_ratio() -> None:
    data = normalize_generate_params(
        size="1024*1024",
        aspect_ratio="16:9",
        quality="standard",
        output="auto",
    )
    assert data["size"] == (1024, 1024)
    assert data["aspect_ratio"] == "1:1"
    assert "SIZE_OVERRIDES_ASPECT_RATIO" in data["warnings"]


def test_size_empty_derives_from_aspect_ratio_and_quality() -> None:
    cap = get_model_capability("volcengine", "doubao-seedream-4-5")
    assert cap is not None

    data = normalize_generate_params(
        size=None,
        aspect_ratio="16:9",
        quality="standard",
        output="auto",
        capability=cap,
    )
    width, height = data["size"]
    pixels = width * height
    ratio = width / height
    assert abs(ratio - (16 / 9)) < 0.05
    assert cap.min_pixels is not None and pixels >= cap.min_pixels
    assert cap.max_pixels is not None and pixels <= cap.max_pixels


def test_size_empty_quality_level_changes_derived_pixels() -> None:
    cap = get_model_capability("volcengine", "doubao-seedream-4-5")
    assert cap is not None

    low = normalize_generate_params(
        size=None,
        aspect_ratio="1:1",
        quality="low",
        output="auto",
        capability=cap,
    )
    hd = normalize_generate_params(
        size=None,
        aspect_ratio="1:1",
        quality="hd",
        output="auto",
        capability=cap,
    )
    assert low["size"][0] * low["size"][1] < hd["size"][0] * hd["size"][1]


def test_string_size_and_aspect_ratio_are_parsed_before_validation() -> None:
    data = normalize_generate_params(
        size="1200*900",
        aspect_ratio="4:3",
        quality="standard",
        output="auto",
    )
    assert data["size"] == (1200, 900)
    assert data["aspect_ratio"] == "4:3"


def test_aspect_ratio_is_ignored_when_size_is_present() -> None:
    data = normalize_generate_params(
        size="1200*900",
        aspect_ratio="oops",
        quality="standard",
        output="auto",
    )
    assert data["size"] == (1200, 900)
    assert data["aspect_ratio"] == "4:3"
    assert "SIZE_OVERRIDES_ASPECT_RATIO" in data["warnings"]


def test_model_capability_rejects_oversized_pixels() -> None:
    cap = get_model_capability("dashscope", "wan2.6-t2i")
    assert cap is not None

    data = normalize_generate_params(
        size=(2048, 2048),
        aspect_ratio=None,
        quality="standard",
        output="auto",
        capability=cap,
    )
    width, height = data["size"]
    pixels = width * height
    assert cap.max_pixels is not None and pixels <= cap.max_pixels


def test_fixed_size_model_adjusts_to_supported_size() -> None:
    cap = get_model_capability("dashscope", "z-image-turbo")
    assert cap is not None
    assert cap.fixed_sizes is not None

    data = normalize_generate_params(
        size="1280*1280",
        aspect_ratio=None,
        quality="standard",
        output="auto",
        capability=cap,
    )
    assert data["size"] in cap.fixed_sizes
    assert "SIZE_ADJUSTED_FOR_MODEL_LIMITS" in data["warnings"]


def test_fixed_size_model_aspect_quality_result_in_fixed_sizes() -> None:
    cap = get_model_capability("dashscope", "z-image-turbo")
    assert cap is not None
    assert cap.fixed_sizes is not None

    low = normalize_generate_params(
        size=None,
        aspect_ratio="1:1",
        quality="low",
        output="auto",
        capability=cap,
    )
    hd = normalize_generate_params(
        size=None,
        aspect_ratio="1:1",
        quality="hd",
        output="auto",
        capability=cap,
    )
    assert low["size"] in cap.fixed_sizes
    assert hd["size"] in cap.fixed_sizes


def test_fixed_size_model_prefers_pixels_within_same_ratio() -> None:
    cap = ModelCapability(
        model_id="test-fixed",
        default_square_size=1024,
        min_pixels=None,
        max_pixels=None,
        fixed_sizes={(1024, 1024), (1536, 1536), (1024, 1536)},
        supported_outputs={"auto", "url", "b64"},
    )

    low = normalize_generate_params(
        size=None,
        aspect_ratio="1:1",
        quality="low",
        output="auto",
        capability=cap,
    )
    hd = normalize_generate_params(
        size=None,
        aspect_ratio="1:1",
        quality="hd",
        output="auto",
        capability=cap,
    )

    assert low["size"] == (1024, 1024)
    assert hd["size"] == (1536, 1536)
