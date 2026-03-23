# Unit2I 下一步开发指南（基于当前框架）

这份文档只说明你接下来该怎么写，不包含实现代码。

## 1. 当前框架状态

你现在已经有了可继续开发的基础骨架：

- 工程与打包：pyproject、src 布局、tests、CI
- 对外入口：Unit2I 客户端
- 领域模型：GenerateRequest、GenerateResult、ImageArtifact、BatchItemResult
- 异常体系：Unit2IError、ConfigError、ProviderError、OutputError、ErrorInfo
- Provider 架构：base + dashscope + volcengine + registry
- 通用能力：参数归一化、HTTP 重试、限流令牌桶

结论：框架够用了，可以开始“填真实能力”。

## 2. 你应该从哪里开始

先从 Provider 的真实请求与响应映射开始，不要先做高级功能。

推荐顺序：
1. 先打通 DashScope 的 generate
2. 再打通 Volcengine 的 generate
3. 然后统一错误码映射
4. 最后完善 batch_generate 的并发与失败语义

原因：
- 主链路先通，后续测试和文档才有真实基准
- 双 provider 都通后，统一抽象才有意义

## 3. 一步一步写（可直接照着做）

### 步骤 1：固定每个 provider 的“最小可用协议”

你要做的事：
- 为 DashScope 明确：
  - 请求 endpoint
  - 鉴权头
  - prompt、model、size、num_images、seed、quality 的字段位置
  - 返回里图片 URL/base64 的字段路径
- 为 Volcengine 做同样的表格

完成标准：
- 每个 provider 都有一张“请求字段映射 + 响应字段映射”表
- 能明确写出哪些字段是必填、哪些可选

建议放置位置：
- 先写在 plan 文档中，确认后再改代码

### 步骤 2：只实现 DashScope 的单条 generate 主路径

你要做的事：
- 按映射表把请求组装改为真实格式
- 只处理成功响应与最常见失败
- metadata 至少填：model_id、size、aspect_ratio、seed、num_images、warnings、latency_ms

完成标准：
- 传入最小 prompt 可以返回 GenerateResult
- output=auto/url/b64 三种模式行为正确
- output=url 但无 URL 时抛 NO_URL_AVAILABLE

### 步骤 3：实现 Volcengine 的单条 generate 主路径

你要做的事：
- 与步骤 2 同样方式，替换为 Volcengine 真实协议
- 不要引入 provider 特有参数到通用签名，仍然放 provider_options

完成标准：
- 同样的 Unit2I.generate 调用方式可跑通 Volcengine
- 返回结构与 DashScope 一致（GenerateResult）

### 步骤 4：统一错误码映射与重试语义

你要做的事：
- 按设计文档统一映射到这些 code：
  - INVALID_REQUEST
  - UNSUPPORTED_SIZE
  - UNSUPPORTED_ASPECT_RATIO
  - PROVIDER_ERROR
  - TIMEOUT
  - RATE_LIMITED
  - NO_URL_AVAILABLE
- 把 provider 原始错误保留在 ErrorInfo.raw
- retryable 只给网络超时、429、5xx

完成标准：
- 出错时都能返回稳定的 ErrorInfo
- 同类错误在两个 provider 上 code 一致

### 步骤 5：收敛参数归一化行为

你要做的事：
- size 预设与 tuple 统一到宽高
- aspect_ratio 合法性校验
- size 和 aspect_ratio 同时传时，按设计写 warning
- quality 不支持时降级 standard 并写 warning

完成标准：
- normalize 层单测覆盖关键分支
- provider 层不再重复写参数校验

### 步骤 6：完善 batch_generate 语义

你要做的事：
- 保证返回顺序与输入顺序一致
- fail_fast=True 时：
  - 第一条失败后停止后续任务投递
  - 未执行项返回可识别错误信息

完成标准：
- 成功、失败、部分失败三种情况可稳定复现
- BatchItemResult 结构始终稳定

### 步骤 7：补测试（先单测，再可选集成）

你要做的事：
- 单测：normalize、错误映射、output 行为、batch 顺序
- provider 适配测试：用 HTTP mock 验证请求与解析
- 集成测试：仅在环境变量存在时运行

完成标准：
- 无 key 时集成测试自动跳过
- 本地可稳定执行 lint + test

## 4. 每一步的自测命令（uv）

每完成一步都执行：
1. uv run ruff check .
2. uv run pytest

每完成一个大步骤再执行：
1. uv run pytest -k normalize
2. uv run pytest -k provider
3. uv run pytest -k batch

## 5. 建议提交节奏

建议一阶段一提交，避免一次改太多：

1. chore: freeze provider protocol mapping
2. feat: implement dashscope generate path
3. feat: implement volcengine generate path
4. feat: unify error mapping and retry semantics
5. feat: finalize parameter normalization rules
6. feat: stabilize batch generate behavior
7. test: add adapter and normalization coverage
8. docs: update README and examples to match behavior

## 6. 你现在就可以做的第一件事

先写“DashScope 与 Volcengine 的字段映射表”。

只要这个表清楚，后面的代码会非常顺。
这一步完成后，再开始改 provider 文件，成功率最高。