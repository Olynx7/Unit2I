# %% [markdown]
# # Unit2I 全量生图测试
#
# 本 Notebook 覆盖 DashScope 和 Volcengine 两个平台全部模型的生图场景，包括：
# - 不同 aspect_ratio / size / quality / output 模式
# - 多图生成 (num_images)
# - 批量生成 (batch_generate)
#
# 运行前确保 `.env` 中配置了对应平台的 API Key。

# %%
import json
import os
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

import httpx

repo_root = Path(__file__).resolve().parent.parent
src_path = repo_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

env_path = repo_root / ".env"
if env_path.exists():
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

from unit2i import Unit2I  # noqa: E402
from unit2i.errors import ProviderError  # noqa: E402


@dataclass
class TestCase:
    name: str
    provider: str
    model: str | None = None
    prompt: str = "a cat with sunglasses, cinematic lighting"
    aspect_ratio: str | None = "1:1"
    size: str | None = None
    quality: str | None = "standard"
    output: str = "url"
    num_images: int = 1
    seed: int | None = 42


@dataclass
class TestResult:
    case: TestCase
    success: bool
    error: str | None = None
    latency_ms: float = 0
    image_urls: list[str] = field(default_factory=list)
    b64_data: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    request_id: str | None = None
    image_count: int = 0


def run_test(client: Unit2I, case: TestCase) -> TestResult:
    start = time.perf_counter()
    try:
        result = client.generate(
            prompt=case.prompt,
            model=case.model,
            size=case.size,
            aspect_ratio=case.aspect_ratio,
            quality=case.quality,
            output=case.output,
            num_images=case.num_images,
            seed=case.seed,
        )
        elapsed = (time.perf_counter() - start) * 1000
        urls = [img.url or f"(b64:{len(img.b64 or '')}chars)" for img in result.images]
        b64s = [img.b64 for img in result.images if img.b64]
        return TestResult(
            case=case,
            success=True,
            image_urls=urls,
            latency_ms=elapsed,
            b64_data=b64s,
            warnings=result.metadata.get("warnings", []),
            request_id=result.request_id,
            image_count=len(result.images),
        )
    except ProviderError as e:
        elapsed = (time.perf_counter() - start) * 1000
        msg = f"{e.error.code}: {e.error.message}" if e.error else str(e)
        return TestResult(case=case, success=False, error=msg, latency_ms=elapsed)
    except Exception as e:
        elapsed = (time.perf_counter() - start) * 1000
        return TestResult(case=case, success=False, error=str(e), latency_ms=elapsed)


def check_ready(provider: str) -> bool:
    env_map = {"dashscope": "UNIT2I_DASHSCOPE_API_KEY", "volcengine": "UNIT2I_VOLC_API_KEY"}
    return bool(os.getenv(env_map.get(provider, "")))


def download_images(results, output_dir: Path):
    """Download all URL and b64 images from test results to output_dir."""
    output_dir.mkdir(parents=True, exist_ok=True)
    saved = 0
    with httpx.Client(timeout=httpx.Timeout(30), follow_redirects=True) as client:
        for r in results:
            if not r.success:
                continue
            safe_name = re.sub(r'[<>:"/\\|?*]', "_", r.case.name)
            # Download URL images
            for i, url in enumerate(r.image_urls):
                if not url or url.startswith("(b64:"):
                    continue
                try:
                    resp = client.get(url)
                    resp.raise_for_status()
                    ext = ".png"
                    ct = resp.headers.get("content-type", "")
                    if "jpeg" in ct:
                        ext = ".jpg"
                    elif "webp" in ct:
                        ext = ".webp"
                    fname = f"{safe_name}_{i + 1}{ext}"
                    fpath = output_dir / fname
                    fpath.write_bytes(resp.content)
                    saved += 1
                    print(f"  saved: {fname}")
                except Exception as e:
                    print(f"  download failed [{r.case.name}]: {e}")
            # Save b64 images
            for i, b64_str in enumerate(r.b64_data):
                if not b64_str:
                    continue
                try:
                    import base64
                    data = base64.b64decode(b64_str)
                    fname = f"{safe_name}_b64_{i + 1}.png"
                    fpath = output_dir / fname
                    fpath.write_bytes(data)
                    saved += 1
                    print(f"  saved: {fname}")
                except Exception as e:
                    print(f"  b64 decode failed [{r.case.name}]: {e}")
    return saved


def print_result(r: TestResult, idx: int, total: int):
    status = "OK" if r.success else "FAIL"
    print(f"[{idx}/{total}] {status}  {r.case.name}")
    if r.success:
        print(f"     {r.latency_ms:.0f}ms  images={r.image_count}  rid={r.request_id}")
        if r.warnings:
            print(f"     warnings={r.warnings}")
    else:
        print(f"     error={r.error}")


print("Setup complete - ready to test")

# %% [markdown]
# ## DashScope 测试

# %%
dashscope_cases = [
    # wan2.6-t2i
    TestCase(
        "wan2.6-t2i default 1_1",
        "dashscope",
        "wan2.6-t2i",
        prompt="a peaceful snow village, watercolor style",
    ),
    TestCase(
        "wan2.6-t2i aspect_ratio_16_9",
        "dashscope",
        "wan2.6-t2i",
        aspect_ratio="16:9",
        prompt="a vast grassland at sunset",
    ),
    TestCase(
        "wan2.6-t2i size_1440x720",
        "dashscope",
        "wan2.6-t2i",
        size="1440*720",
        prompt="underwater world, coral reef and tropical fish",
    ),
    TestCase(
        "wan2.6-t2i output_b64",
        "dashscope",
        "wan2.6-t2i",
        output="b64",
        prompt="a blue-eyed ragdoll cat",
    ),
    TestCase(
        "wan2.6-t2i num_images_2",
        "dashscope",
        "wan2.6-t2i",
        num_images=2,
        prompt="a red balloon in blue sky",
    ),
    # qwen-image-2.0-pro
    TestCase(
        "qwen-image-2.0-pro default 1_1",
        "dashscope",
        "qwen-image-2.0-pro",
        prompt="a young woman reading in a cafe, warm lighting",
    ),
    TestCase(
        "qwen-image-2.0-pro quality_high",
        "dashscope",
        "qwen-image-2.0-pro",
        quality="high",
        prompt="futuristic city skyline at night",
    ),
    TestCase(
        "qwen-image-2.0-pro aspect_ratio_9_16",
        "dashscope",
        "qwen-image-2.0-pro",
        aspect_ratio="9:16",
        prompt="a delicate glass vase with cherry blossoms",
    ),
    # z-image-turbo
    TestCase(
        "z-image-turbo default 1024x1024",
        "dashscope",
        "z-image-turbo",
        prompt="a cute robot, line art style",
    ),
    TestCase(
        "z-image-turbo aspect_ratio_2_3",
        "dashscope",
        "z-image-turbo",
        aspect_ratio="2:3",
        prompt="a cherry tree with rainbow fruits, oil painting",
    ),
]

if check_ready("dashscope"):
    print(f"DashScope: {len(dashscope_cases)} test cases ready")
else:
    print("WARNING: UNIT2I_DASHSCOPE_API_KEY not found, skipping DashScope")
    dashscope_cases = []

# %%
dashscope_results = []
if dashscope_cases:
    client = Unit2I(provider="dashscope")
    total = len(dashscope_cases)
    print(f"Running DashScope tests ({total} cases)...\n")
    for i, case in enumerate(dashscope_cases, 1):
        r = run_test(client, case)
        dashscope_results.append(r)
        print_result(r, i, total)
        print()
    passed = sum(1 for r in dashscope_results if r.success)
    t = sum(r.latency_ms for r in dashscope_results)
    print(f"--- DashScope: {passed}/{total} passed, {t / 1000:.1f}s total ---")
else:
    print("DashScope tests skipped (no API key)")

# %% [markdown]
# ## Volcengine 测试

# %%
volcengine_cases = [
    # doubao-seedream-4-5-251128
    TestCase(
        "doubao-seedream-4-5-251128 default 1_1",
        "volcengine",
        "doubao-seedream-4-5-251128",
        prompt="a peaceful snow village, watercolor style",
    ),
    TestCase(
        "doubao-seedream-4-5-251128 aspect_ratio_16_9",
        "volcengine",
        "doubao-seedream-4-5-251128",
        aspect_ratio="16:9",
        prompt="a vast grassland at sunset",
    ),
    TestCase(
        "doubao-seedream-4-5-251128 size_2880x1620",
        "volcengine",
        "doubao-seedream-4-5-251128",
        size="2880*1620",
        prompt="underwater world, coral reef and tropical fish",
    ),
    TestCase(
        "doubao-seedream-4-5-251128 output_b64",
        "volcengine",
        "doubao-seedream-4-5-251128",
        output="b64",
        prompt="a blue-eyed ragdoll cat",
    ),
    TestCase(
        "doubao-seedream-4-5-251128 quality_hd",
        "volcengine",
        "doubao-seedream-4-5-251128",
        quality="hd",
        prompt="a red balloon in blue sky",
    ),
    # doubao-seedream-4-0-250828
    TestCase(
        "doubao-seedream-4-0 default 1_1",
        "volcengine",
        "doubao-seedream-4-0-250828",
        prompt="a young woman reading in a cafe, warm lighting",
    ),
    TestCase(
        "doubao-seedream-4-0 num_images_2",
        "volcengine",
        "doubao-seedream-4-0-250828",
        num_images=1,
        prompt="futuristic city skyline at night",
    ),
    # doubao-seedream-5-0-260128
    TestCase(
        "doubao-seedream-5-0-260128 default 1_1",
        "volcengine",
        "doubao-seedream-5-0-260128",
        prompt="a cute robot, line art style",
    ),
    TestCase(
        "doubao-seedream-5-0-260128 aspect_ratio_9_16",
        "volcengine",
        "doubao-seedream-5-0-260128",
        aspect_ratio="9:16",
        prompt="a cherry tree with rainbow fruits, oil painting",
    ),
]

if check_ready("volcengine"):
    print(f"Volcengine: {len(volcengine_cases)} test cases ready")
else:
    print("WARNING: UNIT2I_VOLC_API_KEY not found, skipping Volcengine")
    volcengine_cases = []

# %%
volcengine_results = []
if volcengine_cases:
    client = Unit2I(provider="volcengine")
    total = len(volcengine_cases)
    print(f"Running Volcengine tests ({total} cases)...\n")
    for i, case in enumerate(volcengine_cases, 1):
        r = run_test(client, case)
        volcengine_results.append(r)
        print_result(r, i, total)
        print()
    passed = sum(1 for r in volcengine_results if r.success)
    t = sum(r.latency_ms for r in volcengine_results)
    print(f"--- Volcengine: {passed}/{total} passed, {t / 1000:.1f}s total ---")
else:
    print("Volcengine tests skipped (no API key)")

# %% [markdown]
# ## 批量生成测试

# %%
batch_prompt = "a minimalist icon of {subject}, pure white background"

if check_ready("dashscope"):
    client = Unit2I(provider="dashscope", model="wan2.6-t2i")
    reqs = [
        {"prompt": batch_prompt.format(subject=s), "aspect_ratio": "1:1", "output": "url"}
        for s in ["star", "moon", "sun"]
    ]
    print(f"DashScope batch: {len(reqs)} requests ...")
    batch = client.batch_generate(reqs, concurrency=2) # type: ignore
    ok = sum(1 for b in batch if b.success)
    print(f"  {ok}/{len(batch)} succeeded")
    for i, b in enumerate(batch):
        s = "OK" if b.success else "FAIL"
        detail = b.result.request_id if b.success else f"{b.error.code}: {b.error.message}" # type: ignore
        print(f"  [{i + 1}] {s}  {detail}")
else:
    print("DashScope batch skipped (no API key)")

print()

if check_ready("volcengine"):
    client = Unit2I(provider="volcengine", model="doubao-seedream-4-5-251128")
    reqs = [
        {"prompt": batch_prompt.format(subject=s), "aspect_ratio": "1:1", "output": "url"}
        for s in ["star", "moon", "sun"]
    ]
    print(f"Volcengine batch: {len(reqs)} requests ...")
    batch = client.batch_generate(reqs, concurrency=2) # type: ignore
    ok = sum(1 for b in batch if b.success)
    print(f"  {ok}/{len(batch)} succeeded")
    for i, b in enumerate(batch):
        s = "OK" if b.success else "FAIL"
        detail = b.result.request_id if b.success else f"{b.error.code}: {b.error.message}" # type: ignore
        print(f"  [{i + 1}] {s}  {detail}")
else:
    print("Volcengine batch skipped (no API key)")

# %% [markdown]
# ## 汇总 & 下载图片

# %%
all_results = dashscope_results + volcengine_results
output_dir = repo_root / "scripts" / "output_images"

if not all_results:
    print("No providers available. Check your .env configuration.")
else:
    total = len(all_results)
    passed = sum(1 for r in all_results if r.success)
    failed = total - passed
    total_time = sum(r.latency_ms for r in all_results)

    provider_stats = {}
    for r in all_results:
        p = r.case.provider
        if p not in provider_stats:
            provider_stats[p] = {"total": 0, "passed": 0, "time": 0.0}
        provider_stats[p]["total"] += 1
        if r.success:
            provider_stats[p]["passed"] += 1
        provider_stats[p]["time"] += r.latency_ms

    print("=" * 50)
    print(f"TOTAL: {passed}/{total} passed  ({total_time / 1000:.1f}s)")
    print("-" * 50)
    for p, s in provider_stats.items():
        avg = s["time"] / max(s["total"], 1)
        print(f"  {p}: {s['passed']}/{s['total']} passed, avg {avg:.0f}ms/image")
    print("=" * 50)

    if failed > 0:
        print("\nFAILURES:")
        for r in all_results:
            if not r.success:
                print(f"  - {r.case.name}: {r.error}")

    # Download all generated images
    url_results = [r for r in all_results if r.success]
    if url_results:
        print(f"\nDownloading {sum(r.image_count for r in url_results)} images to {output_dir} ...")
        saved = download_images(url_results, output_dir)
        print(f"Downloaded {saved} images.")

    # Save results metadata to JSON
    json_path = repo_root / "scripts" / "smoke_test_results.json"
    output_data = []
    for r in all_results:
        output_data.append(
            {
                "name": r.case.name,
                "provider": r.case.provider,
                "model": r.case.model,
                "success": r.success,
                "error": r.error,
                "latency_ms": round(r.latency_ms, 0),
                "image_count": r.image_count,
                "warnings": r.warnings,
                "request_id": r.request_id,
            }
        )
    json_path.write_text(json.dumps(output_data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Results saved to: {json_path}")
