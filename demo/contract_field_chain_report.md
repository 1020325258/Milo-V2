# 合同系统字段取值链路全景图

---

## 一、数据流向总架构

```
┌─────────────┐    HTTP Request     ┌─────────────────────┐
│   前端页面    │ ──────────────────→ │   Controller 层      │
└─────────────┘                     └─────────┬───────────┘
                                              │
                    ┌─────────────────────────┼──────────────────────────┐
                    │  ① 详情查询链路          │  ② 提交链路              │  ③ PDF 生成链路
                    ▼                         ▼                          ▼
          ┌──────────────────┐    ┌──────────────────────┐   ┌───────────────────────┐
          │ ContractDetail    │    │ ContractContext       │   │ ContractPdfBuild      │
          │ Aspect            │    │ Aspect                │   │ Service               │
          │ (@Before)         │    │ (@Before)             │   │ (反射调用)              │
          │                  │    │                       │   │                       │
          │ 并行加载数据到     │    │ 并行加载数据到         │   │ 从 ThreadLocal 读取    │
          │ DetailContext     │    │ ContractContext       │   │ Context 数据，计算     │
          │ (ThreadLocal)     │    │ (ThreadLocal)         │   │ PDF 模板字段           │
          └──────────────────┘    └──────────────────────┘   └───────────────────────┘
                    │                         │                          │
                    ▼                         ▼                          ▼
          ┌──────────────────────────────────────────────────────────────────────┐
          │                    外部依赖层                                         │
          │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐  │
          │  │ RPC 调用  │ │ Service  │ │ Apollo   │ │ 数据库    │ │ 加密服务  │  │
          │  │ atomChange│ │ project  │ │ 配置中心  │ │ contract │ │ cipher   │  │
          │  │ audit     │ │ fundInfo │ │          │ │ project  │ │          │  │
          │  │ quotation │ │ combo    │ │          │ │          │ │          │  │
          │  │ drawing   │ │ escrow   │ │          │ │          │ │          │  │
          │  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘  │
          └──────────────────────────────────────────────────────────────────────┘
```

**数据流转时序：**

| 阶段 | 触发时机 | 核心动作 | 数据去向 |
|------|---------|---------|---------|
| ① DetailAspect | 详情查询接口被调用 | `@Before` 并行准备详情数据 | `ContractDetailContext` (ThreadLocal) |
| ② ContextAspect | 合同提交接口被调用 | `@Before` 并行准备提交数据 + 参数清洗 | `ContractContext` (ThreadLocal) |
| ③ PdfBuildService | 合同生成/预览时 | 通过反射调用各 `getXxx()` 方法 | 返回 `Map<String, Object>` → PDF 模板引擎 |

---

## 二、按业务维度的字段取值链路

### 2.1 房屋 / 项目信息

| 前端/模板字段 | PdfBuildService 方法 | Context 数据来源 | ContextAspect 准备 | DetailAspect 准备 | 外部依赖 |
|---|---|---|---|---|---|
| `projectOrderId` | `getProjectOrderId()` | `context.contract.projectOrderId` | 从请求参数写入 | 从请求参数写入 | — |
| `projectContractAddress` / `wanLianGongChengShiGongDiZhi` | `getProjectContractAddress()` / `getProjectContractAddressV2()` | `contractReq.projectInfo.queryCertificateAddress()` | 前端传入，经 `preHandleProjectParam()` 默认值处理 | `dealProjectInfo()` → `ProjectInfoReadService.getByProjectOrderId()` | `ProjectInfoReadService` (RPC) |
| `floorName` | `getFloorName()` | `contractReq.projectInfo.floorName` | 前端传入 | 同上 | — |
| `structure` | `getStructureInfo()` | `contractReq.projectInfo.structureCode` → `StructureEnum` | 前端传入 | 同上 | `StructureEnum` 枚举 |
| `roomCnt/parlorCnt/cookroomCnt/toiletCnt/balconyCnt` | `getStructureInfo()` | `contractReq.projectInfo.*Cnt` | 前端传入 | 同上 | — |
| `area` / `wanLianZhuangXiuGongChengMianJi` | `getArea()` / `getAreaV2()` | `contractReq.projectInfo.area` / `planAllDTO.planInfo.pricingArea` | 前端传入（面积）；报价获取（计价面积） | `dealPlanAllDTO()` → `HomeOrderDataConversionService.contractSourceDate()` | `HomeOrderDataConversionService` (Service) |
| `houseType` | `getHouseType()` | `contractReq.projectInfo.houseType` → `HouseTypeEnum` | 前端传入 | 同上 | `HouseTypeEnum` 枚举 |
| `planOpenDate` / `wanLianYuJiKaiGongRiQi` | `getPlanOpenDate()` / `getPlanOpenDateV2()` | `contractReq.projectInfo.planStartTime` | 前端传入 | 同上 | — |
| `projectDay` / `wanLianGongChengQiXian` | `getProjectDay()` / `getProjectDayV2()` | `contractReq.projectInfo.totalDuration` / `TotalDurationEnum` + Apollo 配置 | 前端传入 | 同上 | `ContractApolloConfig` (Apollo) |
| `wanLianGongChengHuXing` | `getHuXingV2()` | `contractReq.projectInfo.*Cnt` 拼接 | 前端传入 | — | — |

**面积取值条件分支：**

```
面积字段取值路径
├── 首期款合同(6)
│   ├── 支持预报价 → quotation.pricingArea
│   └── 不支持 → 城市配置判断
│       ├── VALUATION_AREA → projectInfo.valuationArea
│       └── 其他 → projectInfo.area
│
├── 设计合同(2)
│   ├── valuationArea 非空 → 取 valuationArea
│   └── valuationArea 为空 → fallback 到 area
│
└── 正签合同(3) / 变更(4) / 图纸(7)
    ├── gbCode 在建筑面积城市列表 → planAllDTO.planInfo.area
    └── 其他 → planAllDTO.planInfo.pricingArea
```

---

### 2.2 签约人（甲方）信息

| 前端/模板字段 | PdfBuildService 方法 | Context 数据来源 | ContextAspect 准备 | DetailAspect 准备 | 外部依赖 |
|---|---|---|---|---|---|
| `jiafangXingming` / `wangLianJiaFangXingMing` | `getSignUserInfo()` / `getSignUserInfoV2()` | `contractReq.signInfo.customerName` / `signInfo.wanLianJiaFangXingMing` | `preHandleSignInfoParam()` 清洗：个人→业主名；公司→公司名 | 前端直传到详情查询入参 | — |
| `firstPartyConnectPhone` / `wanLianJiaFangLianXiFangShi` | `getSignUserInfo()` / `getSignUserInfoV2()` | `contractReq.signInfo.customerPhone` | 前端传入，`cipherService.decrypt()` 解密 | 同上 | `CipherService` (加解密) |
| `customerIdNo` / `wanLianJiaFangShenFenZhengHao` | `getSignUserInfo()` / `getSignUserInfoV2()` | `contractReq.signInfo.customerIdNo` | 前端传入，解密；公对公→信用代码替代 | 同上 | `CipherService` |
| `wangLianJiaFangZhengJianLeiXing` | `getSignUserInfoV2()` | `contractReq.signInfo.certificateType` | 前端传入 | — | — |
| `ownerAddress` / `wanLianJiaFangLianXiDiZhi` | `getSignUserInfo()` / `getSignUserInfoV2()` / `getFirstPartAddressInfo()` | 个人→`signInfo.address`；公司→`signInfo.companyAddress` | `preHandleSignInfoParam()` 根据签约形式保留对应地址 | — | — |

**代理人信息：**

| 模板字段 | PdfBuildService 方法 | 取值条件 |
|---|---|---|
| `agentName` / `wanLianWeiTuoDaiLiRenXingMing` | `getSignUserInfo()` / `getAgentUserInfo()` | `haveAgent=YES` → 取代理人姓名；`NO` → "/" |
| `agentIdNo` / `wanLianWeiTuoDaiLiRenShenFenZhengHao` | `getSignUserInfo()` / `getAgentUserInfo()` | 同上，解密后输出 |
| `agentPhone` / `wanLianWeiTuoDaiLiRenLianXiDianHua` | `getSignUserInfo()` / `getAgentUserInfo()` | 同上，解密后输出 |
| `agentIdNoType` / `WeiTuoDaiLiRenZhengJianLeiXing` | `getAgentUserInfo()` | 代理人存在时取证件类型 |

**签约形式分支处理（ContextAspect `preHandleSignInfoParam`）：**

```
签约形式判断
├── PERSON（个人签约）
│   ├── 清空公对公字段（公司名、信用代码、法人、营业执照）
│   ├── haveAgent=YES → 保留代理人字段
│   ├── haveAgent=NO → 清空代理人全部信息
│   └── C端授权 + 有代理人 → agentSign 强制 YES
│
└── COMPANY（公对公签约）
    ├── 清空个人签约字段（业主姓名、手机、身份证、个人代理人）
    ├── 法人签约 + 非授权协议 → 额外清空公司代理人
    └── COMPANY_AGENT 角色 → 取公司经办人信息作为代理人
```

**实际签约人（`getSignatoryUserInfo()`）角色分支：**

```
signatoryRoleType
├── OWNER        → 取业主信息
├── AGENT        → 取个人代理人信息
├── COMPANY_AGENT → 取公司经办人信息
└── LEGAL        → 取法定代表人信息
```

---

### 2.3 合同主体（乙方）信息

| 模板字段 | PdfBuildService 方法 | Context 数据来源 | ContextAspect 准备 | DetailAspect 准备 | 外部依赖 |
|---|---|---|---|---|---|
| `companyCode` | `getCompanyInfo()` | `context.contractCityCompanyInfo` / `signInfo.signCompanyCode` | `dealMultiCompanyInfo()` + 城市分公司配置 | `dealProjectInfo()` → 分公司编码 | `CommonContractService.getCompanyInfo()` (Service) |
| `companyName` | `getCompanyInfo()` | 同上 → `companyInfo.companyName` | 同上 | 同上 | `MdmDataRpc` / `MdmRpc` (RPC) |
| `companyAddress` | `getCompanyInfo()` | 同上 → `companyInfo.companyAddress` | 同上 | 同上 | 同上 |
| `companyPhone` | `getCompanyInfo()` | 同上 | 同上 | 同上 | 同上 |
| `companySealCode` / `companySealCode` | `getCompanyInfo()` / `getCompanyInfoV2()` | 同上 / `signInfo.companyCreditCode` | 同上 | 同上 | 同上 |
| `companyBank` / `companyAccount` | `getCompanyInfo()` | 同上 | 同上 | 同上 | 同上 |
| `salesCompanyName` | `getSecondPartyCompanyInfo()` | `signInfo.signCompanyCode` → `contractCompanyInfoService.getByCompanyCode()` | — | — | `ContractCompanyInfoService` (Service) |

**公司编码取值分支（PdfBuildService `getCompanyInfo()`）：**

```
companyCode 来源
├── 个性化合同(8) → signInfo.signCompanyCode（签约公司）
├── 个人合同 / 资金存管合同(20) → contract.companyCode
└── 其他 → context.contractCityCompanyInfo（城市分公司配置）
```

**多主体信息（资金存管协议 20）：**

| 阶段 | 数据来源 | 说明 |
|---|---|---|
| ContextAspect `dealMultiCompanyInfo()` | `FundEscrowService.getFundEscrowEntryInfoByProjectOrderId()` → `EscrowRpc.queryFundEscrowAccountBasicInfo()` → `MdmDataRpc.getInfoByMerchantNos()` | 获取整装 + 零售两个分公司信息 |
| DetailAspect | 同上 | 逻辑一致 |
| PdfBuildService `getMultiCompanyInfo()` | 遍历 `context.contractCompanyList`，第N个主体 key 加 `N` 后缀 | 无多主体时 fallback 到 `getCompanyInfo()` |

---

### 2.4 合同金额

| 模板字段 | PdfBuildService 方法 | Context 数据来源 | ContextAspect 准备 | DetailAspect 准备 | 外部依赖 |
|---|---|---|---|---|---|
| `contractAmount` / `wanLianGongChengKuanDaXie` | `getContractAmount()` / `getContractAmountV2()` | 套餐正签→`planAllDTO.planInfo.contractPriceTotal`；其他→`projectInfo.amount` | `dealPlanAllDTO()` 获取报价 | `dealPlanAllDTO()` 获取报价 | `HomeOrderDataConversionService` (Service) |
| `contractAmountText` | `getContractAmount()` | 金额 → `MoneyConvertUtil.convert()` 大写 | 同上 | 同上 | `MoneyConvertUtil` (工具) |
| `planDeveloperTotalPrice` | `getContractAmount()` | `planAllDTO.planInfo` 供应商承担金额 | 仅套餐正签(3) | 仅套餐正签(3) | 同上 |
| `planDeveloperAndClientTotalPrice` | `getContractAmount()` | 供应商+客户承担总额 | 同上 | 同上 | 同上 |
| `advanceAmount` / `expectContractAmount` | `getContractAdvanceAmount()` | 支持预报价→`quotation`；不支持→`projectInfo` | `dealAdvancePreQuotation()` 校验 | `dealPlanAllDTO()` | `AtomBudgetRpc` (RPC) |
| `advanceToBAmount` / `advanceToBCAmount` | `getContractAdvanceAmount()` | B支付金额 + 预估合同金额 计算 | 同上 | 同上 | 同上 |
| `personalTotalPrice` | `getPersonalContractAmount()` | 首期款→`amountInfo.quoteTotalAmount`；主材→`contract.amount` | 从请求参数 | 从请求参数 | — |
| `quotationTotalAmount` | `getQuotationTotalAmount()` | `planAllDTO.planInfo.quotePrice` | `dealPlanAllDTO()` | `dealPlanAllDTO()` | 同上 |

**合同金额条件分支：**

```
contractAmount 取值
├── PACKAGE_FORMAL(3) / FULL_SERVICE_SUMMARY
│   └── planAllDTO.planInfo.contractPriceTotal
│       └── 额外计算：供应商承担 + 供应商+客户承担
│
├── ADVANCE(6) 首期款
│   ├── 支持预报价 → quotation 中取
│   └── 不支持 → projectInfo.amount
│
└── 其他合同类型
    └── projectInfo.amount
```

---

### 2.5 设计费

| 模板字段 | PdfBuildService 方法 | Context 数据来源 | ContextAspect 准备 | DetailAspect 准备 | 外部依赖 |
|---|---|---|---|---|---|
| `designerName` | `getDesignerName()` | `commonContractService.getDesignerInfo(projectOrderId)` | 远程查询 | 远程查询 | `CommonContractService` (Service) |
| `designerLevel` | `getDesignerLevel()` | `projectInfo.designerLevelName` / `DesignerLevelEnum.getNameByCode()` | 前端传入或枚举转换 | 同上 | `DesignerLevelEnum` (枚举) |
| `preDiscountDesignerAmount` | `getPreDiscountDesignerAmount()` | `projectInfo.preDiscountDesignerAmount` | 前端传入 | 同上 | — |
| `preDiscountDesignerAmountText` | `getPreDiscountDesignerAmount()` | 金额→`MoneyConvertUtil.convert()` | 同上 | 同上 | `MoneyConvertUtil` |
| `afterDiscountDesignerAmount` | `getAfterDiscountDesignerAmount()` | `projectInfo.afterDiscountDesignerAmount` | `preHandleParam()` 中 `needDesignerAmount=NO` 时清空 | — | — |
| `designContractAmountInfo` | `getDesignContractAmountInfo()` | 内部组合 `designerLevel` + `preDiscount` + `afterDiscount` | — | — | — |

**标准设计费准备链路（仅设计合同 DESIGN(2)）：**

```
ContextAspect dealStandardDesignAmountDTO():
  contractType == DESIGN
  && !designFeeCalculateIsOpen()（全国未开城）
  && gbCode ∈ standardDesignFeeCityCodes（Apollo 配置）
  && area 非空
      │
      ├── contractService.getContractInfo(projectOrderId, DESIGN)
      │   ├── 合同存在且非草稿 → 不设置标准设计费（已有数据）
      │   └── 合同不存在或草稿
      │       ├── baseAuditChannel.queryProjectDesignerUcId() → designerUcId
      │       ├── ceresRpc.getPersonInfo(designerUcId) → 姓名/职级/工号
      │       └── quotationFeignService.getDesignFeeConfig(psLevelName, area) → 标准设计费
      │
      └── 输出：context.designSignPriceInfo
          ├── standardDesignFeeAmount
          ├── designerUcId
          ├── designerUserCode
          ├── designerName
          └── psLevelName
```

**设计费报价合并（ContextAspect 独有，`beforeHandle` 末尾串行）：**

```
PACKAGE_FORMAL(3) + planAllDTO 中有 DesignFeeInfo
  │
  ├── haveDesignQuote = (来源=="报价" && 折后金额≠0)
  ├── preDiscountDesignerAmount ← DesignFeeInfo 折前金额
  ├── afterDiscountDesignerAmount ← DesignFeeInfo 折后金额
  ├── houseBuildType ← 户型
  ├── valuationArea ← 设计计价面积
  └── psLevelName ← 设计师职级
      → 输出到 context.designQuoteFeeDTO
```

---

### 2.6 报价信息

| 模板字段 | PdfBuildService 方法 | Context 数据来源 | ContextAspect 准备 | DetailAspect 准备 | 外部依赖 |
|---|---|---|---|---|---|
| `budgetUrl` / `budgetUrlV2` | `getBudgetUrl()` / `getBudgetUrlV2()` | `planAllDTO.planAttachmentList` 筛选"报价单" | `dealPlanAllDTO()` → `contractSourceDate()` | `dealPlanAllDTO()` → `contractSourceDate()` | `HomeOrderDataConversionService` + `PdfToImageService` |
| `couponAmount` | `getCoupon()` | `planAllDTO.couponList` 筛选 `DIRECT_COUPON` | 同上 | 同上 | — |
| `couponRemark` | `getCoupon()` | `contractBusinessService.getCouponRemarkList(planAllDTO)` | 同上 | 同上 | `ContractBusinessService` |

**报价获取分支（两 Aspect 通用）：**

```
dealPlanAllDTO 报价来源判断
│
├── ADVANCE(6) 预签
│   ├── 翻新全案(REFORM_ALL) → 不查报价（页面上传）
│   └── 其他 → contractDetailService.getAdvanceQuote()
│
├── PERSONAL(8) 个性/销售
│   └── contractDependentDataService.queryPersonalQuoteInfoV2()
│       → context.contractSourceDataBO.personalContractDataList
│
├── PACKAGE_CHANGE(4) + V2.5 + 协同 + 有变更单
│   └── buildAtomChangeQuotation()
│       ├── atomChangeRpc.getChangeApplyInfo() → changeScopeList
│       ├── changeContractUnifyService.getQuoteBillDiff()
│       ├── changeScopeList 含 QUOTATION → 用变更后报价 + 获取硬装文件
│       ├── changeScopeList 不含 QUOTATION → 用变更前报价
│       └── changeScopeList 含 DRAWING → 额外设置 drawingUrl
│
└── 通用（PACKAGE_FORMAL/DRAWING 等）
    └── homeOrderDataConversionService.contractSourceDate()
        → context.planAllDTO
        → context.contractSourceDataBO
```

**首期款预估报价校验（ContextAspect 独有 `dealAdvancePreQuotation`）：**

| 校验项 | 前端参数 | RPC 数据 | 不一致时 |
|-------|---------|---------|---------|
| 装修 PDF | — | `decoratePdfFile` 不能为空 | 抛异常 |
| 计价面积 | `requestQuotation.pricingArea` | `rpcQuotation.pricingArea` | 抛异常 |
| 预估合同额 | `requestQuotation.expectContractAmount` | `rpcQuotation.hardTotalPrice` | 抛异常 |
| 套餐编码 | `requestQuotation.comboCode` | `rpcQuotation.comboBaseInfo.comboCode` | 抛异常 |
| 套餐名称 | `requestQuotation.comboName` | `rpcQuotation.comboBaseInfo.comboName` | 抛异常 |

---

### 2.7 套餐信息

| 模板字段 | PdfBuildService 方法 | Context 数据来源 | ContextAspect 准备 | DetailAspect 准备 | 外部依赖 |
|---|---|---|---|---|---|
| `packageName` | `getPackageNameByPackageId()` / `getPackageNameFromPlanAllDTO()` | `planAllDTO.planInfo.comboName` 或 `quotationFeignService.getPackageList()` | `dealComboInfo()` + `dealPlanAllDTO()` | `dealComboInfo()` + `dealPlanAllDTO()` | `OrderStandardQueryRpc` / `QuotationFeignService` (RPC) |

**套餐加载条件（两 Aspect 通用，三重守卫）：**

```
dealComboInfo 执行条件：
  processV25 == true
  && businessType == HOUSE_CERTIFICATE（整装）
  && contractType ∈ [PACKAGE_FORMAL(3), PACKAGE_CHANGE(4)]
      │
      ├── 正签 → orderStandardQueryRpc.homeStandardOutput(
      │          module=COST_CONTROL_BUDGET_STANDARD_COMBO,
      │          homeOrderNo=projectOrderId, comboTypeList=1)
      │
      └── 变更(changeOrderId非空)
          ├── atomChangeRpc.getChangeApplyInfo() → changeScopeList
          ├── orderStandardQueryRpc.homeStandardOutput(
          │     module=COST_CONTROL_BUDGET_STANDARD_CHANGE_COMBO,
          │     projectChangeNo=changeOrderId)
          ├── QUOTATION ∈ changeScopeList → 用 afterChangeComboList
          └── QUOTATION ∉ changeScopeList → 用 beforeChangeComboList
```

---

### 2.8 图纸信息

| 模板字段 | PdfBuildService 方法 | Context 数据来源 | ContextAspect 准备 | DetailAspect 准备 | 外部依赖 |
|---|---|---|---|---|---|
| `baseConstructionDrawUrl` | `getBaseConstructionDrawUrl()` | `planAllDTO.planAttachmentList` 筛选"基础图纸" | `dealPlanAllDTO()` | `dealPlanAllDTO()` | — |
| `drawingUrl` (2.5版，全页盖章) | `getDrawingUrl_2_5()` | `context.drawingDTO` → 筛选基础图纸 PDF | `dealDrawingDTO()` | `dealDrawingDTO()` | `AtomDrawingRpc` (RPC) |
| `drawingUrlV2` (最后页盖章) | `getDrawingUrlV2()` | 同上 | 同上 | 同上 | 同上 |
| `personalDrawing` | `getPersonalDrawing()` | `personalContractDataList` → `contractSigningSourceRouter.route().buildPersonalDrawingImgList()` | `dealDrawingDTO()` | `dealDrawingDTO()` | `ContractSigningSourceRouter` (路由) |
| `materialForB` | `getMaterialForB()` | `context.drawingDTO` 筛选商品清单/软装配置清单 | `dealDrawingDTO()` | `dealDrawingDTO()` | `AtomDrawingRpc` |

**图纸获取分支（两 Aspect 通用）：**

```
dealDrawingDTO 图纸来源判断
│
├── 非图纸相关合同类型 → 返回
│
├── PERSONAL(8) 销售合同
│   └── contractSigningSourceRouter.route(bindType).buildPersonalDrawing()
│
├── PACKAGE_FORMAL(3) + V2.5 + 团装(GROUP_DECORATE)
│   └── contractBusinessService.getGroupDrawingDTO()
│
├── PACKAGE_CHANGE(4) 变更（仅 ContextAspect）
│   └── atomDrawingRpc.getChangeListDrawings()
│
└── 其他（正签/图纸合同）
    └── atomDrawingRpc.listDrawings()
```

---

### 2.9 附件信息

| 模板字段 | PdfBuildService 方法 | Context 数据来源 | ContextAspect 准备 | DetailAspect 准备 | 外部依赖 |
|---|---|---|---|---|---|
| `decorateRuleUrl` / `decorateRuleUrlV2` | `getDecorateRuleUrl()` / `getDecorateRuleUrlV2()` | `commonContractService.getComboCodesByPlanAllDTO()` → `comboInfoService.getDecorateRule()` | `dealPlanAllDTO()` 提供套餐数据 | `dealPlanAllDTO()` 提供套餐数据 | `ComboInfoService` (Service) |
| `budgetRuleUrl` | `getBudgetRuleUrl()` | `comboInfoService.getBudgetDesc()` | 同上 | 同上 | 同上 |
| `materialUrl` | `getMaterialUrl()` | `comboInfoService.getMaterialList()` | 同上 | 同上 | 同上 |
| `internalConfigurationsUrl` | `getInternalConfigurationsUrl()` | `planAllDTO.planAttachmentList` 筛选"套餐套内配置清单" | `dealPlanAllDTO()` | `dealPlanAllDTO()` | — |
| `extraConfigurationsUrl` | `getExtraConfigurationsUrl()` | `planAttachmentList` 筛选"加载配置清单" | 同上 | 同上 | — |
| `personalQuotionUrl` | `getPersonalQuotionUrl()` | V2.5→`getPersonalBudgetUrlV2()`；旧版→`planAttachmentList` 筛选 | 同上 | 同上 | — |
| `servicePromise` | `getServicePromise()` | `getAttachConfig()` → `contractAttachConfigService` | — | — | `ContractAttachConfigService` (Service) |
| `valuationExplanation` | `getValuationExplanation()` | 同上 | — | — | 同上 |
| `personalSignNotification` | `getPersonalSignNotification()` | 同上 | — | — | 同上 |
| `categoryInformation` | `getCategoryInformation()` | 同上 | — | — | 同上 |
| `groupCategoryInformation` | `getGroupCategoryInformation()` | `getAttachConfig(GROUP_CATEGORY_INFORMATION)` | — | — | 同上 |
| `installationAndDelivery` | `getInstallationAndDelivery()` | `getAttachConfig(INSTALLATION_AND_DELIVERY)` | — | — | 同上 |
| `contractCustomAttach` | `getCustomAttach()` | `contractCustomAttachConfigService.getContractCustomAttachWithDefault()` | — | — | `ContractCustomAttachConfigService` (Service) |
| `durationDescAttach` | `getDurationDescriptionAttach()` | `contractAttachConfigService` 获取 `DURATION_DESCRIPTION_ATTACH` | — | — | `ContractAttachConfigService` |

**附件获取通用模式：**

```
getAttachConfig(attachType, contractType):
  contractAttachConfigService 按 gbCode + businessType + companyCode + contractFormType 查询
  ├── 查到配置 → 返回对应附件 URL
  └── 未查到 → 降级到默认配置（不同合同类型的默认策略不同）
```

---

### 2.10 款项信息

| 模板字段 | PdfBuildService 方法 | Context 数据来源 | ContextAspect 准备 | DetailAspect 准备 | 外部依赖 |
|---|---|---|---|---|---|
| `advancePaidAmount` | `getAdvancePaidInfo()` | `fundInfoService.getFundByOrderIdAndFundType()` | — | `dealRelateFundInfo()` | `FundInfoService` (Service) |
| `advanceContractNo` | `getAdvancePaidInfo()` | `contractService.getContractList()` 筛选已签署首期款 | — | — | `ContractService` (Service) |
| `relateFundInfo` | — | `context.relateFundInfo` | — | `dealRelateFundInfo()` | `FundInfoService` |

**款项获取分支（DetailAspect `dealRelateFundInfo`）：**

```
FundRelateContractMapping.obtainFundTypeByContractType(contractType)
├── 返回 null（该合同类型无关联款项）→ 跳过
└── 返回 fundType → fundInfoService.getFundByOrderIdAndFundType(projectOrderId, fundType)
    → context.relateFundInfo
```

---

### 2.11 收款计划

| 模板字段 | PdfBuildService 方法 | Context 数据来源 | 外部依赖 |
|---|---|---|---|
| `payPlan` / `payPlanNew` | `getCollectionPlanInfo()` | `contractReq.collectionPlanConfigInfo.content` + `planAllDTO.planInfo.contractPriceTotal` | — |
| `firstPayAmount` / `firstPayAmountText` | `getCollectionPlanInfo()` | 收款计划第一期 | — |
| `secondPayAmount` / `secondPayAmountText` | `getCollectionPlanInfo()` | 收款计划第二期 | — |
| `thirdPayAmount` / `thirdPayAmountText` | `getCollectionPlanInfo()` | 收款计划第三期 | — |
| `advanceRate` | `getAdvanceRate()` | `projectInfo.advanceRate` / `quotation` / 默认20% | `FundTaskTypeEnum.ADVANCE_COLLECTION_PROGRESS` |
| `percentageOfTotalOrderAmount` / `firstInstallmentAmountByPercentage` | `getPercentageOfTotalOrderAmount()` | `contractApolloConfig.getPercentageConfigByGbCode()` × `contract.amount` | `ContractApolloConfig` (Apollo) |
| `remainingPercentageOfTotalOrderAmount` / `secondInstallmentAmountByRemainingPercentage` | `getRemainingPercentageOfTotalOrderAmount()` | 同上取剩余配置 | 同上 |

---

### 2.12 保修信息

| 模板字段 | PdfBuildService 方法 | Context 数据来源 | 外部依赖 |
|---|---|---|---|
| `waterElectricGuaranteeYear` | `getWaterElectricGuaranteeYear()` | `getContractBusinessConfig()` → Apollo 配置，数字→中文大写 | `ContractApolloConfig` (Apollo) |
| `waterProofGuaranteeYear` | `getWaterProofGuaranteeYear()` | 同上 | 同上 |
| `otherGuaranteeYear` | `getOtherGuaranteeYear()` | 同上 | 同上 |
| `otherGuaranteeYear` / `waterElectricGuaranteeYear` / `waterProofGuaranteeYear`（直接值） | `getGuaranteeInfo()` | `contractReq.guaranteeInfo` | — |

**保修年限配置取值分支：**

```
getContractBusinessConfig():
├── GROUP_DECORATE（团装）
│   └── 团装专用配置按 gbCode 取
│
└── 其他业务类型
    ├── 按 gbCode + 开渠标识查询
    └── 查不到 → 兜底取非开渠配置
```

---

### 2.13 承包约定

| 模板字段 | PdfBuildService 方法 | Context 数据来源 | 外部依赖 |
|---|---|---|---|
| `ProjectContractMode` / `ProjectContractModeName` | `getPromiseInfo()` | `contractReq.promiseInfo.projectContractModeCode` → `ProjectContractModeEnum` | `ProjectContractModeEnum` (枚举) |
| `constructionDrawMode` | `getPromiseInfo()` | `contractReq.promiseInfo.constructionDrawMode` → `ConstructionDrawModeEnum` | `ConstructionDrawModeEnum` (枚举) |
| `openWorkDayToConstruct` | `getPromiseInfo()` | `contractReq.promiseInfo.openWorkDayToConstruct` | — |
| `taxRate` | `getPromiseInfo()` | `contractReq.promiseInfo.taxRate` + "%" | — |
| `disputeDealMode` / `getDisputeDealMode()` | `getPromiseInfo()` / `getDisputeDealMode()` | `contractReq.promiseInfo.disputeDealMode` | — |
| `beforeDeliveryDaysToWork` | `getPromiseInfo()` | `contractReq.promiseInfo.beforeDeliveryDaysToWork` | — |

**承包方式特殊映射：**

```
B_LABOR_PART_MATERIALS_A_PART_MATERIALS_V2 → 映射为 B_LABOR_PART_MATERIALS_A_PART_MATERIALS 的 code
```

---

### 2.14 存管账户信息

| 模板字段 | PdfBuildService 方法 | Context 数据来源 | ContextAspect 准备 | DetailAspect 准备 | 外部依赖 |
|---|---|---|---|---|---|
| `escrowAccountUserName` | `getEscrowAccountInfo()` | `context.escrowInfo.name` | `dealEscrowDTO()` | `dealEscrowDTO()` | `EscrowDomain` (Service) |
| `escrowAccountUserPhone` | `getEscrowAccountInfo()` | `context.escrowInfo.phone` | 同上 | 同上 | 同上 |
| `escrowAccountUserIdNo` | `getEscrowAccountInfo()` | `context.escrowInfo.idNumber` | 同上 | 同上 | 同上 |
| `escrowAccountUserIdType` | `getEscrowAccountInfo()` | `context.escrowInfo.idType` | 同上 | 同上 | 同上 |
| `openAccountTime` | `getEscrowAccountInfo()` | `context.escrowInfo.openAccountTime` | 同上 | 同上 | 同上 |

**存管账户输出条件（PdfBuildService）：**

```
仅当 escrowAccountUserPhone ≠ 签约人手机号时才输出存管账户信息
否则字段不填入 PDF 模板
```

---

### 2.15 风控审核 / 备件信息

| 模板字段 | Context 数据来源 | ContextAspect 准备 | DetailAspect 准备 | 外部依赖 |
|---|---|---|---|---|
| `auditDetailDTO` | `context.auditDetailDTO` | — | `dealAuditInfo()` | `AuditRpc` (RPC) |
| `changeOrderList` | `context.changeOrderList` | — | `dealAuditInfo()` | `AtomChangeRpc` (RPC) |
| `attachInfoDetail` | `context.attachInfoDetail` | — | `dealAttachInfo()` | `AttachCommonService` (Service) |

**风控审核条件（DetailAspect 独有）：**

```
dealAuditInfo 执行条件（全部满足）：
  contractType == PACKAGE_FORMAL(3)
  && 存在状态为 FINISH 的最新合同
  && processV25 == true
  && businessType ∈ getHouseCertificate25ModeList()
      │
      ├── commonBusinessService.getCoordinationProjectOrder()
      ├── auditRpc.getAuditInfo() → context.auditDetailDTO
      └── atomChangeRpc.getChangeList() → context.changeOrderList
```

---

### 2.16 补充协议 / 和解协议

| 模板字段 | PdfBuildService 方法 | Context 数据来源 | 外部依赖 |
|---|---|---|---|
| `constructionRisk` / `partAMethod` / `partBMethod` / `constructionProblem` / `newContent` / `originalContent` | `getSupplementItemContent()` | `contractReq.supplementItemInfo` | `ContractUnifyService.supplementRequiredCheck()` |
| `houseTransactionFailedTerminationHidden` / `constructionRiskCustomerBearHidden` / `generalScenarioHidden` | `getSupplementItemHiddenFlag()` | `supplementItemInfo.selectedSupplementItem` | — |
| `problem` / `correctiveAction` | `getSettlementItemContent()` | `contractReq.settlementItemInfo` | — |

---

### 2.17 日期 / 编号类

| 模板字段 | PdfBuildService 方法 | 计算逻辑 |
|---|---|---|
| `contractNo` | `getContractNo()` | `context.contract.contractNo`，空则空字符串 |
| `applyDate` | `getApplyDate()` | 取当前日期 |
| `submitContractYear` / `submitContractMonth` / `submitContractDay` | `getContractSubmitDate()` | Calendar 取当前年月日 |
| `effectiveDate` | `getEffectiveDate()` | `contractReq.effectiveDate` |
| `lastContractNo` / `projectOrderType` | `getLastContractNo()` / `getLastContractNoV2()` | `contractService.getLatestContract()` 查询最新合同 |
| `latestSignedFormalContractNo` | `getLatestSignedFormalContractNo()` | 合并发起→ThreadLocal 取；单独发起→`contractService` 查 |

---

### 2.18 操作人信息

| 模板字段 | Context 数据来源 | ContextAspect 准备 | 外部依赖 |
|---|---|---|---|
| 操作人姓名 | `context.operatorName` | `getOperatorName()` 并行任务 | `CommonContractService` (Service) |

---

## 三、合同类型 × 字段覆盖矩阵

> ✅ = 必加载 ｜ ○ = 条件加载 ｜ — = 不适用

| 业务维度 | 认购(1) | 设计(2) | 正签(3) | 变更(4) | 解约(5) | 首期款(6) | 图纸(7) | 销售(8) | 存管(20) |
|---|---|---|---|---|---|---|---|---|---|
| **项目信息** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **签约人信息** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **合同主体** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **多主体（存管）** | — | — | — | — | — | — | — | — | ✅ |
| **合同金额** | ✅ | ✅ | ✅ | ✅ | — | ✅ | — | ✅ | — |
| **报价信息** | — | — | ✅ | ✅ | — | ○ | ✅ | ✅ | — |
| **套餐信息** | — | — | ○ | ○ | — | — | — | — | — |
| **设计费** | — | ✅ | ○ | — | — | — | — | — | — |
| **图纸** | — | — | ○ | ○ | — | — | — | ✅ | — |
| **备件** | — | — | ○ | — | — | — | — | — | — |
| **款项实收** | — | — | ✅ | ✅ | — | ✅ | ✅ | ✅ | — |
| **风控审核** | — | — | ○ | — | — | — | — | — | — |
| **存管账户** | — | — | ○ | — | — | — | — | — | ✅ |
| **收款计划** | — | — | ✅ | ✅ | — | — | — | — | — |
| **保修年限** | — | — | ✅ | — | — | — | — | — | — |
| **附件配置** | — | ✅ | ✅ | ✅ | — | ✅ | — | ✅ | — |
| **补充协议** | — | — | — | ○ | — | — | — | — | — |
| **解约协议** | — | — | — | — | ✅ | — | — | — | — |

> **条件加载说明：**
> - 套餐信息：仅 V2.5 + 整装/团装 + 正签/变更时加载
> - 设计费（正签）：仅当 planAllDTO 中存在 DesignFeeInfo 时加载
> - 图纸（正签）：仅 V2.5 + 团装时加载
> - 备件：仅 PACKAGE_FORMAL 时加载
> - 风控审核：仅 V2.5 + 房产证模式 + 存在已完结合同时加载
> - 存管账户：仅当合同类型在 `getShowEscrowUserAccountInfoList()` 中时加载

---

## 四、外部依赖全景

### 4.1 RPC 调用汇总

| RPC 服务 | 调用场景 | 被哪个 Aspect 调用 | 提供数据 |
|---|---|---|---|
| `AtomChangeRpc.getChangeApplyInfo()` | 变更合同报价/套餐 | Context + Detail | 变更范围列表、变更申请信息 |
| `AtomChangeRpc.getChangeList()` | 风控审核 | Detail | 变更单列表 |
| `AtomBudgetRpc.getPreQuotationByBillCode()` | 首期款报价校验 | Context | 预估报价详情 |
| `AtomDrawingRpc.listDrawings()` | 图纸获取 | Context + Detail | 施工图纸列表 |
| `AtomDrawingRpc.getChangeListDrawings()` | 变更图纸 | Context + Detail | 变更图纸列表 |
| `AuditRpc.getAuditInfo()` | 风控审核 | Detail | 审核详情 |
| `CeresRpc.getPersonInfo()` | 设计师信息 | Context + Detail | 设计师姓名/职级/工号 |
| `DrawingRpc.getBaseChangeDrawing()` | 变更基础图纸 | Context + Detail | 图纸 URL |
| `EscrowRpc.queryFundEscrowAccountBasicInfo()` | 存管主体 | Context + Detail | 存管账户基本信息 |
| `MdmDataRpc.getInfoByMerchantNos()` | 存管主体 | Context + Detail | 分公司详情 |
| `MdmRpc.obtainMdmMapByMdmCodes()` | 存管主体（备选） | Context + Detail | MDM 数据 |
| `OrderStandardQueryRpc.homeStandardOutput()` | 套餐信息 | Context + Detail | 套餐列表 |
| `ProjectOrderFeignService.queryProjectServerInfo()` | 预算员 | PdfBuild | 预算员信息 |
| `QuotationFeignService.getPackageByCombCode()` | 套餐详情 | Context | 套餐基础信息 |
| `QuotationFeignService.getDesignFeeConfig()` | 标准设计费 | Context + Detail | 设计费配置 |

### 4.2 内部 Service 汇总

| Service | 调用场景 | 提供数据 |
|---|---|---|
| `CommonBusinessService` | 流程版本判断、业务类型、公司编码 | processV25、businessType、协同项目单号 |
| `CommonContractService` | 设计师信息、公司信息、套餐编码 | designerName、companyInfo |
| `ContractUnifyService` | 模块配置、设计费开关、签约角色 | moduleInfo、designFeeOpen、signatoryRoleType |
| `ContractService` | 合同查询 | 最新合同、合同列表 |
| `ContractDetailService` | 预签报价 | advanceQuote |
| `ContractDependentDataService` | 个性化报价 | personalContractData |
| `ContractBusinessService` | 团装图纸、优惠券 | drawingDTO、couponRemarkList |
| `ContractFieldService` | 合同扩展字段 | area 等字段 |
| `ContractAttachConfigService` | 附件配置 | 各类附件 URL |
| `ContractCustomAttachConfigService` | 自定义附件 | 自定义附件 URL |
| `ContractCompanyInfoService` | 公司信息 | companyName |
| `ContractCityCompanyConfigService` | 城市公司配置 | 盖章关键字 |
| `ContractConfigVersionService` | 合同版本配置 | contractVersionConfig |
| `ChangeContractUnifyService` | 变更报价差异 | quoteBillDiff |
| `HomeOrderDataConversionService` | 报价数据转换 | planAllDTO、contractSourceDataBO |
| `HomeAndPcCommonService` | 预估合同额、标准设计费 | comboPriceInfo、designSignPriceInfo |
| `FundInfoService` | 款项信息 | fundInfo |
| `FundEscrowService` | 存管入口信息 | fundEscrowInfoDTO |
| `ProjectInfoReadService` | 项目信息 | projectInfoDTO |
| `AttachCommonService` | 备件信息、OCR 开关 | attachInfoDetail |
| `ComboInfoService` | 套餐附件（精装细则/预算说明/材料清单） | 各类图片 URL |
| `PdfToImageService` | PDF 转图片 | 图片 URL 列表 |
| `CommonContractService` | 销售合同签约源路由 | 签约数据源 |
| `EscrowDomain` | 存管账户 | escrowAccountDetailDTO |
| `BaseAuditChannel` | 设计师 UC ID | designerUcId |

### 4.3 Apollo 配置依赖

| 配置项 | 使用场景 | 影响字段 |
|---|---|---|
| `standardDesignFeeCityCodes` | 标准设计费城市白名单 | `preDiscountDesignerAmount`（设计费） |
| `projectDay` 上下限 | 工期合法范围校验 | `projectDay` / `wanLianGongChengQiXian` |
| 团装 2.5 工期（按 gbCode） | 团装专用工期 | `projectDay` |
| `groupOpenDayDesc` | 团装开放日描述 | `groupOpenDayDesc` |
| `percentageConfigByGbCode` | 收款百分比配置 | `percentageOfTotalOrderAmount` 等 |
| 保修年限配置 | 各业务类型的保修年限 | `waterElectricGuaranteeYear` 等 |
| 品类名称映射 | 品类展示文本 | `brandListText` |

---

## 五、ContextAspect vs DetailAspect 差异总结

| 差异维度 | ContextAspect（提交） | DetailAspect（详情） |
|---|---|---|
| **设计目的** | 数据校验 + 清洗 + 预处理 | 数据聚合 + 格式化展示 |
| **参数清洗** | ✅ `preHandleParam` / `preHandleSignInfoParam` / `preHandleProjectParam` | ❌ 不做参数清洗 |
| **一致性校验** | ✅ `dealAdvancePreQuotation`（首期款报价校验） | ❌ 不做校验 |
| **设计费合并** | ✅ 从报价合并设计费到 `designQuoteFeeDTO` | ❌ |
| **项目信息获取** | `getByProjectOrderIdWithoutCache()`（无缓存） | `getByProjectOrderId()`（有缓存） |
| **风控审核** | ❌ | ✅ `dealAuditInfo()` |
| **备件信息** | ❌ | ✅ `dealAttachInfo()` |
| **存管账户** | ✅ `dealEscrowDTO()` | ✅ `dealEscrowDTO()` |
| **多公司主体** | ✅ `dealMultiCompanyInfo()` | ✅（逻辑一致） |
| **变更图纸** | ✅ `atomDrawingRpc.getChangeListDrawings()` | ✅（逻辑一致） |
| **异常处理** | 校验失败 → 抛异常阻止提交 | 部分降级（如风控审核 try-catch 静默） |
| **参数来源** | 前端请求体 `ContractReqDTO` | AOP 方法入参数组 |

**核心设计理念**：两个 Aspect 遵循**查询-提交对称设计**——共享的数据准备方法（报价、图纸、套餐等）保持逻辑一致，各自独有的部分围绕职责补充（Context 侧重校验清洗，Detail 侧重聚合展示）。PdfBuildService 则从统一的 ThreadLocal Context 读取数据，不关心数据是由哪个 Aspect 准备的。