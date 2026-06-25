# ContractDetailAspect 代码分析

## 类概述

这是一个 Spring AOP 切面类，挂在 `@ContractDetailDataPrepare` 注解上，负责在合同详情查询前**并行准备**各类数据到 `ContractDetailContext`（ThreadLocal）。采用"首屏/非首屏"分级加载策略，首屏只加载轻量数据，非首屏才加载报价、套餐、款项等重数据。

---

## 1. `beforeHandle(JoinPoint joinPoint)`

**方法签名：**
```java
@Before("pointCut()")
public void beforeHandle(JoinPoint joinPoint)
```

**职责：** 核心编排方法，从方法参数中解析入参，并行调度各个数据准备任务。

**入参解析（从 JoinPoint 参数数组提取）：**

| 参数位置 | 变量名 | 类型 | 说明 |
|---------|--------|------|------|
| args[1] | `projectOrderId` | String | 项目单号 |
| args[2] | `contractType` | Byte | 合同类型 |
| args[3] | `changeOrderId` | String | 变更单号（可为空） |
| args[4] | `isFirstScreen` | boolean | 是否首屏 |
| args[5] | `billCodeInfoList` | List\<BillCodeInfo\> | 账单编码信息 |
| args[6] | `subOrderInfoList` | List\<SubOrderInfo\> | 子单信息 |
| args[7] | `changeOrderInfoList` | List\<ChangeOrderInfo\> | 变更单信息 |

**数据准备调用链：**

1. `commonBusinessService.isPROCESS_V2_5(projectOrderId, contractType)` → 判断是否 V2.5 流程
2. `commonBusinessService.getBusinessType(projectOrderId)` → 获取业务类型
3. `commonBusinessService.obtainProjectRelationId(projectOrderId)` → 获取关联项目单号（用于协同场景下单号转换）

**输出到 Context 的字段：**

| 字段 | 来源 |
|------|------|
| `processV25` | `commonBusinessService.isPROCESS_V2_5()` |
| `businessType` | `commonBusinessService.getBusinessType()` |
| `firstScreen` | 方法入参 `isFirstScreen` |

**并行任务调度：**

| 任务 | 首屏加载 | 非首屏加载 | 调用方法 |
|------|---------|-----------|---------|
| 项目信息 | ✅ | ✅ | `dealProjectInfo()` |
| 备件信息 | ✅ | ✅ | `dealAttachInfo()` |
| 设计费金额 | ✅ | ✅ | `dealStandardDesignAmountDTO()` |
| 报价信息 | ❌ | ✅ | `dealPlanAllDTO()` |
| 套餐信息 | ❌ | ✅ | `dealComboInfo()` |
| 款项实收 | ❌ | ✅ | `dealRelateFundInfo()` |
| 图纸信息 | ❌ | ✅ | `dealDrawingDTO()` |
| 风控审核 | ❌ | ✅ | `dealAuditInfo()` |

---

## 2. `afterHandle()` / `afterThrowing()`

**方法签名：**
```java
@After("pointCut()")
public void afterHandle()

@AfterThrowing("pointCut()")
public void afterThrowing()
```

**职责：** 清除 ThreadLocal 中的 `ContractDetailContext`，防止线程复用导致数据泄露。无论正常结束还是异常抛出都会执行。

---

## 3. `dealProjectInfo(String projectOrderId, ContractDetailContext context)`

**方法签名：**
```java
private void dealProjectInfo(String projectOrderId, ContractDetailContext context)
```

**职责：** 获取项目基础信息，作为后续所有数据准备的基础依赖。

**数据来源：**

| 调用 | 入参 | 返回 |
|------|------|------|
| `projectInfoReadService.getByProjectOrderId(projectOrderId)` | 项目单号（经过 `obtainProjectRelationId` 转换后） | `ProjectInfoDTO` |

**输出到 Context 的字段：**

| 字段 | 说明 |
|------|------|
| `projectInfoDTO` | 项目信息（含客户信息、分公司编码等） |

**条件分支 / 校验：**

- `projectInfo == null` → 抛出 `UtopiaBussinessException("获取项目信息失败")`
- `customerCommission.companyCode` 为空 → 抛出 `UtopiaBussinessException("项目缺少分公司信息")`

---

## 4. `dealPlanAllDTO(...)` — 报价信息准备

**方法签名：**
```java
private void dealPlanAllDTO(Byte contractType, String projectOrderId, String changeOrderId,
    List<BillCodeInfo> billCodeInfoList, ContractDetailContext context,
    List<SubOrderInfo> subOrderInfoList, List<ChangeOrderInfo> changeOrderInfoList)
```

**职责：** 根据合同类型和业务场景，从不同来源获取报价信息，是逻辑最复杂的方法。

**前置条件判断：**

1. `planAllContractTypes` 不包含当前 `contractType` → 直接返回
   - 适用类型：`ADVANCE`（预签）、`PACKAGE_FORMAL`（套餐正签）、`PACKAGE_CHANGE`（套餐变更）、`DRAWING`（图纸）、`PERSONAL`（个性）
2. 翻新全案 + 预签合同（`REFORM_ALL` + `ADVANCE`）→ 直接返回（报价由页面上传，不从中控获取）

**条件分支详解：**

### 分支 1：预签合同（`ADVANCE`）

| 调用 | 入参 | 返回 |
|------|------|------|
| `contractDetailService.getAdvanceQuote(projectOrderId, billCodeList)` | 项目单号 + 去重后的账单编码列表 | `LightQuotationItem` |

**输出：** `context.preQuotationDTO`

### 分支 2：个性合同（`PERSONAL`）

| 调用 | 入参 | 返回 |
|------|------|------|
| `contractDependentDataService.queryPersonalQuoteInfoV2(bindOrderInfo)` | 组装的绑定订单信息 | `List<PersonalContractData>` |

**输出：** `context.contractSourceDataBO`（包含 `personalContractDataList`）

### 分支 3：V2.5 协同模式 + 有变更单（`changeOrderId` 非空 + `houseProcessV25` 为 true）

**数据来源：**

| 调用 | 说明 |
|------|------|
| `commonBusinessService.getCoordinationProjectOrder(projectOrderId)` | 获取协同项目信息 |
| `changeContractUnifyService.getQuoteBillDiff(projectOrderId, changeOrderId)` | 获取报价变更差异 |
| `atomChangeRpc.getChangeApplyInfo(changeOrderId)` | 获取变更申请信息（含变更范围列表） |
| `homeOrderDataConversionService.changeHardDecorationFileData(changeOrderId)` | 获取变更硬装文件（仅范围含报价时） |
| `drawingRpc.getBaseChangeDrawing(projectOrderId, changeOrderId)` | 获取变更基础图纸（仅范围含图纸时） |
| `changeContractUnifyService.atomChangeQuotationConvertToPlanAllDTO()` | 转换为 PlanAllDTO |

**输出：** `context.planAllDTO`、`context.contractSourceDataBO`、`context.drawingUrl`（条件性）、`context.atomChangeScopeList`

**变更范围子分支：**

- `changeScopeList` 包含 `QUOTATION`（报价变更）→ 使用变更后报价 + 获取硬装文件
- `changeScopeList` 不包含 `QUOTATION` → 使用变更前报价
- `changeScopeList` 包含 `DRAWING`（图纸变更）→ 额外设置 `drawingUrl`

### 分支 4：通用场景（其他所有情况）

| 调用 | 入参 | 返回 |
|------|------|------|
| `homeOrderDataConversionService.contractSourceDate(projectOrderId, changeOrderId)` | 项目单号、变更单号 | `ContractSourceDataBO` |
| `contractDependentDataService.buildPersonalContractData(...)` | sourceData、项目单号、账单、子单信息 | `List<PersonalContractData>` |

**输出：**
- `context.planAllDTO`
- `context.contractSourceDataBO`（含正签对应的 C 报价信息）

**额外逻辑（仅套餐正签 `PACKAGE_FORMAL` + 设计费信息存在时）：**

根据 `DesignFeeInfo` 构建 `DesignQuoteFeeDTO`：
- `haveDesignQuote`：判断设计费来源是否为"报价"且折后金额不为零
- `preDiscountDesignerAmount`：折前设计费
- `afterDiscountDesignerAmount`：折后设计费
- `houseBuildType`：户型
- `valuationArea`：设计计价面积
- `psLevelName`：设计师职级

---

## 5. `dealComboInfo(...)` — 套餐信息准备

**方法签名：**
```java
private void dealComboInfo(Byte contractType, String projectOrderId, String changeOrderId, ContractDetailContext context)
```

**职责：** 获取合同关联的套餐信息（正签套餐或变更套餐）。

**前置条件判断：**

1. `contractType` 不在 `[PACKAGE_FORMAL, PACKAGE_CHANGE]` → 直接返回
2. `commonContractService.querySnapPlanInfoFromMainOrder(businessType, processV25)` 返回 false → 直接返回

**数据来源（变更场景，`changeOrderId` 非空）：**

| 调用 | 说明 |
|------|------|
| `atomChangeRpc.getChangeApplyInfo(changeOrderId)` | 获取变更申请（含变更范围列表） |
| `orderStandardQueryRpc.homeStandardOutput(projectOrderId, moduleParams)` | 查询变更套餐，参数：`projectChangeNo=changeOrderId`，模块 `COST_CONTROL_BUDGET_STANDARD_CHANGE_COMBO` |

**输出：** `context.comboDTOList`

**条件分支（变更场景）：**

- `changeScopeList` 包含 `QUOTATION` → 使用**变更后**套餐列表（`afterChangeComboList`）
- `changeScopeList` 不包含 `QUOTATION` → 使用**变更前**套餐列表（`beforeChangeComboList`）

**数据来源（正签场景）：**

| 调用 | 说明 |
|------|------|
| `orderStandardQueryRpc.homeStandardOutput(projectOrderId, moduleParams)` | 查询正签套餐，参数：`homeOrderNo=projectOrderId`、`comboTypeList=1`、`previewTimeCode=1`，模块 `COST_CONTROL_BUDGET_STANDARD_COMBO` |

---

## 6. `buildAtomChangeQuotation(...)` — 变更报价构建

**方法签名：**
```java
private PlanAllDTO buildAtomChangeQuotation(String changeOrderId, String projectOrderId, ContractDetailContext context)
```

**职责：** 为 V2.5 协同变更场景构建报价数据，被 `dealPlanAllDTO` 的分支 3 调用。

**数据来源：**

| 调用 | 返回 |
|------|------|
| `atomChangeRpc.getChangeApplyInfo(changeOrderId)` | `ChangeApplyInfoDTO`（含 `changeScopeList`） |
| `commonBusinessService.getCoordinationProjectOrder(projectOrderId)` | `CoordinationProjectInfo` |
| `changeContractUnifyService.getQuoteBillDiff(projectOrderId, changeOrderId)` | `QuoteChangeDiffBO` |
| `homeOrderDataConversionService.changeHardDecorationFileData(changeOrderId)` | `PlanAttachmentDTO`（条件性） |
| `drawingRpc.getBaseChangeDrawing(projectOrderId, changeOrderId)` | 图纸 URL（条件性） |

**输出到 Context 的字段：**

| 字段 | 条件 |
|------|------|
| `drawingUrl` | `changeScopeList` 包含 `DRAWING` |
| `atomChangeScopeList` | 始终设置 |

**返回值：** 转换后的 `PlanAllDTO`

---

## 7. `dealRelateFundInfo(...)` — 款项信息准备

**方法签名：**
```java
private void dealRelateFundInfo(String projectOrderId, Byte contractType, ContractDetailContext context)
```

**职责：** 获取合同类型对应的关联款项实收信息。

**数据来源：**

| 调用 | 入参 | 返回 |
|------|------|------|
| `FundRelateContractMapping.obtainFundTypeByContractType(contractType)` | 合同类型编码 | 款项类型（可能为 null） |
| `fundInfoService.getFundByOrderIdAndFundType(projectOrderId, relateFundType)` | 项目单号 + 款项类型 | `FundInfo` |

**输出：** `context.relateFundInfo`

**条件分支：** 若 `relateFundType` 为 null（即该合同类型无关联款项映射），直接返回。

---

## 8. `dealAuditInfo(...)` — 风控审核信息准备

**方法签名：**
```java
private void dealAuditInfo(String projectOrderId, Byte contractType, ContractDetailContext context)
```

**职责：** 获取合并发起正签合同的风控审核信息和变更单列表。

**前置条件判断（全部满足才继续）：**

1. `contractType` 必须为 `PACKAGE_FORMAL`（套餐正签）
2. 必须存在一份状态为 `FINISH` 的最新合同
3. 必须为 V2.5 流程 **且** 业务类型在 `getHouseCertificate25ModeList()` 内

**数据来源：**

| 调用 | 入参 | 返回 |
|------|------|------|
| `contractService.getLatestContractByStatus(projectOrderId, contractType, [FINISH])` | 项目单号 + 合同类型 + 状态列表 | `Contract` |
| `commonBusinessService.getCoordinationProjectOrder(projectOrderId)` | 项目单号 | `CoordinationProjectInfo` |
| `auditRpc.getAuditInfo(coordinationProjectOrderId)` | 协同项目单号 | `AuditDetailDto` |
| `atomChangeRpc.getChangeList(coordinationProjectOrderId)` | 协同项目单号 | `List<ChangeListDTO>` |

**输出：**

| 字段 | 说明 |
|------|------|
| `auditDetailDTO` | 风控审核详情 |
| `changeOrderList` | 变更单列表 |

**异常处理：** 整个获取逻辑被 try-catch 包裹，失败仅记日志，不影响合同详情主流程（降级为不展示审核信息）。

---

## 9. `dealAttachInfo(...)` — 备件信息准备

**方法签名：**
```java
private void dealAttachInfo(String projectOrderId, Byte contractType, ContractDetailContext context)
```

**职责：** 获取项目备件（附件）详情。

**前置条件：** `contractType` 必须为 `PACKAGE_FORMAL`（套餐正签）

**数据来源：**

| 调用 | 入参 | 返回 |
|------|------|------|
| `attachCommonService.getProjectAttachInfoDetail(projectOrderId, false)` | 项目单号、false（非归档） | `AttachInfoDetail` |

**输出：** `context.attachInfoDetail`

---

## 10. `dealStandardDesignAmountDTO(...)` — 设计服务费金额准备

**方法签名：**
```java
private void dealStandardDesignAmountDTO(String projectOrderId, Byte contractType, ContractDetailContext context)
```

**职责：** 获取设计合同对应的设计师信息和标准设计服务费金额。

**前置条件判断：**

1. `contractType` 必须为 `DESIGN`（设计合同）
2. `contractUnifyService.designFeeCalculateIsOpen(projectOrderId)` 为 false（全国设计费计算未开城）
3. 项目所在城市的 `gbCode` 必须在 `contractApolloConfig.getStandardDesignFeeCityCodes()` 配置列表内

**数据来源：**

| 调用 | 说明 | 条件 |
|------|------|------|
| `contractUnifyService.designFeeCalculateIsOpen(projectOrderId)` | 判断设计费计算是否开城 | 始终 |
| `projectInfoReadService.getByProjectOrderId(projectOrderId)` | 获取项目信息（含 gbCode） | 始终 |
| `contractService.getContractInfo(projectOrderId, DESIGN)` | 获取最新设计合同 | 始终 |
| `baseAuditChannel.queryProjectDesignerUcId(projectOrderId)` | 查询设计师 UC ID | 合同不存在或为草稿 |
| `ceresRpc.getPersonInfo(designerUcId)` | 查询设计师人员信息 | 同上 |
| `contractFieldService.getByContractCodeAndKey(contractCode, "area")` | 获取合同扩展字段中的面积 | 合同存在时 |
| `quotationFeignService.getDesignFeeConfig(psLevelName, area)` | 根据职级+面积查询标准设计费 | 面积字段非空时 |

**输出：** `context.designSignPriceInfo`（`DesignSignPriceInfo` 对象）

| 子字段 | 来源 |
|--------|------|
| `standardDesignFeeAmount` | `quotationFeignService.getDesignFeeConfig()` 的 `designFee`（可能为 null） |
| `designerUcId` | `baseAuditChannel.queryProjectDesignerUcId()` |
| `designerUserCode` | `ceresRpc.getPersonInfo().getUserCode()` |
| `designerName` | `ceresRpc.getPersonInfo().getName()` |
| `psLevelName` | `ceresRpc.getPersonInfo().getPsLevelName()` |

**条件分支：**

- 合同已存在且非草稿状态 → 不设置 `designSignPriceInfo`（已有合同数据，不需要标准设计费）
- 合同不存在或为草稿 → 需要查设计师信息和标准设计费

---

## 11. `dealDrawingDTO(...)` — 图纸信息准备

**方法签名：**
```java
private void dealDrawingDTO(String projectOrderId, Byte contractType, String changeOrderId,
    List<BillCodeInfo> billCodeInfoList, ContractDetailContext context,
    List<SubOrderInfo> subOrderInfoList, List<ChangeOrderInfo> changeOrderInfoList)
```

**职责：** 获取合同关联的图纸交付信息。

**前置条件：** `contractType` 必须在 `[PACKAGE_FORMAL, PERSONAL]` 内

**条件分支：**

### 分支 1：个性合同（`PERSONAL`）

| 调用 | 说明 |
|------|------|
| `BindOrderInfo.convert(...)` | 组装绑定订单信息 |
| `contractSigningSourceRouter.route(bindType).buildPersonalDrawing(bindOrderInfo, null, false)` | 根据绑定类型路由到对应实现获取图纸 |

**输出：** `context.drawingDTO`

### 分支 2：团装正签（`processV25 && GROUP_DECORATE && PACKAGE_FORMAL`）

| 调用 | 说明 |
|------|------|
| `contractBusinessService.getGroupDrawingDTO(projectOrderId)` | 获取团装图纸信息 |

**输出：** `context.drawingDTO`

---

## 调用链总览

```
beforeHandle
├── commonBusinessService.isPROCESS_V2_5()        → context.processV25
├── commonBusinessService.getBusinessType()        → context.businessType
├── [并行] dealProjectInfo                         → context.projectInfoDTO
├── [并行] dealAttachInfo                          → context.attachInfoDetail
├── [并行] dealStandardDesignAmountDTO             → context.designSignPriceInfo
└── [非首屏并行]
    ├── dealPlanAllDTO                             → context.preQuotationDTO / planAllDTO / contractSourceDataBO / designQuoteFeeDTO / drawingUrl / atomChangeScopeList
    │   ├── (ADVANCE) contractDetailService.getAdvanceQuote
    │   ├── (PERSONAL) contractDependentDataService.queryPersonalQuoteInfoV2
    │   ├── (V2.5变更) buildAtomChangeQuotation
    │   │   ├── atomChangeRpc.getChangeApplyInfo
    │   │   ├── changeContractUnifyService.getQuoteBillDiff
    │   │   ├── drawingRpc.getBaseChangeDrawing (条件)
    │   │   └── homeOrderDataConversionService.changeHardDecorationFileData (条件)
    │   └── (通用) homeOrderDataConversionService.contractSourceDate
    ├── dealComboInfo                              → context.comboDTOList
    │   ├── (正签) orderStandardQueryRpc.homeStandardOutput (COMBO)
    │   └── (变更) orderStandardQueryRpc.homeStandardOutput (CHANGE_COMBO)
    ├── dealRelateFundInfo                         → context.relateFundInfo
    ├── dealDrawingDTO                             → context.drawingDTO
    │   ├── (PERSONAL) contractSigningSourceRouter.route().buildPersonalDrawing
    │   └── (团装) contractBusinessService.getGroupDrawingDTO
    └── dealAuditInfo                              → context.auditDetailDTO / changeOrderList
        ├── auditRpc.getAuditInfo
        └── atomChangeRpc.getChangeList
```

## 合同类型 × 数据准备矩阵

| 数据项 | ADVANCE | PACKAGE_FORMAL | PACKAGE_CHANGE | DRAWING | PERSONAL | DESIGN |
|--------|---------|---------------|----------------|---------|----------|--------|
| 项目信息 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 备件信息 | - | ✅ | - | - | - | - |
| 设计费金额 | - | - | - | - | - | ✅ |
| 报价信息 | ✅ | ✅ | ✅ | ✅ | ✅ | - |
| 套餐信息 | - | ✅ | ✅ | - | - | - |
| 款项实收 | ✅ | ✅ | ✅ | ✅ | ✅ | - |
| 图纸信息 | - | ✅* | - | - | ✅ | - |
| 风控审核 | - | ✅** | - | - | - | - |

> \* 图纸信息仅在 V2.5 + 团装 + 正签时加载
> \*\* 风控审核仅在 V2.5 + 房产证模式 + 存在已完结合同时加载