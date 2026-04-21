from __future__ import annotations

from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from typing import Any

from .config import PROVIDER_DEFAULTS, resolve_api_key, resolve_base_url, resolve_default_model
from .errors import ConfigError, ErrorInfo, ProviderError
from .normalize import normalize_generate_params
from .providers.model_catalog import get_model_capability
from .providers.provider_options import normalize_provider_options
from .providers.registry import PROVIDERS
from .types import BatchItemResult, GenerateRequest, GenerateResult
from .utils.rate_limit import TokenBucket


class Unit2I:
    def __init__(
        self,
        *,
        provider: str,
        model: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: int = 60,
        max_retries: int = 2,
        rate_limit_rps: float = 2.0,
        rate_limit_burst: int = 4,
    ) -> None:
        if provider not in PROVIDER_DEFAULTS:
            raise ConfigError(
                f"Unsupported provider: {provider}",
                ErrorInfo(
                    code="INVALID_REQUEST",
                    message=f"unsupported provider: {provider}",
                    provider=provider,
                ),
            )

        self.provider_name = provider
        self.timeout = timeout
        self.max_retries = max_retries
        self._bucket = TokenBucket(rps=rate_limit_rps, burst=rate_limit_burst)

        provider_cls = PROVIDERS[provider]
        self._provider = provider_cls(
            api_key=resolve_api_key(provider, api_key),
            base_url=resolve_base_url(provider, base_url),
            model=resolve_default_model(provider, model),
        )

    def generate(
        self,
        prompt: str,
        *,
        model: str | None = None,
        size: str | tuple[int, int] | None = None,
        aspect_ratio: str | tuple[int, int] | None = None,
        num_images: int = 1,
        seed: int | None = None,
        quality: str | None = None,
        timeout: int | None = None,
        provider_options: dict[str, Any] | None = None,
        output: str = "auto",
    ) -> GenerateResult:
        if not prompt or not prompt.strip():
            raise ProviderError(
                "prompt is required",
                ErrorInfo(
                    code="INVALID_REQUEST",
                    message="prompt is required",
                    provider=self.provider_name,
                ),
            )

        normalized = normalize_generate_params(
            size=size,
            aspect_ratio=aspect_ratio,
            quality=quality,
            output=output,
            capability=get_model_capability(
                self.provider_name,
                model or self._provider.default_model,
            ),
        )
        normalized_provider_options = normalize_provider_options(provider_options)

        model_id = model or self._provider.default_model

        req = GenerateRequest(
            prompt=prompt,
            model=model_id,
            size=normalized["size"],
            aspect_ratio=normalized["aspect_ratio"],
            num_images=num_images,
            seed=seed,
            quality=normalized["quality"],
            timeout=timeout,
            provider_options=normalized_provider_options,
            output=normalized["output"],
        )

        self._bucket.acquire()
        result = self._provider.generate(
            req,
            timeout=timeout or self.timeout,
            max_retries=self.max_retries,
        )
        warnings = list(result.metadata.get("warnings", []))
        warnings.extend(normalized["warnings"])
        result.metadata["warnings"] = warnings
        return result

    def batch_generate(
        self,
        requests: list[GenerateRequest | dict[str, Any]],
        *,
        concurrency: int = 4,
        fail_fast: bool = False,
    ) -> list[BatchItemResult]:
        def to_result(item: GenerateRequest | dict[str, Any]) -> BatchItemResult:
            try:
                if isinstance(item, GenerateRequest):
                    payload = {
                        "prompt": item.prompt,
                        "model": item.model,
                        "size": item.size,
                        "aspect_ratio": item.aspect_ratio,
                        "num_images": item.num_images,
                        "seed": item.seed,
                        "quality": item.quality,
                        "timeout": item.timeout,
                        "provider_options": item.provider_options,
                        "output": item.output,
                    }
                else:
                    payload = dict(item)
                result = self.generate(**payload)
                return BatchItemResult(success=True, result=result)
            except Exception as exc:
                err = getattr(exc, "error", None)
                if err is None:
                    err = ErrorInfo(
                        code="PROVIDER_ERROR",
                        message=str(exc),
                        provider=self.provider_name,
                        retryable=False,
                    )
                return BatchItemResult(success=False, error=err)

        results: list[BatchItemResult | None] = [None] * len(requests)
        max_workers = max(1, concurrency)
        with ThreadPoolExecutor(max_workers=max_workers) as ex:
            future_map: dict[Future[BatchItemResult], int] = {}
            next_index = 0
            stop_submit = False

            while next_index < len(requests) and len(future_map) < max_workers:
                future = ex.submit(to_result, requests[next_index])
                future_map[future] = next_index
                next_index += 1

            while future_map:
                done, _ = wait(set(future_map), return_when=FIRST_COMPLETED)
                for future in done:
                    idx = future_map.pop(future)
                    item = future.result()
                    results[idx] = item
                    if fail_fast and not item.success:
                        stop_submit = True

                while (
                    not stop_submit
                    and next_index < len(requests)
                    and len(future_map) < max_workers
                ):
                    future = ex.submit(to_result, requests[next_index])
                    future_map[future] = next_index
                    next_index += 1

        final_results: list[BatchItemResult] = []
        for item in results:
            if item is None:
                final_results.append(
                    BatchItemResult(
                        success=False,
                        error=ErrorInfo(
                            code="PROVIDER_ERROR",
                            message="Item not executed because fail_fast stopped new submissions",
                            provider=self.provider_name,
                        ),
                    )
                )
            else:
                final_results.append(item)
        return final_results
