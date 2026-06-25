# ContractContextAspect 代码分析报告

## 概述

`ContractContextAspect` 是一个 Spring AOP 切面，通过 `@ContractDataPrepare` 注解拦截合同提交接口，在业务方法执行**之前**完成数据预处理，将各种外部依赖数据提前加载到线程上下文 `ContractContext` 中，供后续合同生成逻辑使用。

**拦截的接口列表**（`contractSubmitUriList`）：
| URI | 说明 |
|-----|------|
| `/home/contract/submit` | 家装端合同提交 |
| `/pc/contract/submit` | PC端合同提交 |
| `/pc/changeContract/submit/v2` | PC端变更合同提交 |
| `/home/changeContract/submit` | 家装端变更合同提交 |

---

## 1. `beforeHandle(JoinPoint)` — 主编排方法（@Before 切面入口）

### 方法职责
整个切面的核心编排方法，在合同提交业务方法执行前，初始化上下文、并行执行各项数据预处理任务。

### 执行流程

```
初始化 Context
    ↓
参数预处理 preHandleParam()
    ↓
处理可重复发起合同的前置撤销 dealReContractLaunch()
    ↓
设置入参到 Context
    ↓
判断 processV25 / businessType → 写入 Context
    ↓
并行执行 9 个数据准备任务（线程池）
    ├── dealBaseInfo()           → 基础信息
    ├── dealPlanAllDTO()         → 报价信息
    ├── dealComboInfo()          → 套餐信息
    ├── dealProjectInfo()        → 项目信息
    ├── getOperatorName()        → 操作人姓名
    ├── dealDrawingDTO()         → 图纸信息
    ├── dealEscrowDTO()          → 存管账户信息
    ├── dealStandardDesignAmountDTO() → 标准设计费
    └── dealMultiCompanyInfo()   → 合同主体（分公司）信息
    ↓
串行执行：
    ├── 获取合同城市分公司配置 → context.setContractCityCompanyInfo()
    ├── 计算合同模式 → setContractMode()
    └── 正式套餐合同设计费预处理（从报价合并）
```

### 关键设计
- **并行化**：通过 `ParallelTaskService` 将 9 个数据准备任务并行提交，用 `awaitTasksResult()` 等待全部完成，大幅减少接口响应时间。
- **ThreadLocal 上下文**：`ContractContextHandler` 使用 ThreadLocal 存储 `ContractContext`，保证线程安全。通过 `@After` / `@AfterThrowing` 清理上下文，防止内存泄漏。

### 与 ContractDetailAspect 的关系
`beforeHandle` 与 DetailAspect 的 `beforeHandle` 是**同构设计**——都通过 AOP 初始化上下文并并行加载数据。但 ContextAspect 侧重**提交前的数据校验和预处理**（参数清洗、报价一致性校验），DetailAspect 侧重**查询时的数据聚合和展示**。

---

## 2. `afterHandle()` / `afterThrowing()` — 上下文清理（@After / @AfterThrowing）

### 方法职责
确保 `ContractContextHandler.clearContext()` 被调用，清除 ThreadLocal 中的上下文数据。

### 输出
无。纯清理操作。

### 与 ContractDetailAspect 的关系
与 DetailAspect 中的同名方法完全一致——都是上下文清理，属于 AOP 的标准生命周期管理。

---

## 3. `preHandleParam(ContractReqDTO)` — 参数预处理

### 方法职责
对前端传入的合同请求参数进行**清洗和规范化**，确保参数合法、冗余字段被清除。

### 数据来源
纯前端入参处理，**不调用任何 RPC/Service**。

### 输出字段
修改 `contractReq` 的以下模块：

| 修改目标 | 逻辑 |
|---------|------|
| `contractReq.contractSubmit` | 根据请求 URI 判断是否为提交请求 |
| `signInfo` | 调用 `preHandleSignInfoParam()` 清洗签约信息 |
| `promiseInfo.afterDiscountDesignerAmount` | 未约定设计费时清空 |
| `promiseInfo.materialList` | 甲供材料模式（`B_LABOR_MATERIALS`）时清空 |
| `projectInfo` | 调用 `preHandleProjectParam()` 处理项目字段 |

### 条件分支
| 条件 | 处理 |
|------|------|
| `needDesignerAmount` 为空或为"否" | 清空 `afterDiscountDesignerAmount` |
| `needDesignerAmount` 为"是" | 将设计费金额同步到 `projectInfo` |
| `projectContractModeCode == B_LABOR_MATERIALS`（甲供材料） | 清空材料清单 |

### 与 ContractDetailAspect 的关系
ContextAspect 独有的方法。DetailAspect 是查询接口，不需要做参数清洗。

---

## 4. `preHandleSignInfoParam(ContractReqDTO)` — 签约信息参数清洗

### 方法职责
根据合同类型、签约形式（个人/公对公）、是否有代理人、签约渠道等条件，**清除不相关的冗余字段**，避免脏数据入库。

### 数据来源
纯前端入参 + `AttachCommonService.attachOcrOpenCity()` 判断 OCR 城市开关。

### 输出字段
修改 `contractReq.signInfo` 和 `contractReq.contractAttachInfo` 的大量字段。

### 条件分支逻辑（按优先级）

#### ① 设计费来源默认值
| 条件 | 处理 |
|------|------|
| 合同类型 = 套餐变更协议(4) 或 设计变更协议(11) | 设计费来源默认设为"合同" |

#### ② OCR 城市开关
| 条件 | 处理 |
|------|------|
| `attachOcrOpenCity = true` | 将 `haveHouseProve`、`agentSign` 同步到 `contractAttachInfo` |

#### ③ 签约形式互斥清空
| 签约形式 | 清空内容 |
|---------|---------|
| **公对公**（`COMPANY`） | 清空全部个人签约数据（业主信息、代理人信息、身份证等） |
| 公对公 + 法人签约 + 非授权协议 | 追加清空公司代理人信息 |
| **个人签约**（`PERSON`） | 清空全部公对公数据（公司名称、信用代码、法人信息、营业执照等） |

#### ④ 代理人相关
| 条件 | 处理 |
|------|------|
| 无代理人（`haveAgent = NO`） | 清空代理人全部信息 |
| 无代理人委托证明（`agentSign != YES`） | 清空委托证明附件 |
| C端授权 + 有代理人 | `agentSign` 强制设为 `YES`（等同于有委托证明） |

#### ⑤ 签约渠道
| 条件 | 处理 |
|------|------|
| 线上签约 | 清空线下合同相关字段（附件类型、附件URL、签署时间等） |

#### ⑥ 房产证明互斥清空
根据 `haveHouseProve` 的值，**只保留对应的证明类型**，清空其他所有证明字段：

| 房产证明类型 | 保留 | 清空 |
|------------|------|------|
| 房产证 | `houseCertificate` | 其他权属证明、购房合同、认购合同、契税票、特殊房产 |
| 其他权属证明 | `otherOwnerShip` | 房产证、购房合同、认购合同、契税票、特殊房产 |
| 购房合同 | `houseTradeContract` | 其余全部 |
| 认购合同 | `houseSubscribeContract` | 其余全部 |
| 契税票 | `deedTicket` | 其余全部 |
| 特殊房产证明 | `specialHouse` | 其余全部 |

#### ⑦ 解约协议线下签署
| 条件 | 处理 |
|------|------|
| 解约协议(5) + 线下签约 | 根据（个人/公对公）×（有无代理人/法人/公司代理）4种组合，将 `terminalName`/`terminalPhone` 映射到对应签约人字段 |

#### ⑧ 变更协议清空团装解约字段
| 条件 | 处理 |
|------|------|
| 合同类型 = 套餐变更协议(4) | 清空 `groupTerminalCertificate` 相关字段 |

#### ⑨ 身份证正反面兜底 + 永久 code 兼容
| 条件 | 处理 |
|------|------|
| `userCertificateUnifyDocumentCode` 中正反面为空 | 从 `attachReadyResponseMap` 兜底补充 |
| documentCode 以 `SDOCUMENT` 开头 | 从 `attachReadyResponseMap` 获取永久 code 替换，找不到则抛异常 |

### 与 ContractDetailAspect 的关系
ContextAspect 独有。DetailAspect 查询时不接收前端入参，不做参数清洗。

---

## 5. `preHandleProjectParam(ContractReqDTO)` — 项目信息字段默认值

### 方法职责
根据合同模块配置，为前端未传入的项目信息字段设置**默认值 0**，避免后续空指针。

### 数据来源
- `ContractUnifyService.getModuleInfo()` — 获取合同模块和字段配置
- 纯前端入参

### 输出字段
修改 `contractReq.projectInfo`：

| 条件（字段配置包含） | 默认值处理 |
|-------------------|----------|
| 包含 `resblockObj` 字段 | `resblockId` 为 null 时设为 `0L` |
| 包含 `addressObj` 字段 | `buildingId`/`unitId`/`houseId`/`floorId` 为 null 时设为 `0L` |

### 与 ContractDetailAspect 的关系
ContextAspect 独有。DetailAspect 不做参数默认值处理。

---

## 6. `dealBaseInfo(ContractReqDTO, ContractContext)` — 基础信息准备

### 方法职责
判断当前项目是否为开发商渠道（developer channel），写入上下文。

### 数据来源
| 调用 | 入参 | 返回值 |
|------|------|-------|
| `ContractUnifyService.isDeveloperChannel(projectOrderId)` | projectOrderId | boolean |

### 输出字段
| Context 字段 | 值 |
|-------------|-----|
| `context.developerChannel` | 是否为开发商渠道 |

### 与 ContractDetailAspect 的关系
与 DetailAspect 中 `dealBaseInfo` 对应。两者逻辑相同——都是获取基础渠道标识。

---

## 7. `dealPlanAllDTO(ContractReqDTO, ContractContext)` — 报价信息准备（最复杂的方法）

### 方法职责
根据合同类型获取对应的报价信息，是整个切面中**分支最复杂、调用链最长**的方法。

### 数据来源

| RPC/Service | 入参 | 返回值 |
|-------------|------|-------|
| `CommonBusinessService.getBusinessType()` | projectOrderId | Byte 业务类型 |
| `CommonBusinessService.isPROCESS_V2_5()` | projectOrderId, contractType | boolean |
| `AtomBudgetRpc.getPreQuotationByBillCode()` | billCode | `LightQuotationItem` 预估报价 |
| `HomeAndPcCommonService.getExpectContractAmount()` | projectOrderId, packageId, houseType, area, valuationArea, advanceRate | `ComboPriceInfo` |
| `ContractConfigVersionService.getContractConfigAllVersion()` | convertProjectOrderId | `ContractVersionConfig` |
| `ProjectInfoReadService.getByProjectOrderId()` | projectOrderId | `ProjectInfoDTO` |
| `QuotationFeignService.getPackageByCombCode()` | packageId, organizationMode | `ComboBaseDTO` |
| `AtomChangeRpc.getChangeApplyInfo()` | changeOrderId | `ChangeApplyInfoDTO` |
| `ChangeContractUnifyService.getQuoteBillDiff()` | projectOrderId, changeOrderId | `QuoteChangeDiffBO` |
| `HomeOrderDataConversionService.contractSourceDate()` | projectOrderId, changeOrderId | `ContractSourceDataBO` |
| `ContractDependentDataService.queryPersonalQuoteInfoV2()` | bindOrderInfo | `List<PersonalContractData>` |
| `ContractDependentDataService.buildPersonalContractData()` | contractSourceDataBO, projectOrderId, billCodeInfoList, subOrderInfoList | `List<PersonalContractData>` |

### 输出字段

| Context 字段 | 说明 |
|-------------|------|
| `context.planAllDTO` | 报价全量数据 |
| `context.contractSourceDataBO` | 合同数据源（含 planAllDTO + personalContractData） |
| `context.designQuoteFeeDTO` | 设计费报价信息（仅正式套餐合同） |
| `contractReq.projectInfo.*` | 多个项目信息字段被补充（预估合同额、套餐名、B支付金额等） |

### 条件分支逻辑

```
合同类型判断
├── 首期款合同(6)
│   ├── 翻新全案(4) → 直接返回，不查报价
│   ├── 支持预估报价 → dealAdvancePreQuotation() 校验一致性
│   └── 通用 → getExpectContractAmount() + 查字段配置决定是否写入 expectContractAmount
│
├── 非 planAllContractTypes（1认购/2设计/5解约/6首期款等）→ 直接返回
│
└── planAllContractTypes（3正式套餐/4变更/7图纸/8销售）
    ├── 变更协议(4) + 2.5模式 + 协同签约 → buildAtomChangeQuotation()（中控变更报价）
    ├── 销售合同(8) → queryPersonalQuoteInfoV2()（个性化报价）
    └── 通用 → contractSourceDate() 通用报价 + buildPersonalContractData() C报价
        └── 正式套餐合同(3) + 有设计费信息 → 构建 DesignQuoteFeeDTO
```

### 与 ContractDetailAspect 的关系
与 DetailAspect 中 `dealPlanAllDTO` **高度对应**，但有关键差异：
- ContextAspect 增加了**首期款合同的预估合同额计算**和**报价一致性校验**（`dealAdvancePreQuotation`）
- ContextAspect 需要额外处理 `DesignQuoteFeeDTO`（设计费从报价获取的场景）
- DetailAspect 可能额外处理报价数据的展示格式化

---

## 8. `dealAdvancePreQuotation(ContractReqDTO, ContractContext)` — 首期款预估报价校验

### 方法职责
首期款合同提交时，**实时校验前端参数与报价单数据是否一致**，不一致则拦截提交。

### 数据来源
| 调用 | 入参 | 返回值 |
|------|------|-------|
| `AtomBudgetRpc.getPreQuotationByBillCode()` | billCode（报价单单号） | `LightQuotationItem` |

### 校验规则
| 校验项 | 前端参数 | 报价单数据 |
|-------|---------|----------|
| 装修 PDF 文件 | — | `decoratePdfFile` 不能为空 |
| 计价面积 | `requestQuotation.pricingArea` | `rpcQuotation.pricingArea` |
| 预估合同额 | `requestQuotation.expectContractAmount` | `rpcQuotation.hardTotalPrice` |
| 套餐编码 | `requestQuotation.comboCode` | `rpcQuotation.comboBaseInfo.comboCode` |
| 套餐名称 | `requestQuotation.comboName` | `rpcQuotation.comboBaseInfo.comboName` |

任一不一致则抛出业务异常，阻止提交。

### 条件分支
| 条件 | 处理 |
|------|------|
| billCodeList 为空 | 抛异常："首期款合同缺少报价单单号" |
| 报价单查询结果为 null | 抛异常：报价单状态已变更 |
| 字段不一致 | 抛异常：报价单字段已变更 |

### 与 ContractDetailAspect 的关系
ContextAspect 独有。DetailAspect 不做一致性校验。

---

## 9. `buildAtomChangeQuotation(changeOrderId, projectOrderId, context)` — 变更协议报价构建

### 方法职责
为 2.5 模式下的套餐变更协议，从**中控系统**获取变更报价数据并转换为 `PlanAllDTO`。

### 数据来源
| 调用 | 入参 | 返回值 |
|------|------|-------|
| `AtomChangeRpc.getChangeApplyInfo()` | changeOrderId | `ChangeApplyInfoDTO`（含变更范围列表） |
| `ChangeContractUnifyService.getQuoteBillDiff()` | projectOrderId, changeOrderId | `QuoteChangeDiffBO` |
| `HomeOrderDataConversionService.changeHardDecorationFileData()` | changeOrderId | `PlanAttachmentDTO` |
| `ChangeContractUnifyService.atomChangeQuotationConvertToPlanAllDTO()` | budgetPreviewDTO, baseChangePdf | `PlanAllDTO` |

### 条件分支
| 条件 | 处理 |
|------|------|
| 变更范围包含报价变更（`QUOTATION`） | 并行获取报价差异 + 硬装附件，使用 `quoteBill`（变更后） |
| 变更范围不含报价变更 | 只获取报价差异，使用 `preQuoteBill`（变更前） |

### 输出字段
返回 `PlanAllDTO`，由调用方写入 `context.planAllDTO` 和 `context.contractSourceDataBO`。

### 与 ContractDetailAspect 的关系
与 DetailAspect 中对应方法逻辑一致。DetailAspect 查询变更协议详情时也需要用相同的逻辑构建报价展示数据。

---

## 10. `dealComboInfo(ContractReqDTO, ContractContext)` — 套餐信息准备

### 方法职责
获取 2.5 模式下整装业务正式套餐合同的**套餐列表**信息。

### 数据来源
| 调用 | 入参 | 返回值 |
|------|------|-------|
| `OrderStandardQueryRpc.homeStandardOutput()` | projectOrderId, moduleParams（指定获取 `COST_CONTROL_BUDGET_STANDARD_COMBO` 模块） | `HomeProject` |

### 条件分支（三重守卫）
| 条件 | 不满足时处理 |
|------|------------|
| `processV25 = false` | 直接返回 |
| `businessType ≠ HOUSE_CERTIFICATE`（整装） | 直接返回 |
| `contractType ≠ PACKAGE_FORMAL`（正式套餐合同） | 直接返回 |

仅 **2.5模式 + 整装业务 + 正式套餐合同** 三个条件同时满足才执行。

### 输出字段
| Context 字段 | 值 |
|-------------|-----|
| `context.comboDTOList` | 套餐列表 `List<ComboDTO>` |

### 与 ContractDetailAspect 的关系
与 DetailAspect 中 `dealComboInfo` 对应。逻辑完全相同——都通过 RPC 获取套餐模块数据。DetailAspect 用此数据展示套餐选项，ContextAspect 用此数据在提交时校验套餐有效性。

---

## 11. `dealProjectInfo(ContractReqDTO, ContractContext)` — 项目信息准备

### 方法职责
获取项目信息，校验项目存在性和分公司信息完整性。

### 数据来源
| 调用 | 入参 | 返回值 |
|------|------|-------|
| `CommonBusinessService.obtainProjectRelationId()` | projectOrderId | 转换后的项目单号（处理关联项目） |
| `ProjectInfoReadService.getByProjectOrderIdWithoutCache()` | convertProjectOrderId | `ProjectInfoDTO` |

### 条件分支
| 条件 | 处理 |
|------|------|
| projectInfo == null | 抛异常："获取项目信息失败" |
| 分公司编码为空 | 抛异常："项目缺少分公司信息" |

### 输出字段
| Context 字段 | 值 |
|-------------|-----|
| `context.projectInfoDTO` | 项目信息 |

### 与 ContractDetailAspect 的关系
与 DetailAspect 中 `dealProjectInfo` 对应。DetailAspect 可能不做强制校验（允许展示不完整数据），ContextAspect 必须校验通过才能提交。

---

## 12. `dealDrawingDTO(ContractReqDTO, ContractContext)` — 图纸信息准备

### 方法职责
根据合同类型和业务类型，获取对应的施工图纸数据。

### 数据来源
| 调用 | 入参 | 返回值 |
|------|------|-------|
| `AtomDrawingRpc.listDrawings()` | projectOrderId, softConfigList | `DeliverDrawingDTO` |
| `AtomDrawingRpc.getChangeListDrawings()` | projectOrderId, changeOrderId, softConfigList | `DeliverDrawingDTO` |
| `ContractBusinessService.getGroupDrawingDTO()` | projectOrderId | `DeliverDrawingDTO` |
| `ContractSigningSourceRouter.route().buildPersonalDrawing()` | bindOrderInfo, softConfigList, false | `DeliverDrawingDTO` |

### 条件分支
```
合同类型守卫
├── 非 drawingContractTypes（3/7/8/4）→ 返回
├── 非 2.5 模式 → 返回
│
├── 正式套餐合同(3) + 团装(2) → getGroupDrawingDTO()（团装专用方法）
├── 变更协议(4) → getChangeListDrawings()（变更图纸）
├── 销售合同(8) → route().buildPersonalDrawing()（个性化图纸路由）
└── 其他（正式套餐/图纸合同）→ listDrawings()（通用图纸查询）
```

`softConfigList`（软装配置清单）仅对整装(1)和团装(2)业务类型为 `true`。

### 输出字段
| Context 字段 | 值 |
|-------------|-----|
| `context.drawingDTO` | 图纸信息 `DeliverDrawingDTO` |

### 与 ContractDetailAspect 的关系
与 DetailAspect 中 `dealDrawingDTO` **高度对应**。逻辑一致，但 ContextAspect 增加了 `ContractSigningSourceRouter` 的路由机制来处理销售合同的个性化图纸获取。

---

## 13. `dealEscrowDTO(ContractReqDTO, ContractContext)` — 存管账户信息准备

### 方法职责
获取资金存管账户的开户信息（户名、证件号、开户时间等），用于合同中展示存管信息。

### 数据来源
| 调用 | 入参 | 返回值 |
|------|------|-------|
| `EscrowDomain.queryEscrowAccountInfo()` | projectOrderId, `FundEscrowBusinessTypeEnum.DECORATE_PROJECT` | `EscrowAccountDetailDTO` |

### 条件分支
| 条件 | 处理 |
|------|------|
| 合同类型不在 `getShowEscrowUserAccountInfoList()` 中 | 直接返回 |
| escrowAccountDetailDTO == null | 不设置（静默跳过） |

### 输出字段
| Context 字段 | 子字段 | 来源 |
|-------------|--------|------|
| `context.escrowInfo` | `openAccountTime` | 开户时间 |
| | `idNumber` | 证件号码 |
| | `idType` | 证件类型 |
| | `name` | 户名 |
| | `phone` | 手机号 |

### 与 ContractDetailAspect 的关系
与 DetailAspect 中 `dealEscrowDTO` 对应。两者逻辑相同。

---

## 14. `dealStandardDesignAmountDTO(ContractReqDTO, ContractContext)` — 标准设计费金额准备

### 方法职责
为设计合同(2)获取**标准设计费金额**和**设计师职级**（仅在特定城市生效）。

### 数据来源
| 调用 | 入参 | 返回值 |
|------|------|-------|
| `ContractUnifyService.designFeeCalculateIsOpen()` | projectOrderId | boolean（设计费计算是否全国开城） |
| `HomeAndPcCommonService.getStandardDesignFee()` | projectOrderId, area | `DesignSignPriceInfo` |

### 条件分支（四重守卫）
| 条件 | 不满足时处理 |
|------|------------|
| `contractType ≠ DESIGN`(2) | 直接返回 |
| 设计费计算全国开城 | 直接返回（由新接口 preFillReqData 处理） |
| 城市不在 `standardDesignFeeCityCodes` 配置中 | 直接返回 |
| `area` 为空 | 直接返回 |

### 输出字段
| 输出目标 | 字段 | 值 |
|---------|------|-----|
| `contractReq.projectInfo` | `preDiscountDesignerAmount` | 标准设计费金额 |
| `contractReq.projectInfo` | `designerPsLevelName` | 设计师职级名称 |

### 与 ContractDetailAspect 的关系
与 DetailAspect 中对应方法逻辑一致。都用于设计合同的设计费计算。ContextAspect 中此方法是并行任务之一，DetailAspect 中也是。

---

## 15. `dealMultiCompanyInfo(ContractReqDTO, ContractContext)` — 资金存管合同主体信息

### 方法职责
为资金存管协议(20)获取**整装和零售**两个业务线对应的分公司信息，用于生成存管合同的甲方/乙方主体。

### 数据来源
| 调用 | 入参 | 返回值 |
|------|------|-------|
| `FundEscrowService.getFundEscrowEntryInfoByProjectOrderId()` | projectOrderId | `FundEscrowInfoDTO` |
| `EscrowRpc.queryFundEscrowAccountBasicInfo()` | projectOrderId, `DECORATE_PROJECT` | `EscrowAccountBasicInfoDTO` |
| `MdmDataRpc.getInfoByMerchantNos()` | merchantNoList | `Map<merchantNo, CompanyDetailInfoDto>` |
| `MdmRpc.obtainMdmMapByMdmCodes()` | companyCodeList（备选） | `Map<code, MdmDTO>` |
| `CommonBusinessService.getCompanyCodeForEscrow()` | 多参数 | 公司编码 |

### 条件分支
| 条件 | 处理 |
|------|------|
| `contractType ≠ FUND_ESCROW`(20) | 直接返回 |
| fundEscrowInfoDTO == null | 静默返回 |
| escrowRangeList 为空 | 静默返回 |
| 整装范围 decorateRangeDTO == null | 抛异常 |
| 零售范围 retailRangeDTO != null | 额外获取零售分公司信息 |

### 输出字段
| Context 字段 | 值 |
|-------------|-----|
| `context.contractCompanyList` | `List<ContractCompanyAspectInfo>`，含整装分公司 + 可选零售分公司 |

### 与 ContractDetailAspect 的关系
与 DetailAspect 中 `dealMultiCompanyInfo` 对应。逻辑基本一致——都为资金存管协议获取合同主体信息。

---

## 16. `isContractSubmitRequest()` / `getRequestUri()` — 请求类型判断

### 方法职责
判断当前 HTTP 请求是否为合同提交请求（URI 在 `contractSubmitUriList` 中）。

### 数据来源
从 `RequestContextHolder` 获取当前请求的 URI。

### 输出
设置 `contractReq.contractSubmit` 布尔值。

### 与 ContractDetailAspect 的关系
ContextAspect 独有。DetailAspect 是查询接口，不需要判断提交/查询类型。

---

## 总结：ContextAspect vs DetailAspect 对照表

| 方法 | ContextAspect | DetailAspect | 差异说明 |
|------|:---:|:---:|---------|
| `beforeHandle` | ✅ | ✅ | 编排结构相同，任务列表可能有差异 |
| `afterHandle/afterThrowing` | ✅ | ✅ | 完全相同，上下文清理 |
| `preHandleParam` | ✅ | ❌ | Context 独有：提交时的参数清洗 |
| `preHandleSignInfoParam` | ✅ | ❌ | Context 独有：签约信息字段互斥清空 |
| `preHandleProjectParam` | ✅ | ❌ | Context 独有：项目字段默认值 |
| `dealBaseInfo` | ✅ | ✅ | 基础信息，逻辑一致 |
| `dealPlanAllDTO` | ✅ | ✅ | 高度对应，Context 增加了首期款校验和设计费合并 |
| `dealAdvancePreQuotation` | ✅ | ❌ | Context 独有：首期款报价一致性校验 |
| `buildAtomChangeQuotation` | ✅ | ✅ | 变更报价构建，逻辑一致 |
| `dealComboInfo` | ✅ | ✅ | 套餐信息，逻辑一致 |
| `dealProjectInfo` | ✅ | ✅ | Context 强校验，Detail 可能弱校验 |
| `dealDrawingDTO` | ✅ | ✅ | Context 增加了销售合同路由 |
| `dealEscrowDTO` | ✅ | ✅ | 存管账户信息，逻辑一致 |
| `dealStandardDesignAmountDTO` | ✅ | ✅ | 标准设计费，逻辑一致 |
| `dealMultiCompanyInfo` | ✅ | ✅ | 存管合同主体，逻辑一致 |
| 设计费报价合并（beforeHandle 末尾） | ✅ | ❌ | Context 独有：正式套餐合同从报价合并设计费信息 |

**核心差异**：ContextAspect 侧重**数据校验和清洗**（确保提交数据合法、一致），DetailAspect 侧重**数据聚合和展示**（查询并格式化展示数据）。两者的共享数据准备方法（报价、图纸、套餐等）保持逻辑一致，体现了**查询-提交的对称设计**。