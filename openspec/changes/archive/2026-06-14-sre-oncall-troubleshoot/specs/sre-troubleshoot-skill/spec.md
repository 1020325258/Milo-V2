## ADDED Requirements

### Requirement: SKILL 文件结构

sre-troubleshoot SKILL SHALL 位于 `backend/global_skills/sre-troubleshoot/SKILL.md`，包含：
- frontmatter：`name`、`description` 字段
- 正文：排查流程说明

#### Scenario: SKILL 文件存在
- **WHEN** 系统启动时扫描 `global_skills/` 目录
- **THEN** 找到 `sre-troubleshoot/SKILL.md` 并加载

#### Scenario: 新 workspace 继承 SKILL
- **WHEN** 用户创建新 workspace
- **THEN** workspace 自动继承 `sre-troubleshoot` SKILL

### Requirement: 自动触发机制

SKILL SHALL 支持基于关键词自动触发，当用户问题包含以下关键词时自动加载：
- "合同"、"签约"、"工单"
- "排查"、"问题"、"故障"
- "状态异常"、"失败"、"报错"
- contract_code 格式（如 "C" + 数字）
- project_order_id 格式

#### Scenario: 包含关键词触发
- **WHEN** 用户输入 "合同 C001 签约失败，请排查"
- **THEN** 系统自动加载 `sre-troubleshoot` SKILL

#### Scenario: 不包含关键词不触发
- **WHEN** 用户输入 "今天天气怎么样"
- **THEN** 系统不加载 `sre-troubleshoot` SKILL

### Requirement: 排查流程 - 第一步：提取关键信息

SKILL SHALL 指导 Agent 从用户问题中提取：
- **合同编号**（contract_code）
- **订单号**（project_order_id）
- **问题描述**（现象、时间、影响范围）

如果信息不完整，Agent SHALL 主动询问用户补充。

#### Scenario: 信息完整
- **WHEN** 用户输入 "合同 C001 签约失败"
- **THEN** Agent 提取 contract_code="C001"，继续排查

#### Scenario: 信息不完整
- **WHEN** 用户输入 "签约失败了"
- **THEN** Agent 回复 "请提供合同编号或订单号，以便我查询详情"

### Requirement: 排查流程 - 第二步：查询合同基本信息

SKILL SHALL 指导 Agent 使用 `sre_query` 工具查询合同：
```
action=contract, contract_code={contract_code}
```
或
```
action=contract, project_order_id={project_order_id}
```

#### Scenario: 查询成功
- **WHEN** 调用 `sre_query(action="contract", contract_code="C001")`
- **THEN** Agent 获得合同状态、创建时间等基本信息

#### Scenario: 合同不存在
- **WHEN** 查询返回空结果
- **THEN** Agent 提示 "未找到该合同，请确认合同编号是否正确"

### Requirement: 排查流程 - 第三步：查询合同节点

SKILL SHALL 指导 Agent 查询合同节点，了解流程状态：
```
action=contract_node, contract_code={contract_code}
```

#### Scenario: 查询节点成功
- **WHEN** 调用 `sre_query(action="contract_node", contract_code="C001")`
- **THEN** Agent 获得节点列表，识别当前卡在哪个节点

### Requirement: 排查流程 - 第四步：查询操作日志

SKILL SHALL 指导 Agent 查询操作日志，找出异常操作：
```
action=contract_log, contract_code={contract_code}
```

#### Scenario: 查询日志成功
- **WHEN** 调用 `sre_query(action="contract_log", contract_code="C001")`
- **THEN** Agent 获得操作日志列表，按时间倒序排列

#### Scenario: 指定日志类型
- **WHEN** 调用 `sre_query(action="contract_log", contract_code="C001", log_type=1)`
- **THEN** Agent 获得类型为 1 的操作日志

### Requirement: 排查流程 - 第五步：查询配置信息

SKILL SHALL 指导 Agent 根据需要查询配置信息：
```
action=config_snap, project_order_id={project_order_id}
action=field_config, ...
action=protocol_config, form_id={form_id}
```

#### Scenario: 查询配置快照
- **WHEN** 调用 `sre_query(action="config_snap", project_order_id="P001")`
- **THEN** Agent 获得该订单的配置快照

### Requirement: 排查流程 - 第六步：解密敏感信息

SKILL SHALL 指导 Agent 在需要时解密敏感信息（身份证号、手机号）：
```
action=decrypt, encrypted_text={encrypted_text}
```

#### Scenario: 解密身份证号
- **WHEN** 查询结果包含加密的身份证号
- **THEN** Agent 调用 `sre_query(action="decrypt", encrypted_text="xxx")` 获取明文

### Requirement: 排查流程 - 第七步：综合分析

SKILL SHALL 指导 Agent 综合分析所有收集到的数据，输出排查结论：

```markdown
## 排查结论

### 问题描述
[用户反馈的问题]

### 排查过程
1. [查询了什么数据]
2. [发现了什么]

### 根因分析
[问题的根本原因]

### 解决建议
[如何解决这个问题]
```

#### Scenario: 正常输出结论
- **WHEN** Agent 完成所有查询
- **THEN** Agent 输出格式化的排查结论

#### Scenario: 无法确定根因
- **WHEN** 数据不足以确定根因
- **THEN** Agent 说明已收集的信息，建议进一步排查方向

### Requirement: 源代码检索

SKILL SHALL 指导 Agent 在需要时使用 Bash 工具检索源代码：
- 使用 `grep`、`find` 等命令搜索代码
- 帮助理解业务逻辑、字段含义

#### Scenario: 搜索相关代码
- **WHEN** Agent 需要理解某个字段的含义
- **THEN** Agent 使用 `grep` 在 workspace 中搜索相关代码

### Requirement: 注意事项

SKILL SHALL 包含以下注意事项：
- 查询前确保有有效的 contract_code 或 project_order_id
- 如果查询返回空结果，检查参数是否正确
- 操作日志按时间倒序排列，关注最近的记录
- 注意数据安全，敏感信息需解密后才能查看

#### Scenario: 提醒数据安全
- **WHEN** Agent 准备解密敏感信息
- **THEN** Agent 说明这是敏感数据，仅用于排查目的
