## Why

Milo-V2 当前的 Agent 对话完全依赖 LLM 自身知识，无法检索和引用企业内部知识库内容。接入 ke-rag 知识库能力后，Agent 能够基于企业文档进行精准问答，并在回答中标注引用来源，提升回答可信度和可追溯性。

参考 nrs-agent 的实现，知识库检索和引用是企业级 Agent 的核心能力，需要优先落地。

## What Changes

- **新增知识库检索抽象层**：定义统一的 `KnowledgeRetriever` 接口，支持多后端实现（ke-rag、本地 ES 等），保证可扩展性
- **新增 ke-rag 客户端**：实现 ke-rag HTTP API 封装，支持 `search` 和 `chat` 两种检索模式
- **新增 RAG 中间件**：在 Agent 对话流程中注入检索逻辑，用户输入后先检索知识库，将结果作为上下文注入 system prompt
- **新增引用格式规范**：定义 LLM 输出中引用知识库内容的 Markdown 格式规范
- **新增前端引用渲染**：在聊天消息中渲染知识引用卡片，支持点击查看详情
- **新增知识库配置**：支持配置知识库空间、检索模式、返回条数等参数

## Capabilities

### New Capabilities
- `knowledge-retrieval`: 知识库检索抽象层，定义统一接口和数据模型，支持多后端实现
- `ke-rag-client`: ke-rag HTTP API 客户端封装，实现文件上传、进度查询、知识检索、RAG 问答
- `rag-context-injection`: RAG 上下文注入中间件，在 Agent 对话前检索知识库，格式化后注入 system prompt
- `knowledge-citation`: 知识引用格式规范和前端渲染组件，支持引用来源展示和详情查看

### Modified Capabilities
- (无现有 capability 需要修改)

## Impact

- **后端**：新增 `backend/rag/` 模块，包含抽象层、客户端、中间件
- **前端**：新增知识引用渲染组件，修改消息渲染逻辑
- **依赖**：新增 `httpx` 用于 HTTP 请求（后端）
- **配置**：新增 ke-rag 相关环境变量（API Key、Space ID、检索模式等）
- **Agent 流程**：对话流程中增加知识检索步骤，可能增加响应延迟（< 2s）
