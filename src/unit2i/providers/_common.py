from __future__ import annotations

from typing import Any

import httpx

from ..errors import ErrorInfo, OutputError, ProviderError
from ..types import ImageArtifact


def safe_json(resp: httpx.Response, *, provider: str) -> dict[str, Any]:
    try:
        payload = resp.json()
        if isinstance(payload, dict):
            return payload
        raise ProviderError(
            "Unexpected provider response type",
            ErrorInfo(
                code="PROVIDER_ERROR", message="response is not dict", provider=provider
            ),
        )
    except ValueError as exc:
        raise ProviderError(
            "Invalid JSON response from provider",
            ErrorInfo(
                code="PROVIDER_ERROR",
                message="invalid json",
                provider=provider,
                raw=resp.text,
            ),
        ) from exc


def adapt_output(
    items: list[dict[str, Any]], *, output_mode: str, provider: str
) -> list[ImageArtifact]:
    artifacts: list[ImageArtifact] = []
    for item in items:
        url = (
            item.get("url")
            or item.get("image_url")
            or item.get("result_url")
            or item.get("ResultUrl")
        )
        b64 = (
            item.get("b64")
            or item.get("base64")
            or item.get("image_base64")
            or item.get("b64_json")
        )
        mime_type = item.get("mime_type")
        width = item.get("width")
        height = item.get("height")

        if output_mode == "url" and not url:
            raise OutputError(
                "No URL available for output='url'",
                ErrorInfo(
                    code="NO_URL_AVAILABLE",
                    message="provider did not return url",
                    provider=provider,
                ),
            )

        if output_mode == "b64":
            url = None

        artifacts.append(
            ImageArtifact(url=url, b64=b64, mime_type=mime_type, width=width, height=height)
        )

    return artifacts


def normalize_image_items(
    candidates: list[Any], *, provider: str
) -> list[dict[str, Any]]:
    if isinstance(candidates, dict):
        candidates = [candidates]
    if not isinstance(candidates, list):
        raise ProviderError(
            "Unexpected image list format",
            ErrorInfo(
                code="PROVIDER_ERROR",
                message="image list is not array",
                provider=provider,
            ),
        )
    images: list[dict[str, Any]] = []
    for item in candidates:
        if isinstance(item, dict):
            images.append(item)
        elif isinstance(item, str):
            images.append({"url": item})
    return images
