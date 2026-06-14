## Why

当前研发值班排查流程完全依赖人工：研发人员需要手动登录系统、查询数据库、分析日志，平均每个问题排查耗时 30-60 分钟。这种低效的响应模式不仅消耗大量研发时间，还导致问题响应延迟，影响用户体验。

通过引入 SRE 自动排查能力，可以让 AI Agent 自动执行排查流程，将响应时间从小时级降低到分钟级，同时释放研发人力专注于更有价值的工作。

## What Changes

- **新增 SRE 数据查询工具**：将现有的 `SreQueryController` 接口封装为 AgentScope Tool，让 AI Agent 能够查询生产环境数据（合同、节点、日志、配置等）
- **新增 SRE 排查技能（SKILL）**：定义标准化的排查流程，当用户提出问题时自动触发，引导 Agent 按步骤排查
- **支持源代码检索**：允许 Agent 在 workspace 中搜索源代码，辅助理解业务逻辑
- **支持敏感信息解密**：提供 decrypt 接口，用于解密身份证号、手机号等敏感数据

## Capabilities

### New Capabilities

- `sre-query-tool`: SRE 数据查询工具，封装 12 个查询接口（contract、contract_node、contract_user、contract_field、contract_quotation、config_snap、city_company_info、contract_log、field_config、protocol_config、dim_combos、decrypt），提供统一的查询入口
- `sre-troubleshoot-skill`: SRE 排查技能，定义标准化排查流程，支持自动触发，引导 Agent 按步骤收集数据并分析问题

### Modified Capabilities

（无需修改现有能力）

## Impact

### 受影响的代码

- **新增**：`backend/sre/` 模块（tools.py、client.py）
- **新增**：`backend/global_skills/sre-troubleshoot/SKILL.md`
- **修改**：`backend/main.py`（注册 SreQueryTool）

### 依赖的外部服务

- SRE 查询接口：`http://preview.i.nrs-sales-project.home.ke.com/sre/*`

### 依赖的现有模块

- AgentScope Tool 机制（ToolBase）
- 全局 Skill 机制（global_skills/）
- Redis（用于 AgentScope 会话管理）

### 前端影响

无直接前端改动，通过现有对话界面使用
