from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .errors import ErrorInfo


@dataclass(slots=True)
class GenerateRequest:
    prompt: str
    model: str | None = None
    size: str | tuple[int, int] = "square"
    aspect_ratio: str | tuple[int, int] | None = None
    num_images: int = 1
    seed: int | None = None
    quality: str | None = "standard"
    timeout: int | None = None
    provider_options: dict[str, Any] | None = None
    output: str = "auto"


@dataclass(slots=True)
class ImageArtifact:
    url: str | None = None
    b64: str | None = None
    mime_type: str | None = None
    width: int | None = None
    height: int | None = None


@dataclass(slots=True)
class GenerateResult:
    images: list[ImageArtifact]
    metadata: dict[str, Any] = field(default_factory=dict)
    provider: str = ""
    request_id: str | None = None


@dataclass(slots=True)
class BatchItemResult:
    success: bool
    result: GenerateResult | None = None
    error: ErrorInfo | None = None
