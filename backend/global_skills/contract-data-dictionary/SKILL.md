---
name: contract-data-dictionary
description: 合同域数据字典 - 解读 sre_query 工具返回数据中各字段和枚举值的含义
---

# 合同域数据字典

当 `sre_query` 工具返回数据时，使用本字典解读字段含义和枚举值。

---

## 一、contract 表（合同信息）

`sre_query(action="contract")` 返回的数据对应此表。

| 字段 | 含义 | 取值说明 |
|------|------|----------|
| contractCode | 合同唯一编号 | 以 "C" 开头 + 数字，如 C1776759658764987 |
| contractNo | 合同编号 | 业务编号，非唯一 |
| businessType | 业务类型 | 见「业务类型枚举」 |
| projectOrderId | 订单号 | 18 位纯数字 |
| changeOrderId | 变更单号 | |
| gbCode | 城市编码 | |
| companyCode | 分公司编码 | |
| **type** | **合同类型** | **见「合同类型枚举」** |
| **status** | **合同状态** | **见「合同状态枚举」** |
| pdfGenerationMode | PDF 生成模式 | 1=有版式 2=无版式 |
| userQueryStatus | 用户可见性 | 0=不可见 1=可见 |
| userConfirmStatus | 用户确认状态 | 0=未确认 1=已确认 |
| userSignStatus | 用户签署状态 | 0=未签署 1=已签署 |
| bmpNo | BMP 审核单号 | |
| signChannelType | 签署方式 | 1=线上签约 2=线下补录 |
| userSignType | 用户签署方式 | 0=未知 1=协议确认 2=正式签署 |
| auditType | 审核类型 | 0=不需要审核 1=签前审核 2=签后审核 |
| quotationVersion | 报价版本 | |
| amount | 合同金额 | |
| relateContractCode | 关联合同编号 | |
| platformInstanceId | 协议平台实例 ID | 9 位纯数字 |
| previewKey | 预览文件 key | |
| userSignedKey | 用户签署后文件 key | |
| bothSignedKey | 双方签署后文件 key | |
| thirdSignedKey | 三方签署后文件 key | |
| pdfPageCount | PDF 页数 | |
| delStatus | 删除标记 | 0=未删除 1=已删除 |
| errorMessage | 合同发起失败信息 | 非空时表示发起失败原因 |

---

## 二、contract_user 表（签约人信息）

`sre_query(action="contract_user")` 返回的数据对应此表。

| 字段 | 含义 | 取值说明 |
|------|------|----------|
| contractCode | 合同编号 | |
| **roleType** | **用户角色** | **见「角色类型枚举」** |
| name | 姓名 | |
| **phone** | **手机号（加密）** | **需调用 decrypt 解密** |
| **isSign** | **是否为签约人** | **0=不是签约人 1=是签约人** |
| isAuth | 是否已认证 | 0=未认证 1=已认证 |
| authChannelNo | 认证渠道号 | |
| certificateType | 证件类型 | 1=身份证 2=护照 3=港澳居民通行证 4=台湾居民通行证 5=临时身份证 |
| certificateNo | 证件号码（加密） | 需调用 decrypt 解密 |
| certificateImg1 | 证件图片正面 | |
| certificateImg2 | 证件图片反面 | |
| delStatus | 删除标记 | 0=未删除 1=已删除 |

**查询签约人手机号的典型流程**：
1. 查 `contract_user` 拿到所有用户
2. 找 `isSign=1` 的记录（即签约人）
3. 取 `phone` 字段（加密的）
4. 调 `sre_query(action="decrypt", encrypted_text="...")` 解密

---

## 三、contract_node 表（合同流程节点）

`sre_query(action="contract_node")` 返回的数据对应此表。

| 字段 | 含义 | 取值说明 |
|------|------|----------|
| contractCode | 合同编号 | |
| **nodeType** | **节点类型** | **见「节点类型枚举」** |
| fireTime | 发生时间戳 | 毫秒级时间戳 |
| delStatus | 删除标记 | 0=未删除 1=已删除 |

---

## 四、contract_log 表（合同操作日志）

`sre_query(action="contract_log")` 返回的数据对应此表。

| 字段 | 含义 | 取值说明 |
|------|------|----------|
| contractCode | 合同编号 | |
| **type** | **操作类型** | **见「日志类型枚举」** |
| content | 日志内容 | |
| remark | 备注 | |
| delStatus | 删除标记 | 0=未删除 1=已删除 |

---

## 五、contract_field 表（合同扩展字段）

`sre_query(action="contract_field")` 返回的数据对应此表。

| 字段 | 含义 | 取值说明 |
|------|------|----------|
| contractCode | 合同编号 | |
| **fieldKey** | **字段名称** | **见「合同扩展字段定义」** |
| fieldValue | 字段值 | |
| delStatus | 删除标记 | 0=未删除 1=已删除 |

---

## 六、contract_quotation_relation 表（签约单据关联）

`sre_query(action="contract_quotation")` 返回的数据对应此表。

| 字段 | 含义 | 取值说明 |
|------|------|----------|
| contractCode | 合同编号 | |
| billCode | 关联单据编号 | |
| **bindType** | **绑定类型** | **1=报价单号 2=变更单号 3=子单号** |
| companyCode | 分公司编码 | |
| **status** | **关联状态** | **1=已关联 2=已取消关联** |
| delStatus | 删除标记 | 0=未删除 1=已删除 |

---

## 七、contract_city_company_info 表（城市公司配置）

`sre_query(action="city_company_info")` 返回的数据对应此表。

| 字段 | 含义 | 取值说明 |
|------|------|----------|
| gbCode | 城市编码 | |
| companyCode | 公司编码 | |
| businessType | 业务类型 | 见「业务类型枚举」 |
| contractType | 合同类型 | 见「合同类型枚举」 |
| signChannelType | 签署方式 | 1=线上签约 2=线下补录 |
| auditType | 审核类型 | |
| userSignType | 用户签署方式 | |
| showPlatform | 展示平台 | |
| formId | 版式 ID | 6 位纯数字 |
| formKey | 版式 key | |
| secondFormId | 第二版式 ID | |
| secondFormKey | 第二版式 key | |
| thirdFormId | 第三版式 ID | |
| thirdFormKey | 第三版式 key | |
| sealCode | 图章编码 | |
| auditConfig | 审核配置 JSON | |
| mergeLaunchType | 合并发起的合同类型 | |
| fieldsMap | 扩展字段配置 JSON | |
| configSnap | 配置快照 JSON | |
| processMode | 流程模式 | 1=2.0 流程 2=2.5 流程 |
| version | 版本号 | |
| delStatus | 删除标记 | 0=未删除 1=已删除 |

---

## 八、contract_field_config 表（字段配置）

`sre_query(action="field_config")` 返回的数据对应此表。

| 字段 | 含义 | 取值说明 |
|------|------|----------|
| businessType | 业务类型 | 见「业务类型枚举」 |
| gbCode | 城市编码 | |
| companyCode | 公司编码 | |
| contractType | 合同类型 | 见「合同类型枚举」 |
| version | 版本号 | |
| fieldKey | 字段 key | |
| fieldName | 字段名称 | |
| fieldType | 字段类型 | |
| required | 是否必填 | |
| visible | 是否可见 | |
| editable | 是否可编辑 | |
| delStatus | 删除标记 | 0=未删除 1=已删除 |

---

## 九、contract_protocol_config 表（协议配置）

`sre_query(action="protocol_config")` 返回的数据对应此表。

| 字段 | 含义 | 取值说明 |
|------|------|----------|
| formId | 版式 ID | 6 位纯数字 |
| platformInstanceId | 协议平台实例 ID | 9 位纯数字 |
| templateName | 模板名称 | |
| templateContent | 模板内容 | |
| delStatus | 删除标记 | 0=未删除 1=已删除 |

---

## 十、枚举参考

### 合同类型枚举 (ContractTypeEnum)

| code | 名称 | 说明 |
|------|------|------|
| 1 | 认购合同 | 客户确认意向后签署 |
| 2 | 设计合同 | 确认设计方案服务后签署 |
| 3 | 正式套餐合同 | 确认进入施工阶段后签署 |
| 4 | 套餐变更协议 | 正式套餐合同基础信息变更时签署 |
| 5 | 解约协议 | 草签或正签后解约时签署 |
| 6 | 整装首期款合同 | 确认整装首期款金额后签署 |
| 7 | 套餐施工图纸 | |
| 8 | 销售合同 | 确认定软电品类设计方案服务后签署（原名"个性化主材合同"） |
| 9 | 木作首期款协议 | 确认定软电品类首期款金额后签署 |
| 10 | 其他主材首期款协议 | 确认定软电品类首期款金额后签署 |
| 11 | 设计变更协议 | 确认设计方案变更后签署 |
| **12** | **授权协议书** | |
| 13 | 家电首期款协议 | |
| 14 | 家居首期款协议 | |
| 15 | 定制首期款协议 | |
| 16 | 软装首期款协议 | |
| 17 | 门窗首期款协议 | |
| 18 | 销售合同（零售） | 确认接受零售商品服务后签署 |
| 19 | 销售变更补充协议 | 销售合同信息变更时签署 |
| 20 | 资金存管协议 | |
| 21 | 门窗暖首期款协议 | |
| 22 | 全案合同概要 | |
| 23 | 图纸报价 | |
| 24 | 其他附件 | |
| 25 | K3 首期款协议 | |
| 26 | K5 首期款协议 | |
| 27 | K7 首期款协议 | |
| 28 | 授权委托书 | |
| 29 | 补充协议 | 正式套餐合同条款以外的补充说明 |
| 30 | 和解协议 | 赔付并达成一致时签署 |

### 合同状态枚举 (ContractStatusEnum)

| code | 名称 | 说明 |
|------|------|------|
| 1 | 起草中 | 合同已创建，未发起 |
| 2 | 待确认 | 等待用户确认 |
| 3 | 已确认 | 用户已确认 |
| 4 | 待签署 | 等待用户签署 |
| 5 | 待提交审核 | 等待提交审核 |
| 6 | 审核中 | 正在审核 |
| 7 | 待盖公司章 | 等待公司盖章 |
| 8 | 已签署 | 签署完成（最终状态） |
| 9 | 已取消 | 合同已取消 |
| 10 | 已驳回 | 审核被驳回 |
| 11 | 待盖第三方章 | 等待第三方盖章 |

### 业务类型枚举 (BusinessTypeEnum)

| code | 名称 |
|------|------|
| 1 | 整装 |
| 2 | 团装 |
| 3 | 局装 |
| 4 | 翻新全案 |

### 角色类型枚举 (RoleTypeEnum)

用于 contract_user 表的 roleType 字段。

| code | 名称 | 说明 |
|------|------|------|
| 1 | 业主 | 房屋产权人 |
| 2 | 代理人 | 业主委托的代理人 |
| 3 | 非法代（代理人） | 公司代办人 |
| 4 | 法定代表人 | 公司法定代表人 |

### 节点类型枚举 (NodeTypeEnum)

用于 contract_node 表的 nodeType 字段，记录合同流转的时间节点。

| code | 名称 | 说明 |
|------|------|------|
| 1 | CREATE | 合同创建时间 |
| 2 | SUBMIT | 发起合同时间 |
| 3 | LATEST_AUDIT_CREATE | 最新提交审核时间 |
| 4 | LATEST_AUDIT_PASS | 最新审核通过时间 |
| 5 | USER_CONFIRM | 用户确认时间 |
| 6 | APPLY_SEAL | 申请用章时间 |
| 7 | USER_SIGN | 用户签署完成时间 |
| 8 | COMPANY_SIGN | 盖公司章时间 |
| 9 | FINISH | 最终完成时间 |
| 10 | DELETE | 作废时间 |
| 11 | LATEST_AUDIT_REJECT | 最新审核驳回时间 |
| 12 | DATA_SUPPLEMENT_TIME | 房屋资料上传完毕时间 |
| 13 | CANCEL | 合同已取消时间 |
| 14 | USER_CONFIRM_SIGN_MIX_TIME | 用户确认/签署时间（虚拟节点） |
| 15 | AUTH | 授权时间 |

### 日志类型枚举 (LogTypeEnum)

用于 contract_log 表的 type 字段。

| code | 名称 | 说明 |
|------|------|------|
| 1 | STATUS_CHANGE | 状态变更 |
| 2 | SUBMIT_AUDIT | 提交审核 |
| 3 | AUDIT_REJECT | 审核驳回 |
| 4 | AUDIT_PASS | 审核通过 |
| 5 | USER_SIGN | 签约人签署 |
| 6 | USER_CONFIRM | 用户确认 |
| 7 | COMPANY_SIGN | 盖公司章 |
| 8 | FINISH | 完成 |
| 9 | AUDIT_CREATE_FAIL | 发起审核失败 |
| 10 | COMPANY_SIGN_FAIL | 盖公司章失败 |
| 11 | APPLY_SEAL | 申请用章 |
| 12 | SUBMIT | 发起签约 |
| 13 | UNDO_CONTRACT | 撤销签约 |
| 14 | DELETE | 删除 |
| 16 | DATA_SUPPLEMENT | 房屋资料上传完毕 |
| 17 | CANCEL | 操作合同取消 |
| 18 | UNDO_AUDIT | 审核撤销 |
| 19 | THIRD_PART_SEAL | 盖第三方章 |
| 20 | WATCH_VIDEO | 观看视频 |
| 21 | CREATE_PDF_ERROR | 生成 PDF 异常 |
| 22 | GET_SIGN_URL_ERROR | 获取手签异常 |
| 23 | PREVIEW_PDF | 预览合同 |
| 24 | CONTRACT_BIND_CHANGE | 合同换绑 |
| 25 | CONTRACT_UNBIND | 合同解绑 |

### 签署方式枚举 (SignChannelTypeEnum)

| code | 名称 |
|------|------|
| 1 | 线上签约 |
| 2 | 线下补录 |

### 用户签署方式枚举 (UserSignTypeEnum)

| code | 名称 |
|------|------|
| 0 | 未知 |
| 1 | 协议确认 |
| 2 | 正式签署 |

### 审核类型枚举 (AuditTypeEnum)

| code | 名称 |
|------|------|
| 0 | 不需要审核 |
| 1 | 签前审核 |
| 2 | 签后审核 |

### PDF 生成模式枚举 (PdfGenerationModeEnum)

| code | 名称 |
|------|------|
| 1 | 有版式 |
| 2 | 无版式 |

### 盖章状态枚举 (SealStatusEnum)

| code | 名称 |
|------|------|
| 0 | 无需盖章 |
| 10 | 待盖章 |
| 20 | 盖章成功 |
| 30 | 盖章失败 |

### 自动盖章状态枚举 (SelfSealStatusEnum)

| code | 名称 |
|------|------|
| 1 | 盖章中 |
| 2 | 盖章成功 |
| 3 | 盖章失败 |

### 证件类型枚举 (CertificateTypeEnum)

| code | 名称 |
|------|------|
| 1 | 身份证 |
| 2 | 护照 |
| 3 | 港澳居民通行证 |
| 4 | 台湾居民通行证 |
| 5 | 临时身份证 |

### 主体类型枚举 (ContractObjectTypeEnum)

| code | 名称 |
|------|------|
| 1 | 个人合同 |
| 2 | 公对公合同 |

### 审核状态枚举 (ContractAuditStatusEnum)

用于 contract_audit 表的 auditStatus 字段。

| code | 名称 |
|------|------|
| 1 | 已提交 |
| 2 | 审核通过 |
| 3 | 审核驳回 |

### 审核场景枚举 (ContractAuditSceneEnum)

| code | 名称 |
|------|------|
| 1 | 通用审核 |
| 2 | 设计费专项审核 |

### 签约结果枚举 (SignResultEnum)

| code | 名称 |
|------|------|
| 1 | 成功 |
| 2 | 失败 |
| 3 | 处理中 |

### 签约场景枚举 (SignSceneTypeEnum)

| code | 名称 |
|------|------|
| 10 | 正签签约场景 |
| 20 | 销售合同签约场景 |

### 流程节点类型枚举 (ProcessNodeTypeEnum)

审核流程中的节点类型。

| code | 名称 |
|------|------|
| 1 | 待审核 |
| 10 | 审核 |
| 20 | 复审 |
| 21 | 复审通过 |
| 100 | 完成 |

### 流程状态枚举 (ProcessStatusEnum)

审核流程的整体状态。

| code | 名称 |
|------|------|
| 10 | 待审核 |
| 20 | 审核中 |
| 21 | 审核通过 |
| 22 | 审核驳回 |
| 23 | 复审中 |
| 24 | 复审通过 |
| 100 | 已完成 |

### 流程节点状态枚举 (ProcessNodeStatusEnum)

| code | 名称 |
|------|------|
| 0 | 待执行 |
| 1 | 执行中 |
| 2 | 成功 |
| -1 | 失败 |

### 合同提交状态枚举 (ContractSubmitStatusEnum)

| code | 名称 |
|------|------|
| 0 | 进行中 |
| 1 | 成功 |
| 2 | 失败 |

### 绑定类型枚举 (BindTypeEnum)

用于 contract_quotation_relation 表的 bindType 字段。

| code | 名称 |
|------|------|
| 1 | 报价单号 |
| 2 | 变更单号 |
| 3 | 子单号 |

### 合同授权状态枚举 (ContractAuthStatusEnum)

| code | 名称 |
|------|------|
| 1 | 未认证未授权 |
| 2 | 已认证未授权 |
| 3 | 已认证已授权 |
| 4 | 无关联授权协议 |

### 协议平台签署角色枚举 (FreeFormRoleTypeEnum)

| code | 名称 |
|------|------|
| decoration_company | 装修公司 |
| signUser | 签约用户 |
| signAgent | 委托代理人 |
| companySignUser | 签约公司 |
| retail_company | 零售主体 |

### 人员角色类型枚举 (PersonRoleTypeEnum)

| code | 名称 |
|------|------|
| 0 | 客户 |
| 1 | 代理人 |

### 附件真实性枚举 (ContractAttachVeracityEnum)

| code | 名称 |
|------|------|
| 0 | 初始值 |
| 1 | 准确 |
| 2 | 不准确 |

---

## 十一、合同扩展字段定义 (ContractFieldEnum)

`sre_query(action="contract_field")` 返回的 fieldKey 对应以下定义。

### fieldType=1：企业签约信息

| fieldKey | 含义 | 取值说明 |
|----------|------|----------|
| legalPhone | 法定代表人手机号（加密） | |
| legalCertificateType | 法定代表人证件类型 | 见「证件类型枚举」 |
| legalName | 法定代表人姓名 | |
| legalCertificateNo | 法定代表人证件号码（加密） | |
| companyName | 甲方公司名称 | |
| companyCreditCode | 甲方公司统一社会信用代码 | |
| companyAgentName | 甲方公司经办人姓名 | |
| companyAgentPhone | 甲方公司经办人手机号（加密） | |
| companyAgentCertificateType | 甲方公司经办人证件类型 | 见「证件类型枚举」 |
| companyAgentCertificateNo | 甲方公司经办人证件号码（加密） | |
| **signRole** | **甲方公司签约人** | **3=公司代办人 4=法定代表人** |

### fieldType=2：房屋信息

| fieldKey | 含义 |
|----------|------|
| resblockName / resblockId | 小区名称 / 编码 |
| districtName / districtId | 行政区名称 / 编码 |
| gbName / gbCode | 城市名称 / 编码 |
| buildingName / buildingId | 楼栋名称 / 编码 |
| unitName / unitId | 单元名称 / 编码 |
| floorName / floorId | 楼层名称 / 编码 |
| houseName / houseId | 门牌号名称 / 编码 |
| houseCertificateAddress | 房本地址 |
| houseCertificateNo | 房产证编号 |
| area | 建筑面积 |
| houseType | 房屋类型：0=未知 1=新房 2=老房 |
| houseBuildType | 户型结构：0=未知 1=复式 2=平层 3=跃层 4=错层 5=LOFT 6=跃复一体 7=排屋 8=别墅 9=自建房 |
| structure | 住宅结构：1=砖结构 2=砖混结构 3=钢筋混凝土框架结构 4=钢筋混凝土核心筒剪力墙结构 5=其他 |
| parlorCnt / roomCnt / cookroomCnt / toiletCnt / balconyCnt / storageCnt | 客厅/卧室/厨房/卫生间/阳台/储物间 数量 |

### fieldType=3：承包约定信息

| fieldKey | 含义 | 取值说明 |
|----------|------|----------|
| projectContractModeCode | 工程承包方式 | 0=未知 1=乙方包工包料 2=乙方包工部分包料 3=乙方包工甲方包料 |
| constructionDrawMode | 施工图纸方式 | 1=甲方自行设计 2=签订设计服务协议 3=未签订 |
| needDesignerAmount | 是否约定设计费 | 0=不在正签合同约定 1=在正签合同中约定 |
| clearDay | 甲方提供施工条件的时间 | |
| beforeDeliveryDaysToWork | 提前通知开工天数 | |

### fieldType=4：签约信息

| fieldKey | 含义 | 取值说明 |
|----------|------|----------|
| contractObjectType | 主体类型 | 1=个人合同 2=公对公合同 |
| businessType | 业务类型 | 见「业务类型枚举」 |
| signChannelType | 签约形式 | 1=线上签约 2=线下补录 |
| userSignType | 签署方式 | 1=协议确认 2=正式签署 |
| userSignTime | 用户签约时间 | |
| companySignTime | 公司签署时间 | |
| unitedCompanyName | 乙方公司名称 | |

### fieldType=5：工期信息

| fieldKey | 含义 |
|----------|------|
| planStartTime | 计划开工日期 |
| totalDuration / totalPeriod | 总工期 |

### fieldType=6：个人签约信息

| fieldKey | 含义 |
|----------|------|
| houseOwnerName / ownerName | 房屋产权人 / 产权人姓名 |
| ownerPhone | 产权人手机号（加密） |
| ownerCertificateType | 产权人证件类型 |
| ownerCertificateNo | 产权人证件号码（加密） |
| haveAgent | 是否有代理人：0=没有 1=有 |
| agentName / agentPhone | 代理人姓名 / 手机号（加密） |
| agentCertificateType / agentCertificateNo | 代理人证件类型 / 号码（加密） |
| contractSignName / contractSignPhone | 合同签约人姓名 / 手机号（加密） |

### fieldType=7：设计师信息

| fieldKey | 含义 |
|----------|------|
| designerName | 设计师姓名 |
| designerUcId | 设计师系统号 |

### fieldType=8：税率信息

| fieldKey | 含义 |
|----------|------|
| taxRate | 发票税率 |

### fieldType=9：纠纷处理

| fieldKey | 含义 | 取值说明 |
|----------|------|----------|
| disputeDealMode | 纠纷处理方式 | 1=提交杭州仲裁委员会仲裁 2=依法向人民法院起诉 |

### fieldType=10：甲供清单

| fieldKey | 含义 |
|----------|------|
| materialList | 甲供材料清单 |

### fieldType=11：报价信息

| fieldKey | 含义 |
|----------|------|
| comboName | 所选套餐 |
| pricingArea | 计价面积 |
| houseLayout | 改后户型 |
| quotePrice | 正签/正式套餐合同报价总金额 |
| personalTotalPrice | 定软电品类报价总金额 |
| contractPriceTotal | 正签/正式套餐合同总金额 |

### fieldType=12：收款计划

| fieldKey | 含义 |
|----------|------|
| collectionPlanConfigInfo | 工程款/合同款收款计划 |

---

## 十二、合同模块枚举 (ContractModuleEnum)

用于配置快照 (config_snap) 中的模块标识。

| key | 含义 |
|-----|------|
| signInfo | 签约信息 |
| projectInfo | 项目信息 |
| promiseInfo | 承包约定 |
| guaranteeInfo | 保修 |
| activityInfo | 优惠信息 |
| contractPrice | 合同总价 |
| quotation | 方案报价 |
| drawing | 施工图纸 |
| collectionPlanConfigInfo | 收款计划 |
| contractAttachInfo | 备件 |
| personalQuotation | 个性化报价 |
| businessInfo | 业务信息 |
| amountInfo | 金额总计信息 |
| personalCollectionPlanInfo | 定软电收款计划 |
| supplementItemInfo | 补充协议信息 |
| settlementItemInfo | 和解协议信息 |
