from __future__ import annotations

from abc import ABC, abstractmethod

from ..types import GenerateRequest, GenerateResult


class BaseProvider(ABC):
    name: str

    def __init__(self, *, api_key: str | None, base_url: str, model: str) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.default_model = model

    @abstractmethod
    def generate(self, req: GenerateRequest, *, timeout: int, max_retries: int) -> GenerateResult:
        raise NotImplementedError
