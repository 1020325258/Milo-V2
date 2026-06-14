## Context

milo-v2 是基于 AgentScope 的 AI Agent 对话平台，已具备：
- **Tool 机制**：通过 `ToolBase` 定义工具，`_create_agent_tools` 注册到所有 agent
- **SKILL 机制**：通过 `global_skills/` 目录定义全局技能，所有 workspace 自动继承
- **现有工具示例**：`KnowledgeSearchTool`、`ApolloQueryTool`

当前值班排查流程完全依赖人工，需要登录系统、查询数据库、分析日志，耗时 30-60 分钟/问题。

**约束条件**：
- SRE 查询接口已部署：`http://preview.i.nrs-sales-project.home.ke.com/sre/*`
- 认证方式：仅需 `app=sreAgent` 参数
- 源代码位于 workspace 目录，可通过 Bash 工具检索

## Goals / Non-Goals

**Goals:**
- 将 SRE 查询接口封装为 AgentScope Tool，让 AI Agent 能够查询生产环境数据
- 定义标准化的排查 SKILL，引导 Agent 按步骤排查问题
- 支持敏感信息解密（身份证号、手机号）
- 支持源代码检索辅助排查

**Non-Goals:**
- 不实现自动修复能力（仅排查，不修复）
- 不修改现有 SreQueryController 接口
- 不实现跨服务链路追踪
- 不实现历史问题知识库（MVP 阶段）

## Decisions

### Decision 1: 单一 Tool vs 多个 Tool

**选择**：单一 Tool（`SreQueryTool`）+ action 参数区分

**理由**：
- 所有接口都在同一个 Controller，业务域相同
- 减少工具数量，降低 AI 选择困难
- 参数可复用（如 `contract_code` 在多个查询中使用）
- 参考现有 `ApolloQueryTool` 的设计模式

**备选方案**：
- 多个独立 Tool：每个接口一个 Tool，更灵活但增加复杂度

### Decision 2: Tool 参数设计

**选择**：使用扁平参数结构，所有可能的参数都定义在 `input_schema` 中

**理由**：
- AgentScope 的 Tool 机制要求参数在 schema 中预先定义
- 扁平结构比嵌套对象更易于 AI 理解和填写
- 通过 `required` 字段区分不同 action 的必填参数

**参数映射**：
```python
{
    "action": "contract",           # 必填
    "contract_code": "C001",        # contract 时必填
    "project_order_id": "",         # 或者用这个
    "encrypted_text": "",           # decrypt 时必填
    # ... 其他参数均为可选
}
```

### Decision 3: SKILL 触发机制

**选择**：基于关键词自动触发

**理由**：
- SKILL.md 中定义触发条件（关键词匹配）
- 当用户问题包含"合同"、"签约"、"排查"等关键词时自动加载
- 无需用户手动指定，降低使用门槛

**实现方式**：
- 在 SKILL.md 的 frontmatter 中定义 `triggers` 字段
- AgentScope 在处理用户消息时匹配触发条件

### Decision 4: 返回数据格式化

**选择**：在 Tool 内部格式化为 Markdown 表格

**理由**：
- Markdown 格式易于 AI 理解
- 表格结构清晰展示数据
- 参考 `ApolloQueryTool` 的格式化方式

**格式示例**：
```markdown
## 合同信息

| 字段 | 值 |
|------|-----|
| 合同编号 | C001 |
| 状态 | 已签约 |
| 创建时间 | 2024-01-01 |
```

### Decision 5: 错误处理策略

**选择**：统一错误格式 + 友好错误消息

**理由**：
- 接口返回 `{code, message, data, success}` 格式
- 非 `success` 时返回友好的错误提示，帮助 AI 理解问题
- 区分"查询为空"和"查询失败"两种情况

**实现**：
```python
if not response.get("success"):
    return self._error_response(response.get("message", "查询失败"))

data = response.get("data")
if data is None:
    return self._info_response("查询结果为空")
```

## Risks / Trade-offs

### Risk 1: 接口响应慢导致 Agent 超时
**影响**：查询接口可能因数据库慢查询导致响应慢
**缓解**：
- 设置合理的 HTTP 超时时间（30s）
- 在 Tool 描述中提示用户可能需要等待
- 考虑添加重试机制（MVP 阶段暂不实现）

### Risk 2: AI 误用 Tool 导致无效查询
**影响**：AI 可能传错参数，导致查询失败或返回无关数据
**缓解**：
- 在 SKILL 中明确参数说明和示例
- 在 Tool description 中详细描述每个 action 的参数要求
- 返回友好错误消息，引导 AI 重试

### Risk 3: 敏感数据泄露
**影响**：查询结果可能包含敏感信息（手机号、身份证号）
**缓解**：
- 默认返回加密数据
- 仅在明确需要时调用 decrypt 接口
- 在 SKILL 中提醒 Agent 注意数据安全

### Trade-off: 单一 Tool vs 多个 Tool
**单一 Tool**：更简单，但 action 参数可能较长
**多个 Tool**：更灵活，但增加 AI 选择难度
**决策**：选择单一 Tool，因为业务域统一，且参考现有 ApolloQueryTool 的成功经验
