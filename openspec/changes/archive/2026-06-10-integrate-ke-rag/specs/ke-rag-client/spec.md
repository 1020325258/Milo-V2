## ADDED Requirements

### Requirement: KeRagClient HTTP 客户端

系统 SHALL 实现 `KeRagClient` 类，封装 ke-rag 服务的 HTTP API 调用。

配置项：
- `base_url: str` — 服务地址，默认 `https://openapi-ait.ke.com/v1`
- `api_key: str` — Bearer Token
- `timeout: int` — 请求超时时间（秒），默认 30

#### Scenario: 成功调用知识检索接口
- **WHEN** 调用 `search(query, space_id, mode, limit, user_id)`
- **THEN** 向 `POST /v1/rag/search` 发送请求，返回 `list[KnowledgeChunk]`

#### Scenario: 服务不可用时返回空结果
- **WHEN** ke-rag 服务返回非 0 code 或网络异常
- **THEN** 记录错误日志，返回空列表 `[]`，不抛出异常

### Requirement: search 请求参数映射

`KeRagClient.search()` 方法 SHALL 将参数映射为 ke-rag API 格式。

请求体：
```json
{
    "query": "<query>",
    "scope": [{"type": "space", "ids": ["<space_id>"]}],
    "limit": <limit>,
    "user": "<user_id>",
    "mode": "<mode>"
}
```

#### Scenario: 参数正确映射
- **WHEN** 调用 `search(query="测试", space_id="abc", mode="normal", limit=5, user_id="123")`
- **THEN** 请求体中 `scope` 为 `[{"type":"space","ids":["abc"]}]`，`user` 为 `"123"`

### Requirement: 响应解析

`KeRagClient` SHALL 正确解析 ke-rag API 响应，转换为 `KnowledgeChunk` 列表。

响应映射：
- `data.results[].content` → `KnowledgeChunk.content`
- `data.results[].file_name` → `KnowledgeChunk.file_name`
- `data.results[].paths` → `KnowledgeChunk.paths`
- `chunk_id` 生成规则：`{file_name}_{index}` 或使用服务端返回的 ID

#### Scenario: 解析成功响应
- **WHEN** 收到 `code=0` 的响应，`data.results` 包含 3 条结果
- **THEN** 返回长度为 3 的 `list[KnowledgeChunk]`

#### Scenario: 处理空结果
- **WHEN** 收到 `code=0` 的响应，`data.results` 为空数组
- **THEN** 返回空列表 `[]`

### Requirement: KeRagRetriever 适配器

系统 SHALL 实现 `KeRagRetriever` 类，实现 `KnowledgeRetriever` 接口，内部使用 `KeRagClient`。

#### Scenario: 通过抽象接口调用 ke-rag
- **WHEN** 调用 `KeRagRetriever.retrieve(query, config)`
- **THEN** 内部调用 `KeRagClient.search()`，返回 `list[KnowledgeChunk]`

#### Scenario: 检查 ke-rag 服务可用性
- **WHEN** 调用 `KeRagRetriever.is_available()`
- **THEN** 发送健康检查请求，返回服务是否可用
