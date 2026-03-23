# Unit2I 统一文生图 SDK API 设计（Python pip）

本文是 Unit2I 的中文新手版设计文档。目标是提供一套统一 API，对接 DashScope 和 Volcengine，优先保证首个版本可实现、可测试、可发布。

## 1. 目标与范围
- 提供稳定、统一的文生图接口。
- v0.1 仅支持两个 provider：DashScope、Volcengine。
- v0.1 优先支持同步生成与基础批量；异步任务放入 v0.2。
- v0.1 支持显式指定模型与图片比例。
- SDK 层提供超时、重试、基础限流。
- 默认使用环境变量读取密钥和地址。

## 2. 版本路线

### 2.1 v0.1（当前目标）
- 支持 provider：dashscope、volcengine。
- 对外方法：generate、batch_generate。
- output 支持：auto、url、b64。
- 支持参数：model、aspect_ratio（并保留 size 兼容）。
- 统一错误码与异常层级。

### 2.2 v0.2（后续扩展）
- 异步接口：generate_async、JobHandle。
- 输出扩展：path、pil。
- 增加更多 provider。

## 3. 包结构
- 包名：unit2i
- 对外入口：Unit2I 客户端类
- 内部模块：schema、参数归一化、provider 注册、provider 实现、http/retry

## 4. 对外 API（v0.1）

### 4.1 客户端初始化
```python
from unit2i import Unit2I

client = Unit2I(
    provider="dashscope",   # 或 volcengine
    model=None,              # 默认模型，按 provider 决定
    api_key=None,
    base_url=None,
    timeout=60,
    max_retries=2,
    rate_limit_rps=2.0,
    rate_limit_burst=4,
)
```

参数说明：
- provider：必填，当前仅支持 dashscope / volcengine。
- model：可选，设置客户端默认模型，可在 generate 时覆盖。
- api_key：可选，覆盖环境变量。
- base_url：可选，覆盖默认地址。
- timeout：单次请求超时，默认 60 秒。
- max_retries：可重试错误的重试次数，默认 2。
- rate_limit_rps：每秒请求预算，默认 2.0。
- rate_limit_burst：令牌桶突发容量，默认 4。

### 4.2 同步生成
```python
result = client.generate(
    prompt="a red fox in snow",
    model="wanx2.1-t2i-plus",
    aspect_ratio="1:1",
    num_images=1,
    quality="standard",
)
```

签名：
```python
generate(
    prompt: str,
    *,
    model: str | None = None,
    size: str | tuple[int, int] = "square",
    aspect_ratio: str | tuple[int, int] | None = None,
    num_images: int = 1,
    seed: int | None = None,
    quality: str | None = "standard",
    timeout: int | None = None,
    provider_options: dict | None = None,
    output: str = "auto",
) -> GenerateResult
```

说明：
- 其他供应商特有参数统一走 provider_options。
- 首版不承诺 style/sampler/safety 等跨 provider 统一字段。
- model 优先级：方法参数 > 客户端默认 model > provider 默认模型。
- size 与 aspect_ratio 同时传入时，优先使用 size，并在 metadata.warnings 记录提示。

### 4.3 批量生成
```python
batch = client.batch_generate(
    [
        {"prompt": "golden retriever", "size": "square"},
        {"prompt": "snowy mountain", "size": "landscape"},
    ],
    concurrency=4,
)
```

签名：
```python
batch_generate(
    requests: list[GenerateRequest | dict],
    *,
    concurrency: int = 4,
    fail_fast: bool = False,
) -> list[BatchItemResult]
```

## 5. 数据模型

### 5.1 GenerateRequest
```python
GenerateRequest:
    prompt: str
    model: str | None
    size: str | (int, int)
    aspect_ratio: str | (int, int) | None
    num_images: int
    seed: int | None
    quality: str | None
    timeout: int | None
    provider_options: dict | None
    output: str
```

### 5.2 GenerateResult
```python
GenerateResult:
    images: list[ImageArtifact]
    metadata: dict
    provider: str
    request_id: str | None
```

### 5.3 ImageArtifact
```python
ImageArtifact:
    url: str | None
    b64: str | None
    mime_type: str | None
    width: int | None
    height: int | None
```

### 5.4 ErrorInfo（错误数据对象）
```python
ErrorInfo:
    code: str
    message: str
    provider: str
    request_id: str | None
    retryable: bool
    raw: dict | str | None
```

### 5.5 BatchItemResult
```python
BatchItemResult:
    success: bool
    result: GenerateResult | None
    error: ErrorInfo | None
```

## 6. 参数归一化规则

### 6.1 size
- 支持预设：square、portrait、landscape。
- 也支持显式尺寸：(width, height)。
- 预设默认映射：
  - square -> 1024x1024
  - portrait -> 768x1024
  - landscape -> 1024x768
- 供应商不支持精确尺寸时，优先降级到最近尺寸；无法降级时报错 UNSUPPORTED_SIZE。

### 6.2 aspect_ratio
- 支持常见字符串：1:1、4:3、3:4、16:9、9:16。
- 也支持显式比例：(w_ratio, h_ratio)，例如 (16, 9)。
- 如果只传 aspect_ratio，不传 size：
    - SDK 按 provider 默认基准边长换算目标尺寸；
    - 若 provider 不支持该比例，报错 UNSUPPORTED_ASPECT_RATIO。
- 如果同时传 size 与 aspect_ratio：
    - 以 size 为准；
    - 在 metadata.warnings 增加 SIZE_OVERRIDES_ASPECT_RATIO。

### 6.3 quality
- 标准值：standard、hd。
- 不支持 hd 时回退到 standard，并在 metadata.warnings 写入警告。

### 6.4 output（v0.1）
- auto：优先 URL，没有则 base64。
- url：必须有 URL，否则 NO_URL_AVAILABLE。
- b64：只返回 base64。

## 7. 环境变量

### 7.1 DashScope
- UNIT2I_DASHSCOPE_API_KEY
- UNIT2I_DASHSCOPE_BASE_URL

### 7.2 Volcengine
- UNIT2I_VOLC_API_KEY
- UNIT2I_VOLC_BASE_URL

### 7.3 provider 标识
- dashscope
- volcengine

## 8. 重试、超时、限流
- 仅对可重试错误执行重试：网络超时、5xx、限流。
- 默认退避：0.5s、1s、2s（带 jitter）。
- timeout 作用于单次请求。
- 限流采用每个 provider 的令牌桶。

## 9. 标准错误码
- INVALID_REQUEST
- UNSUPPORTED_SIZE
- UNSUPPORTED_ASPECT_RATIO
- PROVIDER_ERROR
- TIMEOUT
- RATE_LIMITED
- NO_URL_AVAILABLE

## 10. 异常层级
```python
Unit2IError(Exception)
  ├─ ConfigError
  ├─ ProviderError
  └─ OutputError
```

说明：
- ErrorInfo 是数据对象，不是异常类型。
- ProviderError 可携带 ErrorInfo 作为上下文。

## 11. metadata 标准字段

GenerateResult.metadata 至少包含：
- model_id
- size
- aspect_ratio
- seed
- num_images
- image_count_adjusted
- warnings
- latency_ms

## 12. 配置优先级
1. 方法参数（如 generate(timeout=...)）
2. 客户端构造参数（如 Unit2I(timeout=...)）
3. 环境变量
4. SDK 默认值

## 13. 测试策略（v0.1）

### 13.1 单元测试
- schema 默认值与类型校验
- 参数归一化（size、quality、output）
- 错误映射和重试分类

### 13.2 provider 适配器测试
- 使用 HTTP mock
- 验证请求映射
- 验证响应解析
- 验证错误映射

### 13.3 集成测试（可选）
- 由 UNIT2I_DASHSCOPE_API_KEY / UNIT2I_VOLC_API_KEY 控制是否执行
- 使用最小 prompt 验证链路
- 无密钥自动跳过

## 14. 首包工程清单
- 使用 pyproject.toml（setuptools 或 hatchling 二选一）
- src 布局：src/unit2i
- 最少工具：pytest、ruff
- 可选：mypy
- CI：GitHub Actions 跑 lint + test
- 发布：python -m build + twine upload

## 15. 发布前检查清单
- [ ] README 与对外 API 一致
- [ ] DashScope / Volcengine 双 provider 通过基础生成测试
- [ ] batch_generate 返回结构稳定（BatchItemResult）
- [ ] 错误码与重试测试通过
- [ ] 环境变量名与默认值确认
- [ ] 更新 changelog 与版本标签
