# Unit2I

Unit2I 是一个统一文生图 SDK（v0.1），当前支持：
- DashScope
- Volcengine

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
    aspect_ratio="1:1",
    output="auto",
)

for img in result.images:
    print(img.url or "(only b64 returned)")
```

## 环境变量

- `UNIT2I_DASHSCOPE_API_KEY`
- `UNIT2I_DASHSCOPE_BASE_URL`
- `UNIT2I_VOLC_API_KEY`
- `UNIT2I_VOLC_BASE_URL`

## 开发

```bash
uv run ruff check .
uv run pytest
```
