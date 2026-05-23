import time

from unit2i.utils.rate_limit import TokenBucket


def test_token_bucket_acquire_does_not_block_when_tokens_available() -> None:
    bucket = TokenBucket(rps=100.0, burst=10)
    start = time.perf_counter()
    for _ in range(5):
        bucket.acquire()
    elapsed = time.perf_counter() - start
    assert elapsed < 0.1


def test_token_bucket_refills_over_time() -> None:
    bucket = TokenBucket(rps=1000.0, burst=2)
    for _ in range(2):
        bucket.acquire()
    t0 = time.perf_counter()
    bucket.acquire()
    elapsed = time.perf_counter() - t0
    assert 0.0008 < elapsed < 0.2


def test_token_bucket_respects_burst() -> None:
    bucket = TokenBucket(rps=0.1, burst=3)
    start = time.perf_counter()
    for _ in range(3):
        bucket.acquire()
    elapsed = time.perf_counter() - start
    assert elapsed < 0.1
