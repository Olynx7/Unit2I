from unit2i.config import (
    PROVIDER_DEFAULTS,
    resolve_api_key,
    resolve_base_url,
    resolve_default_model,
)


def test_resolve_api_key_returns_override() -> None:
    assert resolve_api_key("dashscope", override="sk-test") == "sk-test"


def test_resolve_api_key_falls_back_to_env(monkeypatch) -> None:
    monkeypatch.setenv("UNIT2I_DASHSCOPE_API_KEY", "sk-env")
    assert resolve_api_key("dashscope") == "sk-env"


def test_resolve_api_key_returns_none_when_not_set(monkeypatch) -> None:
    monkeypatch.delenv("UNIT2I_DASHSCOPE_API_KEY", raising=False)
    assert resolve_api_key("dashscope") is None


def test_resolve_base_url_returns_override() -> None:
    assert resolve_base_url("dashscope", override="https://custom.example") == "https://custom.example"


def test_resolve_base_url_falls_back_to_env(monkeypatch) -> None:
    monkeypatch.setenv("UNIT2I_DASHSCOPE_BASE_URL", "https://env.example")
    assert resolve_base_url("dashscope") == "https://env.example"


def test_resolve_base_url_uses_default() -> None:
    url = resolve_base_url("dashscope")
    assert url == PROVIDER_DEFAULTS["dashscope"]["default_base_url"]


def test_resolve_default_model_returns_override() -> None:
    assert resolve_default_model("dashscope", override="custom-model") == "custom-model"


def test_resolve_default_model_uses_catalog_default() -> None:
    model = resolve_default_model("dashscope")
    assert model is not None
    assert len(model) > 0


def test_provider_defaults_have_required_keys() -> None:
    for _, cfg in PROVIDER_DEFAULTS.items():
        assert "api_key_env" in cfg
        assert "base_url_env" in cfg
        assert "default_base_url" in cfg
        assert "default_model" in cfg


def test_resolve_base_url_env_name_matches_defaults(monkeypatch) -> None:
    env_name = PROVIDER_DEFAULTS["volcengine"]["base_url_env"]
    monkeypatch.setenv(env_name, "https://env-volc.example")
    assert resolve_base_url("volcengine") == "https://env-volc.example"
