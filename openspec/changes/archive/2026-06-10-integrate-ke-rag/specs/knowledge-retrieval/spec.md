## ADDED Requirements

### Requirement: KnowledgeRetriever 抽象接口

系统 SHALL 定义统一的 `KnowledgeRetriever` 抽象接口，所有知识库后端实现 MUST 遵循此接口。

接口定义：
- `retrieve(query: str, config: RetrievalConfig) -> list[KnowledgeChunk]`
- `is_available() -> bool`

#### Scenario: 通过抽象接口调用检索
- **WHEN** 调用方使用 `KnowledgeRetriever.retrieve(query, config)`
- **THEN** 返回 `list[KnowledgeChunk]`，包含检索到的知识片段列表

#### Scenario: 检查后端可用性
- **WHEN** 调用 `is_available()`
- **THEN** 返回布尔值，指示后端服务是否可用

### Requirement: RetrievalConfig 配置模型

系统 SHALL 定义 `RetrievalConfig` 数据模型，用于配置检索行为。

字段：
- `space_id: str` — 知识库空间 ID
- `mode: Literal["fast", "normal", "ultra"]` — 检索模式，默认 `"normal"`
- `limit: int` — 返回结果数量，默认 5
- `user_id: str` — 用户 ID（影响城市过滤）

#### Scenario: 使用默认配置检索
- **WHEN** 调用方仅提供 `space_id`，其他字段使用默认值
- **THEN** 系统使用 `mode="normal"`、`limit=5` 进行检索

### Requirement: KnowledgeChunk 数据模型

系统 SHALL 定义 `KnowledgeChunk` 数据模型，统一表示检索结果。

字段：
- `content: str` — 知识片段内容
- `file_name: str` — 来源文件名
- `title: str` — 知识标题
- `paths: list[str]` — 引用信息逻辑位置
- `chunk_id: str` — 唯一标识（用于引用链接）
- `metadata: dict` — 扩展元数据

#### Scenario: 检索结果包含完整字段
- **WHEN** 从知识库检索到一条结果
- **THEN** 返回的 `KnowledgeChunk` 包含 `content`、`file_name`、`title`、`paths`、`chunk_id` 字段

### Requirement: 知识库后端注册机制

系统 SHALL 提供后端注册机制，支持运行时切换知识库实现。

#### Scenario: 注册新的知识库后端
- **WHEN** 调用 `register_retriever(name, retriever_instance)`
- **THEN** 系统记录该后端，可通过 `get_retriever(name)` 获取

#### Scenario: 获取默认后端
- **WHEN** 调用 `get_retriever()` 不传参数
- **THEN** 返回注册的默认后端实例
