# Unit2I 可用方法与示例（EXAMPLES）

这个文件聚焦一件事：当 `unit2i` 包实现完成后，你可以直接调用哪些方法。

本文示例对齐 v0.1：仅支持 `dashscope` 与 `volcengine`，优先同步接口。

## 1. 你最常用的对象

### 1.1 Unit2I 客户端
```python
from unit2i import Unit2I

client = Unit2I(provider="dashscope")
```

也可以切换 provider：
```python
client = Unit2I(provider="volcengine")
```

## 2. 客户端可用方法

### 2.1 generate()
用途：同步生成图片，最常用。

```python
result = client.generate(
	prompt="a red fox in snow",
	model="wanx2.1-t2i-plus",
	aspect_ratio="1:1",
	num_images=1,
	quality="standard",
	output="auto",
)
```

常见可选参数：
- `model`
- `size`
- `aspect_ratio`
- `seed`
- `num_images`
- `quality`
- `output`
- `provider_options`

参数说明（新加）：
- `model`：指定本次请求的模型名称。
- `aspect_ratio`：指定图片比例，如 `1:1`、`16:9`、`9:16`。
- 同时传 `size` 和 `aspect_ratio` 时，以 `size` 为准。

### 2.2 batch_generate()
用途：一次提交多条生成请求。

```python
batch = client.batch_generate(
	[
		{"prompt": "golden retriever", "size": "square"},
		{"prompt": "snowy mountain", "size": "landscape"},
	],
	concurrency=4,
)

for item in batch:
	if item.success:
		print("ok", len(item.result.images))
	else:
		print("failed", item.error.code, item.error.message)
```

## 3. v0.1 输出模式
- `auto`：优先 URL，没有则 base64
- `url`：只接受 URL
- `b64`：只接受 base64

## 4. 结果对象怎么取值

### 4.1 GenerateResult
- `result.images`：图片列表
- `result.metadata`：生成参数和警告等
- `result.provider`：供应商
- `result.request_id`：请求 ID（可能为空）

### 4.2 ImageArtifact
- `url`
- `b64`
- `mime_type`
- `width`
- `height`

示例：
```python
img = result.images[0]
print(img.url or "(only b64 returned)")
```

## 5. 最小可运行示例（新手推荐）

```python
from unit2i import Unit2I

client = Unit2I(provider="dashscope")

result = client.generate(
    prompt="a cute corgi in a coffee shop",
	model="wanx2.1-t2i-plus",
	aspect_ratio="4:3",
    output="auto",
)

for i, img in enumerate(result.images, 1):
    print(i, img.url or "(only b64 returned)")
```

## 6. 新手避坑
- `prompt` 必填，不能为空。
- 建议优先用 `aspect_ratio` 控制构图，用 `size` 做精确像素控制。
- 同时传 `size` 和 `aspect_ratio` 会以 `size` 为准。
- v0.1 先用 `output="auto"` 或 `output="url"`，调试最方便。
- 批量接口 `batch_generate()` 返回统一结果对象，按 `item.success` 判断。
- provider 特有参数放到 `provider_options`，避免污染通用参数。

## 7. 文档关系
- [README.md](README.md)：快速上手。
- [DESIGN.md](DESIGN.md)：完整 API 设计与行为细节。

## 8. 当前 provider（v0.1）
- `dashscope`
- `volcengine`

## 9. 后续版本（v0.2）
- 计划增加 `generate_async()` 和 `JobHandle`
- 计划增加 `output="path"` 和 `output="pil"`
