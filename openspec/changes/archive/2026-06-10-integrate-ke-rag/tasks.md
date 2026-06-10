## 1. 后端：知识库抽象层

- [x] 1.1 创建 `backend/rag/` 模块，定义 `KnowledgeRetriever` 抽象接口（`retriever.py`）
- [x] 1.2 定义 `RetrievalConfig` 和 `KnowledgeChunk` 数据模型（`models.py`）
- [x] 1.3 实现后端注册机制 `register_retriever` / `get_retriever`（`registry.py`）

## 2. 后端：ke-rag 客户端

- [x] 2.1 实现 `KeRagClient` HTTP 客户端，封装 `/v1/rag/search` 接口调用（`client.py`）
- [x] 2.2 实现 `KeRagRetriever` 适配器，实现 `KnowledgeRetriever` 接口（`ke_rag_retriever.py`）
- [x] 2.3 添加 `httpx` 依赖到 `requirements.txt`
- [x] 2.4 添加 ke-rag 相关环境变量配置（`KE_RAG_BASE_URL`、`KE_RAG_API_KEY`）

## 3. 后端：RAG Tool 注册

- [x] 3.1 实现 `knowledge_search` Tool，封装检索调用和结果格式化（`tools.py`）
- [x] 3.2 实现检索结果 Markdown 格式化逻辑（标题截断、编号列表）
- [x] 3.3 在 Agent 创建时注册 `knowledge_search` Tool
- [x] 3.4 实现 RAG 配置选项（`rag_enabled`、`rag_space_id`、`rag_mode`、`rag_limit`）

## 4. 后端：System Prompt 注入

- [x] 4.1 在 Agent system prompt 中添加 RAG 引用格式规范
- [x] 4.2 实现 system prompt 模板，支持 `{{ragContext}}` 占位符替换
- [x] 4.3 添加引用格式的正向约束（必须引用来源）和负向约束（禁止编造引用）

## 5. 前端：引用渲染组件

- [x] 5.1 实现 `CitationModal` 引用详情弹窗组件
- [x] 5.2 实现 `CitationRenderer` 内联引用渲染组件（可点击蓝色标记）
- [x] 5.3 在 `MessageBubble` 中集成引用渲染逻辑
- [x] 5.4 实现引用解析函数，从 Markdown 中提取引用标记和来源列表

## 6. 前端：检索状态展示

- [x] 6.1 在聊天界面添加知识库检索状态提示组件
- [x] 6.2 处理 SSE 事件中的知识检索相关状态（检索中/完成/失败）
- [x] 6.3 实现 "正在检索知识库..." 和 "已检索到 N 条相关知识" 的 UI 展示

## 7. 测试

- [x] 7.1 编写 `KnowledgeRetriever` 抽象接口的单元测试
- [x] 7.2 编写 `KeRagClient` 的单元测试（Mock HTTP 响应）
- [x] 7.3 编写 `knowledge_search` Tool 的单元测试
- [x] 7.4 编写引用解析函数的单元测试
- [x] 7.5 编写 `CitationRenderer` 组件的单元测试

## 8. 集成验证

- [x] 8.1 端到端测试：用户提问 → 知识检索 → LLM 回答 → 前端渲染引用
- [x] 8.2 验证无检索结果时的降级行为
- [x] 8.3 验证 ke-rag 服务不可用时的错误处理
