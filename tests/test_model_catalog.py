from unit2i.errors import ProviderError
from unit2i.providers.model_catalog import (
    get_model_capability,
    get_provider_default_model,
    validate_catalogs,
)
from unit2i.providers.provider_options import normalize_provider_options


def test_provider_default_models_from_catalog() -> None:
    assert get_provider_default_model("dashscope") == "wan2.6-t2i"
    assert get_provider_default_model("volcengine") == "doubao-seedream-4-5"


def test_model_capability_lookup() -> None:
    cap = get_model_capability("volcengine", "doubao-seedream-4-5")
    assert cap is not None
    assert cap.default_square_size == 2048
    assert cap.max_pixels == 4096 * 4096


def test_catalog_schema_validation_passes() -> None:
    assert validate_catalogs() == []


def test_provider_options_normalization_with_new_namespace() -> None:
    normalized = normalize_provider_options(
        {
            "transport": {"endpoint": "/v1/custom", "headers": {"X-Test": "1"}},
            "provider_payload": {"watermark": False},
        }
    )
    assert normalized["transport"]["endpoint"] == "/v1/custom"
    assert normalized["provider_payload"]["watermark"] is False


def test_provider_options_rejects_legacy_keys() -> None:
    try:
        normalize_provider_options(
            {
                "endpoint": "/legacy",
                "headers": {"X-Legacy": "1"},
            }
        )
        raise AssertionError("expected ProviderError")
    except ProviderError as exc:
        assert exc.error is not None
        assert exc.error.code == "INVALID_REQUEST"
