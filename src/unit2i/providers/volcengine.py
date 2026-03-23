from __future__ import annotations

import time
from typing import Any

import httpx

from ..errors import ErrorInfo, OutputError, ProviderError
from ..types import GenerateRequest, GenerateResult, ImageArtifact
from ..utils.http import request_with_retry
from .base import BaseProvider


class VolcengineProvider(BaseProvider):
    name = "volcengine"

    def generate(self, req: GenerateRequest, *, timeout: int, max_retries: int) -> GenerateResult:
        start = time.perf_counter()
        payload = {
            "model": req.model or self.default_model,
            "prompt": req.prompt,
            "size": {"width": req.size[0], "height": req.size[1]},
            "num_images": req.num_images,
            "seed": req.seed,
            "quality": req.quality,
        }
        if req.provider_options:
            payload.update(req.provider_options)

        endpoint = (req.provider_options or {}).get("endpoint", "/")

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        with httpx.Client(base_url=self.base_url, timeout=timeout) as client:
            resp = request_with_retry(
                lambda: client.post(endpoint, json=payload, headers=headers),
                max_retries=max_retries,
            )

        data = _safe_json(resp)
        images = _extract_images(data)
        artifacts = _adapt_output(images, req.output)

        return GenerateResult(
            images=artifacts,
            provider=self.name,
            request_id=resp.headers.get("x-request-id"),
            metadata={
                "model_id": payload["model"],
                "size": f"{req.size[0]}x{req.size[1]}",
                "aspect_ratio": req.aspect_ratio,
                "seed": req.seed,
                "num_images": req.num_images,
                "image_count_adjusted": len(artifacts),
                "warnings": [],
                "latency_ms": int((time.perf_counter() - start) * 1000),
            },
        )


def _safe_json(resp: httpx.Response) -> dict[str, Any]:
    try:
        payload = resp.json()
        if isinstance(payload, dict):
            return payload
        raise ProviderError(
            "Unexpected provider response type",
            ErrorInfo(code="PROVIDER_ERROR", message="response is not dict", provider="volcengine"),
        )
    except ValueError as exc:
        raise ProviderError(
            "Invalid JSON response from provider",
            ErrorInfo(
                code="PROVIDER_ERROR",
                message="invalid json",
                provider="volcengine",
                raw=resp.text,
            ),
        ) from exc


def _extract_images(payload: dict[str, Any]) -> list[dict[str, Any]]:
    data = payload.get("data") or payload
    candidates = data.get("images") or data.get("result") or []
    if not isinstance(candidates, list):
        raise ProviderError(
            "Unexpected image list format",
            ErrorInfo(
                code="PROVIDER_ERROR",
                message="image list is not array",
                provider="volcengine",
                raw=payload,
            ),
        )
    return [item for item in candidates if isinstance(item, dict)]


def _adapt_output(items: list[dict[str, Any]], output_mode: str) -> list[ImageArtifact]:
    artifacts: list[ImageArtifact] = []
    for item in items:
        url = item.get("url") or item.get("image_url")
        b64 = item.get("b64") or item.get("base64")
        mime_type = item.get("mime_type")
        width = item.get("width")
        height = item.get("height")

        if output_mode == "url" and not url:
            raise OutputError(
                "No URL available for output='url'",
                ErrorInfo(
                    code="NO_URL_AVAILABLE",
                    message="provider did not return url",
                    provider="volcengine",
                ),
            )

        if output_mode == "b64":
            url = None

        artifacts.append(
            ImageArtifact(url=url, b64=b64, mime_type=mime_type, width=width, height=height)
        )

    return artifacts
