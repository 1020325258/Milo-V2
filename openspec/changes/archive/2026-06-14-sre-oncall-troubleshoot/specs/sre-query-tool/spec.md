## ADDED Requirements

### Requirement: Tool 基本信息

SreQueryTool SHALL 继承 `agentscope.tool.ToolBase`，并定义以下属性：
- `name`: `"sre_query"`
- `description`: 描述工具功能和适用场景
- `input_schema`: JSON Schema 格式的参数定义
- `is_concurrency_safe`: `True`（只读操作）
- `is_read_only`: `True`

#### Scenario: Tool 注册
- **WHEN** 系统启动时调用 `_create_agent_tools`
- **THEN** 返回的工具列表中包含 `SreQueryTool` 实例

### Requirement: 支持的查询操作

SreQueryTool SHALL 支持以下 12 种 action：

| action | 说明 | 必需参数 |
|--------|------|---------|
| `decrypt` | 解密敏感信息 | `encrypted_text` |
| `contract` | 查询合同信息 | `contract_code` 或 `project_order_id` |
| `contract_node` | 查询合同节点 | `contract_code` |
| `contract_user` | 查询签约人 | `contract_code` |
| `contract_field` | 查询合同扩展字段 | `contract_code` |
| `contract_quotation` | 查询签约单据 | `contract_code` |
| `config_snap` | 查询配置快照 | `project_order_id` |
| `city_company_info` | 查询城市公司配置 | `business_type`, `gb_code`, `company_code`, `version`, `contract_type` |
| `contract_log` | 查询合同操作日志 | `contract_code`（可选：`log_type`） |
| `field_config` | 查询字段配置 | 无必需参数（均可选） |
| `protocol_config` | 查询协议配置 | `form_id` |
| `dim_combos` | 查询维度组合 | 无必需参数（均可选） |

#### Scenario: 查询合同信息
- **WHEN** 调用 `sre_query(action="contract", contract_code="C001")`
- **THEN** 返回合同 C001 的详细信息

#### Scenario: 查询合同节点
- **WHEN** 调用 `sre_query(action="contract_node", contract_code="C001")`
- **THEN** 返回合同 C001 的所有节点列表

#### Scenario: 解密敏感信息
- **WHEN** 调用 `sre_query(action="decrypt", encrypted_text="xxx")`
- **THEN** 返回解密后的明文

### Requirement: 参数验证

SreQueryTool SHALL 在调用前验证参数：
- `action` 为必需参数
- 根据不同 action 验证对应的必需参数
- 参数验证失败时返回友好的错误消息

#### Scenario: 缺少必需参数
- **WHEN** 调用 `sre_query(action="contract")` 但未提供 `contract_code` 或 `project_order_id`
- **THEN** 返回错误消息："contract 操作需要 contract_code 或 project_order_id 参数"

#### Scenario: 未知的 action
- **WHEN** 调用 `sre_query(action="unknown_action")`
- **THEN** 返回错误消息："未知的操作类型: unknown_action"

### Requirement: HTTP 客户端

SreQueryTool SHALL 使用 `httpx.AsyncClient` 调用远程接口：
- Base URL: `http://preview.i.nrs-sales-project.home.ke.com`
- 认证参数: `app=sreAgent`
- 超时时间: 30 秒
- HTTP 方法: GET

#### Scenario: 正常调用远程接口
- **WHEN** 调用 `sre_query(action="contract", contract_code="C001")`
- **THEN** 发送 GET 请求到 `http://preview.i.nrs-sales-project.home.ke.com/sre/contract?contractCode=C001&app=sreAgent`

#### Scenario: 远程接口超时
- **WHEN** 远程接口响应超过 30 秒
- **THEN** 返回错误消息："查询超时，请稍后重试"

### Requirement: 返回数据格式化

SreQueryTool SHALL 将返回数据格式化为 Markdown：
- 成功时：返回格式化的 Markdown 表格或列表
- 查询为空时：返回 "查询结果为空" 提示
- 失败时：返回友好的错误消息

#### Scenario: 格式化单条记录
- **WHEN** 查询返回单个对象（如 contract）
- **THEN** 返回 Markdown 表格，包含字段名和值

#### Scenario: 格式化多条记录
- **WHEN** 查询返回数组（如 contract_node 列表）
- **THEN** 返回 Markdown 表格，每行一条记录

#### Scenario: 查询结果为空
- **WHEN** 接口返回 `data: null`
- **THEN** 返回消息："ℹ️ 查询结果为空"

#### Scenario: 接口调用失败
- **WHEN** 接口返回 `success: false`
- **THEN** 返回错误消息："❌ {message}"

### Requirement: 权限检查

SreQueryTool SHALL 实现 `check_permissions` 方法：
- 始终返回 `PermissionDecision(behavior=PermissionBehavior.ALLOW)`
- 因为是只读查询操作，不需要特殊权限

#### Scenario: 权限检查
- **WHEN** Agent 调用 SreQueryTool
- **THEN** 权限检查通过，允许执行
