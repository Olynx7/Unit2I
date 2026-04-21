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
    default_endpoint = "/api/v3/images/generations"

    def generate(self, req: GenerateRequest, *, timeout: int, max_retries: int) -> GenerateResult:
        start = time.perf_counter()
        provider_options = req.provider_options or {}
        transport = provider_options.get("transport") or {}
        provider_payload = provider_options.get("provider_payload") or {}
        if not isinstance(transport, dict):
            transport = {}
        if not isinstance(provider_payload, dict):
            provider_payload = {}
        model_id = req.model or self.default_model
        response_format = "b64_json" if req.output == "b64" else "url"
        payload = {
            "model": model_id,
            "prompt": req.prompt,
            "size": f"{req.size[0]}x{req.size[1]}",
            "response_format": response_format,
            "stream": False,
            "watermark": True,
            "n": req.num_images,
            "seed": req.seed,
        }
        if req.quality in {"high", "hd", "ultra"}:
            payload["optimize_prompt_options"] = {"mode": "standard"}
        else:
            payload["optimize_prompt_options"] = {"mode": "fast"}

        payload.update(provider_payload)

        endpoint = transport.get("endpoint") or self.default_endpoint

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        if isinstance(transport.get("headers"), dict):
            headers.update(transport["headers"])

        with httpx.Client(base_url=self.base_url, timeout=timeout) as client:
            resp = request_with_retry(
                lambda: client.post(endpoint, json=payload, headers=headers),
                max_retries=max_retries,
                provider=self.name,
            )

        data = _safe_json(resp)
        _raise_for_provider_error(data)
        images = _extract_images(data)
        artifacts = _adapt_output(images, req.output)
        request_id = (
            resp.headers.get("x-request-id")
            or data.get("request_id")
            or data.get("requestId")
            or ((data.get("ResponseMetadata") or {}).get("RequestId"))
        )

        return GenerateResult(
            images=artifacts,
            provider=self.name,
            request_id=request_id,
            metadata={
                "model_id": model_id,
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


def _raise_for_provider_error(payload: dict[str, Any]) -> None:
    error_obj = payload.get("error")
    if isinstance(error_obj, dict) and error_obj:
        code_text = str(error_obj.get("code") or "")
        message = str(error_obj.get("message") or "provider request failed")
        lower = f"{code_text} {message}".lower()
        error_code = "PROVIDER_ERROR"
        retryable = False
        if "rate" in lower and "limit" in lower:
            error_code = "RATE_LIMITED"
            retryable = True
        elif any(token in lower for token in ("invalid", "illegal", "parameter", "bad request")):
            error_code = "INVALID_REQUEST"
        elif any(token in lower for token in ("timeout", "temporar", "busy", "unavailable")):
            error_code = "TIMEOUT"
            retryable = True
        raise ProviderError(
            message,
            ErrorInfo(
                code=error_code,
                message=message,
                provider="volcengine",
                request_id=payload.get("request_id") or payload.get("requestId"),
                retryable=retryable,
                raw=payload,
            ),
        )

    metadata = payload.get("ResponseMetadata")
    if isinstance(metadata, dict):
        err = metadata.get("Error")
        if isinstance(err, dict) and err:
            code_text = str(err.get("Code") or "")
            message = str(err.get("Message") or "provider request failed")
            lower = f"{code_text} {message}".lower()
            error_code = "PROVIDER_ERROR"
            retryable = False
            if "rate" in lower and "limit" in lower:
                error_code = "RATE_LIMITED"
                retryable = True
            elif any(
                token in lower for token in ("invalid", "illegal", "parameter", "bad request")
            ):
                error_code = "INVALID_REQUEST"
            elif any(token in lower for token in ("timeout", "temporar", "busy", "unavailable")):
                error_code = "TIMEOUT"
                retryable = True
            raise ProviderError(
                message,
                ErrorInfo(
                    code=error_code,
                    message=message,
                    provider="volcengine",
                    request_id=metadata.get("RequestId"),
                    retryable=retryable,
                    raw=payload,
                ),
            )


def _extract_images(payload: dict[str, Any]) -> list[dict[str, Any]]:
    data = payload.get("data") or payload.get("Result") or payload
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]

    candidates = (
        data.get("images")
        or data.get("image_urls")
        or data.get("result")
        or data.get("Results")
        or []
    )
    if isinstance(candidates, dict):
        candidates = [candidates]
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
    images: list[dict[str, Any]] = []
    for item in candidates:
        if isinstance(item, dict):
            images.append(item)
        elif isinstance(item, str):
            images.append({"url": item})
    return images


def _adapt_output(items: list[dict[str, Any]], output_mode: str) -> list[ImageArtifact]:
    artifacts: list[ImageArtifact] = []
    for item in items:
        url = item.get("url") or item.get("image_url") or item.get("ResultUrl")
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
                    provider="volcengine",
                ),
            )

        if output_mode == "b64":
            url = None

        artifacts.append(
            ImageArtifact(url=url, b64=b64, mime_type=mime_type, width=width, height=height)
        )

    return artifacts
