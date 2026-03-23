import os


PROVIDER_DEFAULTS: dict[str, dict[str, str]] = {
    "dashscope": {
        "api_key_env": "UNIT2I_DASHSCOPE_API_KEY",
        "base_url_env": "UNIT2I_DASHSCOPE_BASE_URL",
        "default_base_url": "https://dashscope.aliyuncs.com",
        "default_model": "wanx2.1-t2i-plus",
    },
    "volcengine": {
        "api_key_env": "UNIT2I_VOLC_API_KEY",
        "base_url_env": "UNIT2I_VOLC_BASE_URL",
        "default_base_url": "https://visual.volcengineapi.com",
        "default_model": "doubao-seedream-3-0-t2i-250415",
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
    return PROVIDER_DEFAULTS[provider]["default_model"]
