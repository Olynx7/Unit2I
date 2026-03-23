from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class ErrorInfo:
    code: str
    message: str
    provider: str
    request_id: str | None = None
    retryable: bool = False
    raw: dict[str, Any] | str | None = None


class Unit2IError(Exception):
    def __init__(self, message: str, error: ErrorInfo | None = None) -> None:
        super().__init__(message)
        self.error = error


class ConfigError(Unit2IError):
    pass


class ProviderError(Unit2IError):
    pass


class OutputError(Unit2IError):
    pass
