---
name: contract-data-dictionary
description: 合同域数据字典 - 解读 sre_query 工具返回数据中各字段和枚举值的含义
---

# 合同域数据字典

当 `sre_query` 工具返回数据时，使用本字典解读字段含义和枚举值。

---

## 字段含义

`sre_query` 工具返回数据中的字段含义已内置在工具的 `_FIELD_MEANINGS` 映射中，会自动在返回结果中显示字段含义列。

---

## 枚举参考

`sre_query` 返回数据中的枚举字段（如 type、status、roleType 等）的含义，请参考以下枚举定义：

| 枚举类型 | 用途 | 参考文件 |
|----------|------|----------|
| [ContractTypeEnum](references/ContractTypeEnum.md) | 合同类型 | contract.type |
| [ContractStatusEnum](references/ContractStatusEnum.md) | 合同状态 | contract.status |
| [BusinessTypeEnum](references/BusinessTypeEnum.md) | 业务类型 | contract.businessType |
| [RoleTypeEnum](references/RoleTypeEnum.md) | 用户角色 | contract_user.roleType |
| [NodeTypeEnum](references/NodeTypeEnum.md) | 节点类型 | contract_node.nodeType |
| [LogTypeEnum](references/LogTypeEnum.md) | 日志类型 | contract_log.type |
| [SignChannelTypeEnum](references/SignChannelTypeEnum.md) | 签署方式 | contract.signChannelType |
| [UserSignTypeEnum](references/UserSignTypeEnum.md) | 用户签署方式 | contract.userSignType |
| [AuditTypeEnum](references/AuditTypeEnum.md) | 审核类型 | contract.auditType |
| [PdfGenerationModeEnum](references/PdfGenerationModeEnum.md) | PDF生成模式 | contract.pdfGenerationMode |
| [SealStatusEnum](references/SealStatusEnum.md) | 盖章状态 | - |
| [SelfSealStatusEnum](references/SelfSealStatusEnum.md) | 自动盖章状态 | - |
| [CertificateTypeEnum](references/CertificateTypeEnum.md) | 证件类型 | contract_user.certificateType |
| [ContractObjectTypeEnum](references/ContractObjectTypeEnum.md) | 主体类型 | - |
| [ContractAuditStatusEnum](references/ContractAuditStatusEnum.md) | 审核状态 | - |
| [ContractAuditSceneEnum](references/ContractAuditSceneEnum.md) | 审核场景 | - |
| [SignResultEnum](references/SignResultEnum.md) | 签约结果 | - |
| [SignSceneTypeEnum](references/SignSceneTypeEnum.md) | 签约场景 | - |
| [ProcessNodeTypeEnum](references/ProcessNodeTypeEnum.md) | 流程节点类型 | - |
| [ProcessStatusEnum](references/ProcessStatusEnum.md) | 流程状态 | - |
| [ProcessNodeStatusEnum](references/ProcessNodeStatusEnum.md) | 流程节点状态 | - |
| [ContractSubmitStatusEnum](references/ContractSubmitStatusEnum.md) | 合同提交状态 | - |
| [BindTypeEnum](references/BindTypeEnum.md) | 绑定类型 | contract_quotation.bindType |
| [ContractAuthStatusEnum](references/ContractAuthStatusEnum.md) | 合同授权状态 | - |
| [FreeFormRoleTypeEnum](references/FreeFormRoleTypeEnum.md) | 协议平台签署角色 | - |
| [PersonRoleTypeEnum](references/PersonRoleTypeEnum.md) | 人员角色类型 | - |
| [ContractAttachVeracityEnum](references/ContractAttachVeracityEnum.md) | 附件真实性 | - |

---

## 扩展字段定义

`sre_query(action="contract_field")` 返回的 fieldKey 对应的业务含义，请参考 [ContractFieldEnum](references/ContractFieldEnum.md)。

---

## 模块枚举

配置快照 (config_snap) 中的模块标识，请参考 [ContractModuleEnum](references/ContractModuleEnum.md)。

---

## 典型查询流程

### 查询签约人手机号

1. 查 `contract_user` 拿到所有用户
2. 找 `isSign=1` 的记录（即签约人）
3. 取 `phone` 字段（加密的）
4. 调 `sre_query(action="decrypt", encrypted_text="...")` 解密