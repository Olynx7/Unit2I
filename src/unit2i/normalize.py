from math import gcd, sqrt
from typing import Any

from .errors import ErrorInfo, ProviderError
from .model_catalog import ModelCapability

SIZE_PRESETS: dict[str, tuple[int, int]] = {
    "square": (1024, 1024),
    "portrait": (768, 1024),
    "landscape": (1024, 768),
}

VALID_ASPECT_RATIOS = {"1:1", "4:3", "3:4", "16:9", "9:16"}
VALID_OUTPUTS = {"auto", "url", "b64"}
VALID_QUALITIES = {"standard", "hd"}


def normalize_size(
    size: str | tuple[int, int], capability: ModelCapability | None = None
) -> tuple[int, int]:
    if isinstance(size, tuple):
        w, h = size
        if w <= 0 or h <= 0:
            raise ProviderError(
                "Invalid size tuple.",
                ErrorInfo(code="INVALID_REQUEST", message="size must be positive", provider=""),
            )
        return w, h

    size_presets = capability.size_presets if capability else SIZE_PRESETS
    if size not in size_presets:
        raise ProviderError(
            f"Unsupported size preset: {size}",
            ErrorInfo(code="UNSUPPORTED_SIZE", message=f"unsupported size: {size}", provider=""),
        )
    return size_presets[size]


def normalize_aspect_ratio(aspect_ratio: str | tuple[int, int] | None) -> str | None:
    if aspect_ratio is None:
        return None
    if isinstance(aspect_ratio, tuple):
        rw, rh = aspect_ratio
        if rw <= 0 or rh <= 0:
            raise ProviderError(
                "Invalid aspect ratio tuple.",
                ErrorInfo(
                    code="INVALID_REQUEST",
                    message="aspect ratio must be positive",
                    provider="",
                ),
            )
        return f"{rw}:{rh}"

    if aspect_ratio not in VALID_ASPECT_RATIOS:
        raise ProviderError(
            f"Unsupported aspect ratio: {aspect_ratio}",
            ErrorInfo(
                code="UNSUPPORTED_ASPECT_RATIO",
                message=f"unsupported aspect ratio: {aspect_ratio}",
                provider="",
            ),
        )
    return aspect_ratio


def normalize_quality(quality: str | None, warnings: list[str]) -> str:
    if quality is None:
        return "standard"
    if quality in VALID_QUALITIES:
        return quality
    warnings.append("QUALITY_FALLBACK_TO_STANDARD")
    return "standard"


def normalize_quality_with_capability(
    quality: str | None,
    warnings: list[str],
    capability: ModelCapability | None,
) -> str:
    final_quality = normalize_quality(quality, warnings)
    if capability and capability.supported_qualities:
        if final_quality not in capability.supported_qualities:
            warnings.append("QUALITY_FALLBACK_TO_STANDARD")
            return "standard"
    return final_quality


def validate_output(output: str) -> str:
    if output not in VALID_OUTPUTS:
        raise ProviderError(
            f"Unsupported output mode: {output}",
            ErrorInfo(code="INVALID_REQUEST", message=f"unsupported output: {output}", provider=""),
        )
    return output


def validate_output_with_capability(output: str, capability: ModelCapability | None) -> str:
    final_output = validate_output(output)
    if (
        capability
        and capability.supported_outputs
        and final_output not in capability.supported_outputs
    ):
        raise ProviderError(
            f"Unsupported output mode: {output}",
            ErrorInfo(code="INVALID_REQUEST", message=f"unsupported output: {output}", provider=""),
        )
    return final_output


def _parse_ratio(ratio: str) -> tuple[int, int]:
    left, right = ratio.split(":", maxsplit=1)
    return int(left), int(right)


def _size_from_aspect_ratio(ratio: str, base_side: int = 1024) -> tuple[int, int]:
    rw, rh = _parse_ratio(ratio)
    if rw >= rh:
        width = base_side
        height = max(1, int(round(base_side * rh / rw)))
    else:
        height = base_side
        width = max(1, int(round(base_side * rw / rh)))
    return width, height


def _aspect_ratio_from_size(size: tuple[int, int]) -> str:
    w, h = size
    d = gcd(w, h)
    return f"{w // d}:{h // d}"


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


def _fit_size_to_capability_pixel_range(
    size: tuple[int, int], capability: ModelCapability | None
) -> tuple[int, int]:
    if capability is None:
        return size

    width, height = size
    pixels = width * height

    if capability.min_pixels is not None and pixels < capability.min_pixels:
        factor = sqrt(capability.min_pixels / pixels)
        width = max(1, int(round(width * factor)))
        height = max(1, int(round(height * factor)))
        while width * height < capability.min_pixels:
            width += 1

    pixels = width * height
    if capability.max_pixels is not None and pixels > capability.max_pixels:
        factor = sqrt(capability.max_pixels / pixels)
        width = max(1, int(round(width * factor)))
        height = max(1, int(round(height * factor)))
        while width * height > capability.max_pixels and width > 1:
            width -= 1

    return width, height


def normalize_generate_params(
    *,
    size: str | tuple[int, int],
    aspect_ratio: str | tuple[int, int] | None,
    quality: str | None,
    output: str,
    capability: ModelCapability | None = None,
) -> dict[str, Any]:
    warnings: list[str] = []
    final_aspect = normalize_aspect_ratio(aspect_ratio)

    default_square = capability.default_square_size if capability else 1024
    derived_from_aspect = False
    if final_aspect is not None and size == "square":
        final_size = _size_from_aspect_ratio(final_aspect, base_side=default_square)
        derived_from_aspect = True
    else:
        final_size = normalize_size(size, capability=capability)
        if final_aspect is not None:
            warnings.append("SIZE_OVERRIDES_ASPECT_RATIO")

    if derived_from_aspect:
        adjusted_size = _fit_size_to_capability_pixel_range(final_size, capability)
        if adjusted_size != final_size:
            final_size = adjusted_size
            warnings.append("SIZE_ADJUSTED_FOR_MODEL_LIMITS")

    _validate_size_for_capability(final_size, capability)
    normalized_aspect = final_aspect or _aspect_ratio_from_size(final_size)

    final_quality = normalize_quality_with_capability(quality, warnings, capability)
    final_output = validate_output_with_capability(output, capability)

    return {
        "size": final_size,
        "aspect_ratio": normalized_aspect,
        "quality": final_quality,
        "output": final_output,
        "warnings": warnings,
    }
