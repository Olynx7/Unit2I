# Unit2I

Unit2I 是一个统一文生图（Text-to-Image）Python SDK，目标是用一致的接口对接不同云厂商能力。

当前版本（v0.1.0）支持：
- DashScope
- Volcengine

## 特性

- 统一调用接口：同一套 `generate` / `batch_generate` API 适配多个 provider
- 能力目录驱动：模型尺寸、像素范围、输出能力集中管理
- Provider 职责清晰：provider 只负责协议映射和请求发送
- 可扩展 provider 参数：通过 `provider_options.transport` 和 `provider_options.provider_payload` 透传定制项
- 内置基础限流：默认 token bucket（`2 rps / burst 4`）

## 安装

### 方式 1：开发环境（推荐）

```bash
uv sync --extra dev
```

### 方式 2：本地可编辑安装

```bash
pip install -e .
```

## 快速开始

```python
from unit2i import Unit2I

client = Unit2I(provider="dashscope")
result = client.generate(
    prompt="a red fox in snow",
    model="wan2.6-t2i",
    aspect_ratio="1:1",
    output="auto",
)

for img in result.images:
    print(img.url or "(only b64 returned)")
```

## 核心 API

### `Unit2I(...)`

```python
Unit2I(
    provider: str,
    model: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    timeout: int = 60,
    max_retries: int = 2,
    rate_limit_rps: float = 2.0,
    rate_limit_burst: int = 4,
)
```

### `generate(...)`

常用参数：
- `prompt`: 文本提示词（必填）
- `model`: 模型名（可选，默认使用 provider 默认模型）
- `size`: 图像尺寸，支持别名或 `(width, height)`
- `aspect_ratio`: 比例（如 `"16:9"`）
- `num_images`: 生成张数
- `seed`: 随机种子
- `quality`: 质量档位
- `provider_options`: provider 透传选项
- `output`: 输出模式（如 `auto`）

### `batch_generate(...)`

```python
requests = [
    {"prompt": "a cat with sunglasses"},
    {"prompt": "a mountain at sunrise", "aspect_ratio": "16:9"},
]

batch = client.batch_generate(requests, concurrency=4, fail_fast=False)
for item in batch:
    if item.success:
        print(item.result.request_id)
    else:
        print(item.error.code, item.error.message)
```

## `provider_options` 结构

`provider_options` 仅支持以下结构：

```python
provider_options = {
    "transport": {
        "endpoint": "/api/v1/services/aigc/multimodal-generation/generation",
        "headers": {"X-Trace-Id": "demo"},
    },
    "provider_payload": {
        "parameters": {"watermark": False},
    },
}
```

Volcengine 示例：

```python
provider_options = {
    "transport": {"endpoint": "/api/v3/images/generations"},
    "provider_payload": {"watermark": False},
}
```

## 环境变量

- `UNIT2I_DASHSCOPE_API_KEY`
- `UNIT2I_DASHSCOPE_BASE_URL`
- `UNIT2I_VOLC_API_KEY`
- `UNIT2I_VOLC_BASE_URL`

默认 `base_url`：
- DashScope: `https://dashscope.aliyuncs.com`
- Volcengine: `https://ark.cn-beijing.volces.com`

默认 endpoint：
- DashScope: `/api/v1/services/aigc/multimodal-generation/generation`
- Volcengine: `/api/v3/images/generations`

## 开发

```bash
uv run ruff check .
uv run pytest
```

## 开源协议

本项目采用 MIT License。

详情请见 [LICENSE](LICENSE)。
