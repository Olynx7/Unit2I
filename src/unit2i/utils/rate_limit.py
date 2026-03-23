from __future__ import annotations

import threading
import time


class TokenBucket:
    def __init__(self, *, rps: float, burst: int) -> None:
        self.capacity = float(max(1, burst))
        self.tokens = self.capacity
        self.rps = max(0.1, rps)
        self.updated_at = time.monotonic()
        self._lock = threading.Lock()

    def acquire(self) -> None:
        while True:
            with self._lock:
                now = time.monotonic()
                elapsed = now - self.updated_at
                self.updated_at = now
                self.tokens = min(self.capacity, self.tokens + elapsed * self.rps)
                if self.tokens >= 1.0:
                    self.tokens -= 1.0
                    return
            time.sleep(0.01)
