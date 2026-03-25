from __future__ import annotations

import time
from typing import Any

import httpx

from ..errors import ErrorInfo, OutputError, ProviderError
from ..types import GenerateRequest, GenerateResult, ImageArtifact
from ..utils.http import request_with_retry
from .base import BaseProvider


class DashScopeProvider(BaseProvider):
    name = "dashscope"
    default_endpoint = "/api/v1/services/aigc/multimodal-generation/generation"

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
        payload = {
            "model": model_id,
            "input": {
                "messages": [
                    {
                        "role": "user",
                        "content": [{"text": req.prompt}],
                    }
                ]
            },
            "parameters": {
                "size": f"{req.size[0]}*{req.size[1]}",
                "n": req.num_images,
                "seed": req.seed,
                "watermark": True,
            },
        }
        if req.quality in {"hd", "standard"}:
            payload["parameters"]["prompt_extend"] = req.quality == "hd"
        if req.output == "b64":
            payload["parameters"]["response_format"] = "b64_json"
        else:
            payload["parameters"]["response_format"] = "url"

        parameter_overrides: dict[str, Any] = {}
        if isinstance(provider_payload.get("parameters"), dict):
            parameter_overrides.update(provider_payload["parameters"])
        for key, value in provider_payload.items():
            if key != "parameters":
                parameter_overrides[key] = value

        payload["parameters"].update(parameter_overrides)

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
            ErrorInfo(code="PROVIDER_ERROR", message="response is not dict", provider="dashscope"),
        )
    except ValueError as exc:
        raise ProviderError(
            "Invalid JSON response from provider",
            ErrorInfo(
                code="PROVIDER_ERROR",
                message="invalid json",
                provider="dashscope",
                raw=resp.text,
            ),
        ) from exc


def _raise_for_provider_error(payload: dict[str, Any]) -> None:
    success = payload.get("success")
    code = payload.get("code")
    has_error_obj = isinstance(payload.get("error"), dict) and bool(payload.get("error"))
    if success is False or has_error_obj or (
        isinstance(code, str) and code not in {"", "0", "SUCCESS", "Success"}
    ):
        message = _extract_error_message(payload)
        retryable = _is_retryable_business_error(payload)
        error_code = "RATE_LIMITED" if _is_rate_limit_error(payload) else "PROVIDER_ERROR"
        if _is_invalid_request_error(payload):
            error_code = "INVALID_REQUEST"
        raise ProviderError(
            message,
            ErrorInfo(
                code=error_code,
                message=message,
                provider="dashscope",
                request_id=payload.get("request_id") or payload.get("requestId"),
                retryable=retryable,
                raw=payload,
            ),
        )


def _extract_images(payload: dict[str, Any]) -> list[dict[str, Any]]:
    # DashScope multimodal-generation returns images under choices[].message.content[].image
    output = payload.get("output") or payload
    choices = output.get("choices")
    if isinstance(choices, list):
        collected: list[dict[str, Any]] = []
        for choice in choices:
            if not isinstance(choice, dict):
                continue
            message = choice.get("message")
            if not isinstance(message, dict):
                continue
            content_items = message.get("content")
            if not isinstance(content_items, list):
                continue
            for content in content_items:
                if not isinstance(content, dict):
                    continue
                image_url = content.get("image")
                b64 = content.get("b64_json")
                if image_url or b64:
                    collected.append({"url": image_url, "b64": b64})
        if collected:
            return collected

    candidates = (
        output.get("results")
        or output.get("images")
        or output.get("data")
        or output.get("image_list")
        or []
    )
    if not isinstance(candidates, list):
        raise ProviderError(
            "Unexpected image list format",
            ErrorInfo(
                code="PROVIDER_ERROR",
                message="image list is not array",
                provider="dashscope",
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
        url = item.get("url") or item.get("image_url") or item.get("result_url")
        b64 = item.get("b64") or item.get("base64") or item.get("image_base64")
        mime_type = item.get("mime_type")
        width = item.get("width")
        height = item.get("height")

        if output_mode == "url" and not url:
            raise OutputError(
                "No URL available for output='url'",
                ErrorInfo(
                    code="NO_URL_AVAILABLE",
                    message="provider did not return url",
                    provider="dashscope",
                ),
            )

        if output_mode == "b64":
            url = None

        artifacts.append(
            ImageArtifact(url=url, b64=b64, mime_type=mime_type, width=width, height=height)
        )

    return artifacts


def _extract_error_message(payload: dict[str, Any]) -> str:
    error = payload.get("error")
    if isinstance(error, dict):
        for key in ("message", "msg"):
            value = error.get(key)
            if isinstance(value, str) and value.strip():
                return value
    for key in ("message", "msg"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return "provider request failed"


def _is_rate_limit_error(payload: dict[str, Any]) -> bool:
    error = payload.get("error")
    if isinstance(error, dict):
        text = str(error.get("code") or "") + " " + str(error.get("message") or "")
    else:
        text = str(payload.get("code") or "") + " " + str(payload.get("message") or "")
    text = text.lower()
    return "rate" in text and "limit" in text


def _is_invalid_request_error(payload: dict[str, Any]) -> bool:
    error = payload.get("error")
    if isinstance(error, dict):
        text = str(error.get("code") or "") + " " + str(error.get("message") or "")
    else:
        text = str(payload.get("code") or "") + " " + str(payload.get("message") or "")
    text = text.lower()
    return any(token in text for token in ("invalid", "illegal", "bad request", "parameter"))


def _is_retryable_business_error(payload: dict[str, Any]) -> bool:
    if _is_rate_limit_error(payload):
        return True
    error = payload.get("error")
    if isinstance(error, dict):
        text = str(error.get("code") or "") + " " + str(error.get("message") or "")
    else:
        text = str(payload.get("code") or "") + " " + str(payload.get("message") or "")
    text = text.lower()
    return any(token in text for token in ("timeout", "temporar", "unavailable", "busy"))
