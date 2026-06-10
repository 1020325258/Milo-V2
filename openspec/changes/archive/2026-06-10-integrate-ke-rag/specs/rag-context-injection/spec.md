## ADDED Requirements

### Requirement: RAG 检索 Tool 注册

系统 SHALL 将知识库检索能力注册为 AgentScope 的 Tool，供 Agent 在对话中调用。

Tool 定义：
- 名称：`knowledge_search`
- 参数：`query: str`（检索关键词）
- 返回：格式化的知识检索结果文本

#### Scenario: Agent 调用知识检索工具
- **WHEN** Agent 决定调用 `knowledge_search` 工具，参数为 `{"query": "退款流程"}`
- **THEN** 系统执行知识库检索，返回格式化的检索结果

#### Scenario: 检索无结果
- **WHEN** 知识库检索返回空结果
- **THEN** 返回提示文本："未找到相关知识，请尝试其他关键词或直接回答。"

### Requirement: 检索结果格式化

系统 SHALL 将检索结果格式化为 Markdown 文本，便于 LLM 理解和引用。

格式：
```
找到 N 条相关知识：

1. **标题** | 来源：文件名
   内容摘要...

2. **标题** | 来源：文件名
   内容摘要...
```

#### Scenario: 格式化多条结果
- **WHEN** 检索到 3 条结果
- **THEN** 输出包含 "找到 3 条相关知识：" 标题，每条结果以编号列表展示

#### Scenario: 内容过长截断
- **WHEN** 单条结果内容超过 500 字符
- **THEN** 截断至 500 字符并添加 "..." 后缀

### Requirement: RAG 上下文注入 System Prompt

系统 SHALL 在 Agent 的 system prompt 中注入知识检索结果作为上下文。

注入方式：
- 在 system prompt 末尾添加 `{{ragContext}}` 占位符
- 检索完成后，将格式化结果替换到占位符位置

#### Scenario: system prompt 包含 RAG 上下文
- **WHEN** 用户发送消息，Agent 配置启用了 RAG
- **THEN** Agent 的 system prompt 中包含检索到的知识内容

#### Scenario: 未启用 RAG 时不影响
- **WHEN** Agent 配置未启用 RAG
- **THEN** system prompt 中不包含 `{{ragContext}}` 占位符内容

### Requirement: RAG 配置选项

系统 SHALL 支持在 Agent 配置中启用/禁用 RAG 并设置参数。

配置项：
- `rag_enabled: bool` — 是否启用 RAG，默认 `false`
- `rag_space_id: str` — 知识库空间 ID
- `rag_mode: str` — 检索模式，默认 `"normal"`
- `rag_limit: int` — 返回结果数量，默认 5

#### Scenario: Agent 启用 RAG
- **WHEN** Agent 配置中 `rag_enabled=true`，`rag_space_id="abc"`
- **THEN** 对话时自动调用知识检索

#### Scenario: Agent 未启用 RAG
- **WHEN** Agent 配置中 `rag_enabled=false`（默认）
- **THEN** 对话时不调用知识检索，行为与当前一致
