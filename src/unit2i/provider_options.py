from __future__ import annotations

from typing import Any

from .errors import ErrorInfo, ProviderError


def normalize_provider_options(
    provider_options: dict[str, Any] | None,
) -> dict[str, Any]:
    if provider_options is None:
        return {"transport": {}, "provider_payload": {}}

    transport: dict[str, Any] = {}
    provider_payload: dict[str, Any] = {}

    transport_in = provider_options.get("transport")
    if isinstance(transport_in, dict):
        transport = dict(transport_in)
    elif transport_in is not None:
        raise ProviderError(
            "provider_options.transport must be a dict",
            ErrorInfo(
                code="INVALID_REQUEST",
                message="provider_options.transport must be a dict",
                provider="",
            ),
        )

    provider_payload_in = provider_options.get("provider_payload")
    if isinstance(provider_payload_in, dict):
        provider_payload = dict(provider_payload_in)
    elif provider_payload_in is not None:
        raise ProviderError(
            "provider_options.provider_payload must be a dict",
            ErrorInfo(
                code="INVALID_REQUEST",
                message="provider_options.provider_payload must be a dict",
                provider="",
            ),
        )

    known_keys = {"transport", "provider_payload"}
    unknown_keys = [key for key in provider_options if key not in known_keys]
    if unknown_keys:
        raise ProviderError(
            "provider_options contains unsupported keys",
            ErrorInfo(
                code="INVALID_REQUEST",
                message=(
                    "provider_options only supports 'transport' and "
                    "'provider_payload'"
                ),
                provider="",
                raw={"unsupported_keys": unknown_keys},
            ),
        )

    return {
        "transport": transport,
        "provider_payload": provider_payload,
    }
