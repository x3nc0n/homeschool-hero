from __future__ import annotations

import asyncio
from collections import defaultdict, deque
from dataclasses import dataclass
from time import monotonic


@dataclass(frozen=True, slots=True)
class RateLimitRule:
    name: str
    max_requests: int
    window_seconds: int


class RateLimiter:
    def __init__(self) -> None:
        self._requests: dict[tuple[str, str], deque[float]] = defaultdict(deque)
        self._lock = asyncio.Lock()

    async def check(self, rule: RateLimitRule, key: str) -> tuple[bool, int]:
        now = monotonic()
        bucket_key = (rule.name, key)
        async with self._lock:
            bucket = self._requests[bucket_key]
            cutoff = now - rule.window_seconds
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()
            if len(bucket) >= rule.max_requests:
                retry_after = max(1, int(rule.window_seconds - (now - bucket[0])))
                return False, retry_after
            bucket.append(now)
            return True, 0

