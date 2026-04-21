from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ModelCapability:
    model_id: str
    default_square_size: int
    min_pixels: int | None = None
    max_pixels: int | None = None
    min_aspect_ratio: float | None = None
    max_aspect_ratio: float | None = None
    fixed_sizes: set[tuple[int, int]] | None = None
    supported_outputs: set[str] | None = None


@dataclass(frozen=True, slots=True)
class ProviderCatalog:
    default_model: str
    models: dict[str, ModelCapability]


CATALOGS: dict[str, ProviderCatalog] = {
    "dashscope": ProviderCatalog(
        default_model="wan2.6-t2i",
        models={
            "wan2.6-t2i": ModelCapability(
                model_id="wan2.6-t2i",
                default_square_size=1280,
                min_pixels=1280 * 1280,
                max_pixels=1440 * 1440,
                min_aspect_ratio=1 / 4,
                max_aspect_ratio=4,
                supported_outputs={"auto", "url", "b64"},
            ),
            "qwen-image-2.0-pro": ModelCapability(
                model_id="qwen-image-2.0-pro",
                default_square_size=2048,
                min_pixels=512 * 512,
                max_pixels=2048 * 2048,
                supported_outputs={"auto", "url", "b64"},
            ),
            "z-image-turbo": ModelCapability(
                model_id="z-image-turbo",
                default_square_size=1024,
                min_pixels=None,
                max_pixels=None,
                fixed_sizes={(1024, 1024), (1024, 1536), (1536, 1024)},
                supported_outputs={"auto", "url", "b64"},
            ),
        },
    ),
    "volcengine": ProviderCatalog(
        default_model="doubao-seedream-4-5",
        models={
            "doubao-seedream-4-0-250828": ModelCapability(
                model_id="doubao-seedream-4-0-250828",
                default_square_size=2048,
                min_pixels=1280 * 720,
                max_pixels=4096 * 4096,
                min_aspect_ratio=1 / 16,
                max_aspect_ratio=16,
                supported_outputs={"auto", "url", "b64"},
            ),
            "doubao-seedream-4-5": ModelCapability(
                model_id="doubao-seedream-4-5",
                default_square_size=2048,
                min_pixels=2560 * 1440,
                max_pixels=4096 * 4096,
                min_aspect_ratio=1 / 16,
                max_aspect_ratio=16,
                supported_outputs={"auto", "url", "b64"},
            ),
            "doubao-seedream-5-lite": ModelCapability(
                model_id="doubao-seedream-5-lite",
                default_square_size=2048,
                min_pixels=2560 * 1440,
                max_pixels=10404496,
                min_aspect_ratio=1 / 16,
                max_aspect_ratio=16,
                supported_outputs={"auto", "url", "b64"},
            ),
        },
    ),
}


def get_provider_default_model(provider: str) -> str | None:
    catalog = CATALOGS.get(provider)
    if catalog is None:
        return None
    return catalog.default_model


def get_model_capability(provider: str, model: str) -> ModelCapability | None:
    catalog = CATALOGS.get(provider)
    if catalog is None:
        return None
    return catalog.models.get(model)


def validate_catalogs() -> list[str]:
    errors: list[str] = []

    for provider, catalog in CATALOGS.items():
        if catalog.default_model not in catalog.models:
            errors.append(
                f"{provider}: default_model '{catalog.default_model}' is missing from models"
            )

        for model_id, capability in catalog.models.items():
            if capability.default_square_size <= 0:
                errors.append(f"{provider}/{model_id}: default_square_size must be positive")

            if capability.fixed_sizes is not None:
                for fixed_w, fixed_h in capability.fixed_sizes:
                    if fixed_w <= 0 or fixed_h <= 0:
                        errors.append(f"{provider}/{model_id}: fixed_sizes must be positive")
                if capability.min_pixels is not None or capability.max_pixels is not None:
                    errors.append(
                        f"{provider}/{model_id}: "
                        "fixed_sizes models must not set min_pixels/max_pixels"
                    )

            if (
                capability.min_pixels is not None
                and capability.max_pixels is not None
                and capability.min_pixels > capability.max_pixels
            ):
                errors.append(f"{provider}/{model_id}: min_pixels cannot exceed max_pixels")

            if (
                capability.min_aspect_ratio is not None
                and capability.max_aspect_ratio is not None
                and capability.min_aspect_ratio > capability.max_aspect_ratio
            ):
                errors.append(
                    f"{provider}/{model_id}: min_aspect_ratio cannot exceed max_aspect_ratio"
                )

    return errors
