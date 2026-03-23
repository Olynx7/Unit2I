from __future__ import annotations

from .dashscope import DashScopeProvider
from .volcengine import VolcengineProvider

PROVIDERS = {
    "dashscope": DashScopeProvider,
    "volcengine": VolcengineProvider,
}
