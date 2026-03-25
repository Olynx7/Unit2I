# Unit2I

Unit2I 是一个统一文生图 SDK（v0.1），当前支持：
- DashScope
- Volcengine

当前版本采用“能力目录 + 统一适配层”架构：
- 模型能力（尺寸、像素范围、输出能力）集中在 `model_catalog`
- provider 仅负责协议映射
- `provider_options` 仅支持新结构：`transport` + `provider_payload`

## 安装

```bash
uv sync --extra dev
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

## provider_options（最新规范）

`provider_options` 只支持以下结构：

```python
provider_options={
    "transport": {
        "endpoint": "/api/v1/services/aigc/multimodal-generation/generation",
        "headers": {"X-Trace-Id": "demo"},
    },
    "provider_payload": {
        # DashScope 示例
        "parameters": {"watermark": False},
    },
}
```

Volcengine 场景示例：

```python
provider_options={
    "transport": {"endpoint": "/api/v3/images/generations"},
    "provider_payload": {"watermark": False},
}
```

## 环境变量

- `UNIT2I_DASHSCOPE_API_KEY`
- `UNIT2I_DASHSCOPE_BASE_URL`
- `UNIT2I_VOLC_API_KEY`
- `UNIT2I_VOLC_BASE_URL`

默认值：
- DashScope base_url: `https://dashscope.aliyuncs.com`
- Volcengine base_url: `https://ark.cn-beijing.volces.com`

## Provider 协议参考

- DashScope 对照文档：[plan/DASHSCOPE_API.md](plan/DASHSCOPE_API.md)
- Volcengine 对照文档：[plan/VOLC_API.md](plan/VOLC_API.md)

实现约定：
- DashScope 默认 endpoint 为 `/api/v1/services/aigc/multimodal-generation/generation`
- Volcengine 默认 endpoint 为 `/api/v3/images/generations`

## 相关文档

- 设计说明：[plan/DESIGN.md](plan/DESIGN.md)
- 调用示例：[plan/EXAMPLES.md](plan/EXAMPLES.md)
- 规划索引：[plan/README.md](plan/README.md)

## 开发

```bash
uv run ruff check .
uv run pytest
```
