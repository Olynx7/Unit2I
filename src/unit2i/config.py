import os

from .providers.model_catalog import get_provider_default_model

PROVIDER_DEFAULTS: dict[str, dict[str, str]] = {
    "dashscope": {
        "api_key_env": "UNIT2I_DASHSCOPE_API_KEY",
        "base_url_env": "UNIT2I_DASHSCOPE_BASE_URL",
        "default_base_url": "https://dashscope.aliyuncs.com",
        "default_model": "wan2.6-t2i",
    },
    "volcengine": {
        "api_key_env": "UNIT2I_VOLC_API_KEY",
        "base_url_env": "UNIT2I_VOLC_BASE_URL",
        "default_base_url": "https://ark.cn-beijing.volces.com",
        "default_model": "doubao-seedream-4-5",
    },
}


def resolve_api_key(provider: str, override: str | None = None) -> str | None:
    if override:
        return override
    env_name = PROVIDER_DEFAULTS[provider]["api_key_env"]
    return os.getenv(env_name)


def resolve_base_url(provider: str, override: str | None = None) -> str:
    if override:
        return override
    env_name = PROVIDER_DEFAULTS[provider]["base_url_env"]
    return os.getenv(env_name, PROVIDER_DEFAULTS[provider]["default_base_url"])


def resolve_default_model(provider: str, override: str | None = None) -> str:
    if override:
        return override
    catalog_default = get_provider_default_model(provider)
    if catalog_default:
        return catalog_default
    return PROVIDER_DEFAULTS[provider]["default_model"]
