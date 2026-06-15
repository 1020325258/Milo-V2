---
name: contract-data-dictionary
description: 合同域数据字典与知识图谱 - 实体定义、字段含义、枚举值、实体间关联关系。解读 sre_query 工具返回数据中各字段和枚举值的含义。
---

# 合同域数据字典与知识图谱

当 `sre_query` 工具返回数据时，使用本字典解读字段含义和枚举值。当需要理解合同数据结构、字段关系、或进行跨表关联查询时，参考知识图谱。

---

## 知识图谱

```json
{
  "entities": [
    {
      "name": "contract",
      "table": "contract",
      "description": "合同主表，记录合同的核心信息和状态",
      "fields": [
        {"name": "contractCode", "description": "合同唯一编号，格式为C开头+数字", "type": "string", "isPrimaryKey": true},
        {"name": "contractNo", "description": "合同编号（业务编号）", "type": "string"},
        {"name": "projectOrderId", "description": "项目订单号，18位数字", "type": "string"},
        {"name": "changeOrderId", "description": "变更单号，变更场景下使用", "type": "string"},
        {"name": "type", "description": "合同类型，见 ContractTypeEnum", "type": "byte", "enumRef": "ContractTypeEnum"},
        {"name": "status", "description": "合同状态，见 ContractStatusEnum", "type": "integer", "enumRef": "ContractStatusEnum"},
        {"name": "businessType", "description": "业务类型，见 BusinessTypeEnum", "type": "byte", "enumRef": "BusinessTypeEnum"},
        {"name": "signChannelType", "description": "签署方式，见 SignChannelTypeEnum", "type": "byte", "enumRef": "SignChannelTypeEnum"},
        {"name": "userSignType", "description": "用户签署方式，见 UserSignTypeEnum", "type": "byte", "enumRef": "UserSignTypeEnum"},
        {"name": "auditType", "description": "审核类型，见 AuditTypeEnum", "type": "byte", "enumRef": "AuditTypeEnum"},
        {"name": "userQueryStatus", "description": "用户可见性", "type": "byte", "enum": {"0": "不可见", "1": "可见"}},
        {"name": "userConfirmStatus", "description": "用户确认状态", "type": "byte", "enum": {"0": "未确认", "1": "已确认"}},
        {"name": "userSignStatus", "description": "用户签署状态", "type": "byte", "enum": {"0": "未签署", "1": "已签署"}},
        {"name": "amount", "description": "合同金额", "type": "decimal"},
        {"name": "gbCode", "description": "城市编码", "type": "integer"},
        {"name": "companyCode", "description": "分公司编码", "type": "string"},
        {"name": "bmpNo", "description": "BMP审核单号，用于在审核系统追踪审核流程", "type": "string"},
        {"name": "platformInstanceId", "description": "协议平台合同实例ID，用于电子签章", "type": "long"},
        {"name": "relateContractCode", "description": "授权协议关联 - 公对公签约时，指向关联的授权协议书合同编号", "type": "string"},
        {"name": "previewKey", "description": "预览文件key（S3）", "type": "string"},
        {"name": "userSignedKey", "description": "用户签署后的PDF文件key（S3）", "type": "string"},
        {"name": "bothSignedKey", "description": "双方签署后的PDF文件key（S3）", "type": "string"},
        {"name": "thirdSignedKey", "description": "三方签署后的PDF文件key（S3）", "type": "string"},
        {"name": "pdfPageCount", "description": "线上合同PDF页数", "type": "integer"},
        {"name": "errorMessage", "description": "合同发起失败时的错误信息", "type": "string"},
        {"name": "pdfGenerationMode", "description": "PDF生成模式，见 PdfGenerationModeEnum", "type": "integer", "enumRef": "PdfGenerationModeEnum"},
        {"name": "quotationVersion", "description": "报价版本", "type": "string"},
        {"name": "delStatus", "description": "删除标记", "type": "byte", "enum": {"0": "未删除", "1": "已删除"}},
        {"name": "ctime", "description": "创建时间", "type": "datetime"},
        {"name": "mtime", "description": "更新时间", "type": "datetime"},
        {"name": "createUserId", "description": "创建人UCID", "type": "string"},
        {"name": "createUserName", "description": "创建人姓名", "type": "string"},
        {"name": "modifyUserId", "description": "更新人UCID", "type": "string"},
        {"name": "modifyUserName", "description": "更新人姓名", "type": "string"}
      ],
      "relationships": [
        {"target": "contract_node", "foreignKey": "contractCode", "cardinality": "1:N", "description": "一个合同有多个流程节点"},
        {"target": "contract_user", "foreignKey": "contractCode", "cardinality": "1:N", "description": "一个合同有多个签约人"},
        {"target": "contract_field", "foreignKey": "contractCode", "cardinality": "1:N", "description": "一个合同有多个扩展字段"},
        {"target": "contract_log", "foreignKey": "contractCode", "cardinality": "1:N", "description": "一个合同有多个操作日志"},
        {"target": "contract_quotation_relation", "foreignKey": "contractCode", "cardinality": "1:N", "description": "一个合同关联多个报价单/变更单/S单"},
        {"target": "contract_relation", "foreignKey": "contractCode", "cardinality": "1:N", "description": "一个合同有多个合并发起关联"},
        {"target": "contract", "foreignKey": "relateContractCode", "cardinality": "N:1", "description": "公对公签约时，指向关联的授权协议书"}
      ]
    },
    {
      "name": "contract_node",
      "table": "contract_node",
      "description": "合同流程节点，记录合同生命周期中的关键时间点",
      "fields": [
        {"name": "contractCode", "description": "关联的合同编号", "type": "string"},
        {"name": "nodeType", "description": "节点类型，见 NodeTypeEnum", "type": "byte", "enumRef": "NodeTypeEnum"},
        {"name": "fireTime", "description": "发生时间戳（毫秒）", "type": "long"},
        {"name": "delStatus", "description": "删除标记", "type": "byte", "enum": {"0": "未删除", "1": "已删除"}}
      ],
      "relationships": [
        {"target": "contract", "foreignKey": "contractCode", "cardinality": "N:1", "description": "多个节点属于同一个合同"}
      ]
    },
    {
      "name": "contract_user",
      "table": "contract_user",
      "description": "合同签约人，记录参与合同签署的人员信息",
      "fields": [
        {"name": "contractCode", "description": "关联的合同编号", "type": "string"},
        {"name": "roleType", "description": "角色类型，见 RoleTypeEnum", "type": "byte", "enumRef": "RoleTypeEnum"},
        {"name": "name", "description": "姓名", "type": "string"},
        {"name": "phone", "description": "手机号（加密存储）", "type": "string"},
        {"name": "phonePlain", "description": "手机号（明文，需通过解密接口获取）", "type": "string"},
        {"name": "ucid", "description": "用户ID", "type": "string"},
        {"name": "isSign", "description": "是否为签约人", "type": "byte", "enum": {"0": "不是签约人", "1": "是签约人"}},
        {"name": "isAuth", "description": "是否已实名认证", "type": "byte", "enum": {"0": "未认证", "1": "已认证"}},
        {"name": "certificateType", "description": "证件类型，见 CertificateTypeEnum", "type": "byte", "enumRef": "CertificateTypeEnum"},
        {"name": "certificateNo", "description": "证件号码（加密存储）", "type": "string"},
        {"name": "ctime", "description": "创建时间", "type": "datetime"},
        {"name": "mtime", "description": "更新时间", "type": "datetime"},
        {"name": "delStatus", "description": "删除标记", "type": "byte", "enum": {"0": "未删除", "1": "已删除"}}
      ],
      "relationships": [
        {"target": "contract", "foreignKey": "contractCode", "cardinality": "N:1", "description": "多个签约人属于同一个合同"}
      ]
    },
    {
      "name": "contract_field",
      "table": "contract_field",
      "description": "合同扩展字段，以key-value形式存储合同的业务属性。fieldKey的完整定义见 ContractFieldEnum。",
      "fields": [
        {"name": "contractCode", "description": "关联的合同编号", "type": "string"},
        {"name": "fieldKey", "description": "字段名（英文标识），完整定义见 ContractFieldEnum", "type": "string", "enumRef": "ContractFieldEnum"},
        {"name": "fieldValue", "description": "字段值（字符串形式存储）", "type": "string"},
        {"name": "delStatus", "description": "删除标记", "type": "byte", "enum": {"0": "未删除", "1": "已删除"}}
      ],
      "relationships": [
        {"target": "contract", "foreignKey": "contractCode", "cardinality": "N:1", "description": "多个扩展字段属于同一个合同"}
      ]
    },
    {
      "name": "contract_log",
      "table": "contract_log",
      "description": "合同操作日志，记录合同生命周期中的每次操作",
      "fields": [
        {"name": "contractCode", "description": "关联的合同编号", "type": "string"},
        {"name": "type", "description": "操作类型，见 LogTypeEnum", "type": "byte", "enumRef": "LogTypeEnum"},
        {"name": "content", "description": "日志内容，可能包含错误详情或操作说明", "type": "string"},
        {"name": "remark", "description": "备注", "type": "string"},
        {"name": "createUserName", "description": "操作人姓名", "type": "string"},
        {"name": "ctime", "description": "操作时间", "type": "datetime"},
        {"name": "delStatus", "description": "删除标记", "type": "byte", "enum": {"0": "未删除", "1": "已删除"}}
      ],
      "relationships": [
        {"target": "contract", "foreignKey": "contractCode", "cardinality": "N:1", "description": "多条日志属于同一个合同"}
      ]
    },
    {
      "name": "contract_quotation_relation",
      "table": "contract_quotation_relation",
      "description": "合同与报价单/变更单/S单（子单）的关联关系",
      "fields": [
        {"name": "contractCode", "description": "合同编号", "type": "string"},
        {"name": "billCode", "description": "关联的报价单号/变更单号/S单号（子单号）", "type": "string"},
        {"name": "bindType", "description": "绑定类型，见 BindTypeEnum", "type": "integer", "enumRef": "BindTypeEnum"},
        {"name": "companyCode", "description": "分公司编码", "type": "string"},
        {"name": "status", "description": "关联状态", "type": "integer", "enum": {"1": "当前绑定", "2": "已解绑（换绑）"}},
        {"name": "ctime", "description": "创建时间", "type": "datetime"},
        {"name": "mtime", "description": "修改时间", "type": "datetime"},
        {"name": "delStatus", "description": "删除标记", "type": "byte", "enum": {"0": "未删除", "1": "已删除"}}
      ],
      "relationships": [
        {"target": "contract", "foreignKey": "contractCode", "cardinality": "N:1", "description": "多条关联记录属于同一个合同"}
      ]
    },
    {
      "name": "contract_relation",
      "table": "contract_relation",
      "description": "合同合并发起关联关系，记录多个合同之间通过合并发起方式建立的关联",
      "fields": [
        {"name": "id", "description": "主键ID", "type": "long", "isPrimaryKey": true},
        {"name": "contractCode", "description": "主合同编号", "type": "string"},
        {"name": "relateContractCode", "description": "关联合同编号", "type": "string"},
        {"name": "relationType", "description": "关联类型", "type": "byte", "enum": {"1": "合同发起（合并发起）"}},
        {"name": "ctime", "description": "创建时间", "type": "datetime"},
        {"name": "mtime", "description": "更新时间", "type": "datetime"},
        {"name": "delStatus", "description": "删除标记", "type": "byte", "enum": {"0": "未删除", "1": "已删除"}}
      ],
      "relationships": [
        {"target": "contract", "foreignKey": "contractCode", "cardinality": "N:1", "description": "多条关联记录指向同一个主合同"},
        {"target": "contract", "foreignKey": "relateContractCode", "cardinality": "N:1", "description": "多条关联记录指向同一个关联合同"}
      ]
    }
  ]
}
```

---

## 实体关系概览

```
                          Order (订单)
                               │
                          1:N  ↓
                    ┌── Contract (合同) ──────────────────┐
                    │         │           │                │
                    │    1:N  │  1:N      │                │ relateContractCode
                    │         ↓           │                ↓ (指向同表的授权协议书 type=12)
                    │  ContractNode       │           Contract (合同)
                    │  (流程节点)          │           授权协议书 (type=12)
                    │                     │
                    │    1:N              │
                    ↓         ↓           │
              ContractUser  ContractField │
              (签约人)       (扩展字段)    │
                    │                     │
                    │    1:N              │
                    ↓         ↓           │
              ContractLog  ContractQuotationRelation ──→ PersonalQuote
              (操作日志)    (报价单/S单/变更单关联)       (个性化报价)
                    │
                    │    1:N
                    ↓
              ContractRelation (合并发起关联)
              contractCode → 主合同
              relateContractCode → 关联合同
```

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

### 查询合同完整信息

1. 查 `contract` 拿到合同主数据
2. 查 `contract_user` 拿到签约人列表，`isSign=1` 为签约人
3. 查 `contract_field` 拿到扩展字段（fieldKey → fieldValue）
4. 查 `contract_node` 拿到流程节点时间线
5. 查 `contract_quotation_relation` 拿到关联的报价单/S单