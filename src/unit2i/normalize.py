from math import gcd, sqrt
from typing import Any

from .errors import ErrorInfo, ProviderError
from .providers.model_catalog import ModelCapability

VALID_OUTPUTS = {"auto", "url", "b64"}
SIZE_QUALITY_LEVELS = ("low", "standard", "high", "hd", "ultra")


def _pixel_bounds(capability: ModelCapability | None) -> tuple[int, int]:
    if capability and capability.fixed_sizes:
        pixels_list = [w * h for w, h in capability.fixed_sizes]
        return min(pixels_list), max(pixels_list)

    default_pixels = (
        capability.default_square_size * capability.default_square_size
        if capability
        else 1024 * 1024
    )
    min_pixels = (
        capability.min_pixels
        if capability and capability.min_pixels is not None
        else default_pixels
    )
    max_pixels = (
        capability.max_pixels
        if capability and capability.max_pixels is not None
        else default_pixels
    )
    if max_pixels < min_pixels:
        max_pixels = min_pixels
    return min_pixels, max_pixels


def _parse_size(size: str | tuple[int, int]) -> tuple[int, int]:
    if isinstance(size, tuple):
        if len(size) != 2:
            raise ProviderError(
                "Invalid size tuple.",
                ErrorInfo(code="INVALID_REQUEST", message="size must be width,height", provider=""),
            )
        width, height = size
    elif isinstance(size, str):
        cleaned = size.strip().lower().replace(" ", "")
        if "*" not in cleaned:
            raise ProviderError(
                f"Unsupported size format: {size}",
                ErrorInfo(
                    code="INVALID_REQUEST",
                    message="size string must be 'width*height'",
                    provider="",
                ),
            )
        left, right = cleaned.split("*", maxsplit=1)
        try:
            width, height = int(left), int(right)
        except ValueError as exc:
            raise ProviderError(
                f"Unsupported size format: {size}",
                ErrorInfo(
                    code="INVALID_REQUEST",
                    message="size string must be numeric 'width*height'",
                    provider="",
                ),
            ) from exc
    else:
        raise ProviderError(
            "Invalid size type.",
            ErrorInfo(code="INVALID_REQUEST", message="size must be tuple or string", provider=""),
        )

    if width <= 0 or height <= 0:
        raise ProviderError(
            "Invalid size value.",
            ErrorInfo(code="INVALID_REQUEST", message="size must be positive", provider=""),
        )
    return width, height


def _parse_aspect_ratio(aspect_ratio: str | tuple[int, int]) -> tuple[int, int]:
    if isinstance(aspect_ratio, tuple):
        rw, rh = aspect_ratio
    elif isinstance(aspect_ratio, str):
        cleaned = aspect_ratio.strip().replace(" ", "")
        if ":" not in cleaned:
            raise ProviderError(
                f"Unsupported aspect ratio: {aspect_ratio}",
                ErrorInfo(
                    code="UNSUPPORTED_ASPECT_RATIO",
                    message="aspect_ratio must be 'w:h' or tuple",
                    provider="",
                ),
            )
        left, right = cleaned.split(":", maxsplit=1)
        try:
            rw, rh = int(left), int(right)
        except ValueError as exc:
            raise ProviderError(
                f"Unsupported aspect ratio: {aspect_ratio}",
                ErrorInfo(
                    code="UNSUPPORTED_ASPECT_RATIO",
                    message="aspect_ratio must be numeric 'w:h'",
                    provider="",
                ),
            ) from exc
    else:
        raise ProviderError(
            "Invalid aspect_ratio type.",
            ErrorInfo(
                code="INVALID_REQUEST",
                message="aspect_ratio must be tuple or string",
                provider="",
            ),
        )

    if rw <= 0 or rh <= 0:
        raise ProviderError(
            "Invalid aspect ratio value.",
            ErrorInfo(
                code="INVALID_REQUEST",
                message="aspect ratio must be positive",
                provider="",
            ),
        )
    d = gcd(rw, rh)
    return rw // d, rh // d


def _aspect_ratio_from_size(size: tuple[int, int]) -> str:
    w, h = size
    d = gcd(w, h)
    return f"{w // d}:{h // d}"


def _pick_fixed_size(
    fixed_sizes: set[tuple[int, int]],
    *,
    target_ratio: float,
    target_pixels: int,
) -> tuple[int, int]:
    ratio_scored = []
    for size in fixed_sizes:
        w, h = size
        ratio_scored.append((abs((w / h) - target_ratio), size))

    min_ratio_diff = min(score for score, _ in ratio_scored)
    ratio_candidates = [
        size for score, size in ratio_scored if abs(score - min_ratio_diff) < 1e-12
    ]

    def pixel_distance(size: tuple[int, int]) -> int:
        w, h = size
        return abs((w * h) - target_pixels)

    return min(ratio_candidates, key=pixel_distance)


def _validate_size_for_capability(
    size: tuple[int, int], capability: ModelCapability | None
) -> None:
    if capability is None:
        return

    width, height = size
    pixels = width * height

    if capability.min_pixels is not None and pixels < capability.min_pixels:
        raise ProviderError(
            "Image size is below model minimum pixels",
            ErrorInfo(code="UNSUPPORTED_SIZE", message="size below minimum pixels", provider=""),
        )

    if capability.max_pixels is not None and pixels > capability.max_pixels:
        raise ProviderError(
            "Image size exceeds model maximum pixels",
            ErrorInfo(code="UNSUPPORTED_SIZE", message="size above maximum pixels", provider=""),
        )

    ratio = width / height
    if capability.min_aspect_ratio is not None and ratio < capability.min_aspect_ratio:
        raise ProviderError(
            "Image aspect ratio is not supported by model",
            ErrorInfo(
                code="UNSUPPORTED_ASPECT_RATIO",
                message="aspect ratio below model limit",
                provider="",
            ),
        )

    if capability.max_aspect_ratio is not None and ratio > capability.max_aspect_ratio:
        raise ProviderError(
            "Image aspect ratio is not supported by model",
            ErrorInfo(
                code="UNSUPPORTED_ASPECT_RATIO",
                message="aspect ratio above model limit",
                provider="",
            ),
        )

    if capability.fixed_sizes and size not in capability.fixed_sizes:
        raise ProviderError(
            "Image size is not in model supported fixed sizes",
            ErrorInfo(
                code="UNSUPPORTED_SIZE",
                message="size is not in model fixed size list",
                provider="",
            ),
        )


def _adjust_size_to_capability(
    size: tuple[int, int],
    capability: ModelCapability | None,
) -> tuple[tuple[int, int], bool]:
    width, height = size
    adjusted = False

    if capability is None:
        return (width, height), adjusted

    pixels = width * height
    if capability.min_pixels is not None and pixels < capability.min_pixels:
        factor = sqrt(capability.min_pixels / pixels)
        width = max(1, int(round(width * factor)))
        height = max(1, int(round(height * factor)))
        while width * height < capability.min_pixels:
            width += 1
        adjusted = True

    pixels = width * height
    if capability.max_pixels is not None and pixels > capability.max_pixels:
        factor = sqrt(capability.max_pixels / pixels)
        width = max(1, int(round(width * factor)))
        height = max(1, int(round(height * factor)))
        while width * height > capability.max_pixels and width > 1:
            width -= 1
        adjusted = True

    if capability.fixed_sizes and (width, height) not in capability.fixed_sizes:
        width, height = _pick_fixed_size(
            capability.fixed_sizes,
            target_ratio=width / height,
            target_pixels=width * height,
        )
        adjusted = True

    return (width, height), adjusted


def _resolve_from_size(
    size: str | tuple[int, int],
    capability: ModelCapability | None,
) -> tuple[tuple[int, int], str, str, list[str]]:
    warnings: list[str] = []
    final_size = _parse_size(size)
    final_size, adjusted = _adjust_size_to_capability(final_size, capability)
    if adjusted:
        warnings.append("SIZE_ADJUSTED_FOR_MODEL_LIMITS")

    _validate_size_for_capability(final_size, capability)
    final_aspect = _aspect_ratio_from_size(final_size)

    min_pixels, max_pixels = _pixel_bounds(capability)
    pixels = final_size[0] * final_size[1]
    if max_pixels == min_pixels:
        level_index = 1
    else:
        rank = (pixels - min_pixels) / (max_pixels - min_pixels)
        rank = max(0.0, min(1.0, rank))
        level_index = int(round(rank * (len(SIZE_QUALITY_LEVELS) - 1)))
    quality_level = SIZE_QUALITY_LEVELS[level_index]
    final_quality = "hd" if quality_level in {"hd", "ultra"} else "standard"
    return final_size, final_aspect, final_quality, warnings


def _resolve_from_aspect_quality(
    aspect_ratio: str | tuple[int, int],
    quality: str | None,
    capability: ModelCapability | None,
) -> tuple[tuple[int, int], str, str, list[str]]:
    warnings: list[str] = []
    rw, rh = _parse_aspect_ratio(aspect_ratio)

    quality_level = "standard" if quality is None else quality.strip().lower()
    if quality_level not in SIZE_QUALITY_LEVELS:
        quality_level = "standard"
        warnings.append("QUALITY_FALLBACK_TO_STANDARD")

    min_pixels, max_pixels = _pixel_bounds(capability)
    level_index = SIZE_QUALITY_LEVELS.index(quality_level)
    rank = level_index / (len(SIZE_QUALITY_LEVELS) - 1)
    target_pixels = int(round(min_pixels + (max_pixels - min_pixels) * rank))

    scale = sqrt(target_pixels / (rw * rh))
    width = max(1, int(round(rw * scale)))
    height = max(1, int(round(rh * scale)))
    proposed_size = (width, height)

    if capability and capability.fixed_sizes:
        final_size = _pick_fixed_size(
            capability.fixed_sizes,
            target_ratio=rw / rh,
            target_pixels=target_pixels,
        )
        adjusted = final_size != proposed_size
    else:
        final_size, adjusted = _adjust_size_to_capability(proposed_size, capability)

    if adjusted:
        warnings.append("SIZE_ADJUSTED_FOR_MODEL_LIMITS")

    _validate_size_for_capability(final_size, capability)
    final_aspect = _aspect_ratio_from_size(final_size)
    final_quality = "hd" if quality_level in {"hd", "ultra"} else "standard"

    if capability and capability.fixed_sizes and final_quality == "hd":
        final_quality = "standard"
        warnings.append("QUALITY_FALLBACK_TO_STANDARD")

    return final_size, final_aspect, final_quality, warnings


def normalize_generate_params(
    *,
    size: str | tuple[int, int] | None,
    aspect_ratio: str | tuple[int, int] | None,
    quality: str | None,
    output: str,
    capability: ModelCapability | None = None,
) -> dict[str, Any]:
    if size not in (None, ""):
        final_size, normalized_aspect, final_quality, warnings = _resolve_from_size(
            size,
            capability,
        )
        if aspect_ratio is not None:
            warnings.append("SIZE_OVERRIDES_ASPECT_RATIO")
    elif aspect_ratio is not None:
        final_size, normalized_aspect, final_quality, warnings = _resolve_from_aspect_quality(
            aspect_ratio,
            quality,
            capability,
        )
    else:
        raise ProviderError(
            "size and aspect_ratio are both missing",
            ErrorInfo(
                code="INVALID_REQUEST",
                message="either size or aspect_ratio must be provided",
                provider="",
            ),
        )

    if output not in VALID_OUTPUTS:
        raise ProviderError(
            f"Unsupported output mode: {output}",
            ErrorInfo(code="INVALID_REQUEST", message=f"unsupported output: {output}", provider=""),
        )
    if capability and capability.supported_outputs and output not in capability.supported_outputs:
        raise ProviderError(
            f"Unsupported output mode: {output}",
            ErrorInfo(code="INVALID_REQUEST", message=f"unsupported output: {output}", provider=""),
        )

    return {
        "size": final_size,
        "aspect_ratio": normalized_aspect,
        "quality": final_quality,
        "output": output,
        "warnings": warnings,
    }
