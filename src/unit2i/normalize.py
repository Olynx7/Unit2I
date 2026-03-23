from typing import Any

from .errors import ErrorInfo, ProviderError


SIZE_PRESETS: dict[str, tuple[int, int]] = {
    "square": (1024, 1024),
    "portrait": (768, 1024),
    "landscape": (1024, 768),
}

VALID_ASPECT_RATIOS = {"1:1", "4:3", "3:4", "16:9", "9:16"}
VALID_OUTPUTS = {"auto", "url", "b64"}
VALID_QUALITIES = {"standard", "hd"}


def normalize_size(size: str | tuple[int, int]) -> tuple[int, int]:
    if isinstance(size, tuple):
        w, h = size
        if w <= 0 or h <= 0:
            raise ProviderError(
                "Invalid size tuple.",
                ErrorInfo(code="INVALID_REQUEST", message="size must be positive", provider=""),
            )
        return w, h

    if size not in SIZE_PRESETS:
        raise ProviderError(
            f"Unsupported size preset: {size}",
            ErrorInfo(code="UNSUPPORTED_SIZE", message=f"unsupported size: {size}", provider=""),
        )
    return SIZE_PRESETS[size]


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


def validate_output(output: str) -> str:
    if output not in VALID_OUTPUTS:
        raise ProviderError(
            f"Unsupported output mode: {output}",
            ErrorInfo(code="INVALID_REQUEST", message=f"unsupported output: {output}", provider=""),
        )
    return output


def normalize_generate_params(
    *,
    size: str | tuple[int, int],
    aspect_ratio: str | tuple[int, int] | None,
    quality: str | None,
    output: str,
    size_overrides_aspect: bool,
) -> dict[str, Any]:
    warnings: list[str] = []
    final_size = normalize_size(size)
    final_aspect = normalize_aspect_ratio(aspect_ratio)

    if size_overrides_aspect:
        warnings.append("SIZE_OVERRIDES_ASPECT_RATIO")

    final_quality = normalize_quality(quality, warnings)
    final_output = validate_output(output)

    return {
        "size": final_size,
        "aspect_ratio": final_aspect,
        "quality": final_quality,
        "output": final_output,
        "warnings": warnings,
    }
