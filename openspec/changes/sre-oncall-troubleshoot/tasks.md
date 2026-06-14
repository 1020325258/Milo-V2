## 1. SRE 模块基础结构

- [x] 1.1 创建 `backend/sre/` 目录结构（`__init__.py`、`tools.py`、`client.py`）
- [x] 1.2 创建 `SreQueryClient` 类，实现 HTTP 客户端
- [x] 1.3 创建 `SreQueryTool` 类，继承 `ToolBase`

## 2. SreQueryClient 实现

- [x] 2.1 实现 `__init__` 方法，配置 base_url、app 参数、超时时间
- [x] 2.2 实现 `query` 方法，统一处理 GET 请求
- [x] 2.3 实现 `_get_endpoint` 方法，映射 action 到 API endpoint
- [x] 2.4 实现 `close` 方法，关闭 HTTP 客户端

## 3. SreQueryTool 实现

- [x] 3.1 定义 `name`、`description`、`input_schema` 属性
- [x] 3.2 实现 `check_permissions` 方法（始终允许）
- [x] 3.3 实现 `__call` 方法，统一处理查询逻辑
- [x] 3.4 实现参数验证逻辑（根据 action 验证必需参数）
- [x] 3.5 实现返回数据格式化（单条记录、多条记录、空结果、错误）

## 4. 支持的查询操作

- [x] 4.1 实现 `decrypt` action（解密敏感信息）
- [x] 4.2 实现 `contract` action（查询合同信息）
- [x] 4.3 实现 `contract_node` action（查询合同节点）
- [x] 4.4 实现 `contract_user` action（查询签约人）
- [x] 4.5 实现 `contract_field` action（查询合同扩展字段）
- [x] 4.6 实现 `contract_quotation` action（查询签约单据）
- [x] 4.7 实现 `config_snap` action（查询配置快照）
- [x] 4.8 实现 `city_company_info` action（查询城市公司配置）
- [x] 4.9 实现 `contract_log` action（查询合同操作日志）
- [x] 4.10 实现 `field_config` action（查询字段配置）
- [x] 4.11 实现 `protocol_config` action（查询协议配置）
- [x] 4.12 实现 `dim_combos` action（查询维度组合）

## 5. 注册到 main.py

- [x] 5.1 导入 `SreQueryClient` 和 `SreQueryTool`
- [x] 5.2 初始化 `SreQueryClient` 实例
- [x] 5.3 在 `_create_agent_tools` 函数中添加 `SreQueryTool`
- [x] 5.4 添加环境变量配置（SRE_BASE_URL、SRE_APP）

## 6. 创建排查 SKILL

- [x] 6.1 创建 `backend/global_skills/sre-troubleshoot/SKILL.md` 文件
- [x] 6.2 编写 frontmatter（name、description）
- [x] 6.3 编写排查流程 - 第一步：提取关键信息
- [x] 6.4 编写排查流程 - 第二步：查询合同基本信息
- [x] 6.5 编写排查流程 - 第三步：查询合同节点
- [x] 6.6 编写排查流程 - 第四步：查询操作日志
- [x] 6.7 编写排查流程 - 第五步：查询配置信息
- [x] 6.8 编写排查流程 - 第六步：解密敏感信息
- [x] 6.9 编写排查流程 - 第七步：综合分析输出结论
- [x] 6.10 编写注意事项和输出格式模板

## 7. 测试验证

- [x] 7.1 编写 `SreQueryClient` 单元测试
- [x] 7.2 编写 `SreQueryTool` 单元测试
- [x] 7.3 测试 Tool 注册是否成功
- [x] 7.4 测试 SKILL 是否自动加载
- [ ] 7.5 端到端测试：输入工单问题，验证排查流程
