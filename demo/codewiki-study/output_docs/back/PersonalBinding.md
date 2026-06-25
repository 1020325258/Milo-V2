# PersonalBinding 模块文档

## 模块概述

PersonalBinding（个性化合同绑定）模块负责管理销售合同与各类业务单据（报价单、变更单、S单）之间的绑定关系。该模块在合同生命周期中承担两个核心职责：

1. **签约源数据提供**：通过策略模式，根据不同的绑定类型（报价单/变更单/S单），为个性化合同的创建、编辑提供签约源数据（商品信息、图纸、可签约单据等）。
2. **关联关系管理**：处理协同报价单撤回时的合同关联解绑逻辑，包括分布式锁保护、合同状态回退、正签草稿字段清理等。

## 系统架构

```mermaid
graph TD
    subgraph PersonalBinding
        PRH[PersonalRelationHandler]
        PRHI[PersonalRelationHandlerImpl]
        CSI[ContractSigningSource]
        ACS[AbstractContractSigningSource]
        BSS[BillSigningSourceStrategy]
        COSS[ChangeOrderSigningSourceStrategy]
        SOS[SubOrderSigningSourceStrategy]
    end

    PRH --> PRHI
    CSI --> ACS
    ACS --> BSS
    ACS --> COSS
    ACS --> SOS

    subgraph 外部依赖
        LS[LockService]
        CBLS[ContractBindLogService]
        CS[ContractService]
        CQRS[ContractQuotationRelationService]
        CRHS[ContractRelationService]
        SFS[SubOrderFeignService]
        ABR[AtomBudgetRpc]
        CFS[CommonContractService]
        HPCS[HomeAndPcCommonService]
        QRCS[QuotationRelationCommonService]
        CFH[ContractFieldHandler]
        PQS[ProductQueryService]
        MDM[MdmRpc]
    end

    PRHI --> LS
    PRHI --> CBLS
    PRHI --> CS
    PRHI --> CQRS
    PRHI --> CRHS
    PRHI --> SFS
    PRHI --> CFS
    PRHI --> HPCS
    PRHI --> QRCS
    PRHI --> CFH
    BSS --> ABR
    BSS --> PQS
    COSS --> ABR
    COSS --> PQS
    SOS --> SFS
    SOS --> MDM
```

## 核心组件详解

### 1. 合同签约源策略体系

该部分采用**策略模式 + 模板方法模式**的组合，为不同绑定类型的个性化合同提供统一的数据获取接口。

```mermaid
classDiagram
    class ContractSigningSource {
        <<interface>>
        +bindType() Integer
        +queryPersonalQuoteInfo(BindOrderInfo) List
        +hasInvalidStatusOrders(BindOrderInfo) boolean
        +buildGoodsInfo(BindOrderInfo) Map
        +buildSignableOrderInfos(String) List
        +checkPersonalCanCreate(String) boolean
        +buildPersonalDrawingImgList(BindOrderInfo) List
        +buildPersonalDrawing(BindOrderInfo, Boolean, Boolean) DrawingDTO
        +hasCPart(BindOrderInfo) boolean
        +hasBPart(BindOrderInfo) boolean
    }

    class AbstractContractSigningSource {
        <<abstract>>
        +queryPersonalQuoteInfo(BindOrderInfo) List
        +buildPersonalDrawingImgList(BindOrderInfo) List
        +buildPersonalDrawing(BindOrderInfo, Boolean, Boolean) DrawingDTO
        #buildParam(BindOrderInfo)* PersonalContractDataParam
        #filterByCompanyCode(BindOrderInfo, List)* List
        #buildProductItemCodes(BindOrderInfo)* List
        #buildDrawingQuery(...)* DrawingQuery
        #mergeCategoryNames(Set) String
        #isCPart(Integer) boolean
        #isBPart(Integer) boolean
    }

    class BillSigningSourceStrategy {
        +bindType() Integer
        +hasInvalidStatusOrders(BindOrderInfo) boolean
        +buildGoodsInfo(BindOrderInfo) Map
        +buildSignableOrderInfos(String) List
        +checkPersonalCanCreate(String) boolean
        +hasCPart(BindOrderInfo) boolean
        +hasBPart(BindOrderInfo) boolean
    }

    class ChangeOrderSigningSourceStrategy {
        +bindType() Integer
        +hasInvalidStatusOrders(BindOrderInfo) boolean
        +buildGoodsInfo(BindOrderInfo) Map
        +buildSignableOrderInfos(String) List
        +checkPersonalCanCreate(String) boolean
        +hasCPart(BindOrderInfo) boolean
        +hasBPart(BindOrderInfo) boolean
    }

    class SubOrderSigningSourceStrategy {
        +bindType() Integer
        +hasInvalidStatusOrders(BindOrderInfo) boolean
        +buildGoodsInfo(BindOrderInfo) Map
        +buildSignableOrderInfos(String) List
        +checkPersonalCanCreate(String) boolean
        +hasCPart(BindOrderInfo) boolean
        +hasBPart(BindOrderInfo) boolean
    }

    ContractSigningSource <|.. AbstractContractSigningSource
    AbstractContractSigningSource <|-- BillSigningSourceStrategy
    AbstractContractSigningSource <|-- ChangeOrderSigningSourceStrategy
    AbstractContractSigningSource <|-- SubOrderSigningSourceStrategy
```

#### 策略路由机制

系统通过 `ContractSigningSourceRouter`（参见 [ContractCore](ContractCore.md) 和 [ContractAspect](ContractAspect.md) 模块）根据 `BindTypeEnum` 路由到具体策略实现：

| 绑定类型 | 枚举值 | 策略实现 | 数据来源 |
|---------|--------|---------|---------|
| 报价单 (BILL_CODE) | 1 | `BillSigningSourceStrategy` | Atom 预算服务的报价单数据 |
| 变更单 (CHANGE_ORDER) | 2 | `ChangeOrderSigningSourceStrategy` | Atom 预算服务的变更单数据 |
| S单 (SUB_ORDER) | 3 | `SubOrderSigningSourceStrategy` | 订单服务的子单数据 |

#### 模板方法模式

`AbstractContractSigningSource` 定义了三个模板方法，封装了公共的数据获取流程，子类只需实现差异化的钩子方法：

- **`queryPersonalQuoteInfo`**：查询个性化报价数据 → 子类实现 `buildParam()` 构建查询参数 + `filterByCompanyCode()` 按公司过滤
- **`buildPersonalDrawingImgList`**：构建图纸图片列表 → 子类实现 `buildProductItemCodes()` + `buildDrawingQuery()`
- **`buildPersonalDrawing`**：构建图纸交付物 → 同上

#### 各策略差异点

**BillSigningSourceStrategy（报价单策略）**
- 通过 `AtomBudgetRpc` 校验报价单状态（排除调整中/已删除/已作废的报价单）
- 通过 `ProductQueryService` 获取 SKU 商品信息构建商品描述
- `buildSignableOrderInfos` 获取正签报价中的个性化数据，仅处理"全翻新"和"房产证"业务类型
- `checkPersonalCanCreate` 返回 `false`（报价单不单独判断是否可创建）

**ChangeOrderSigningSourceStrategy（变更单策略）**
- 通过 `AtomBudgetRpc.getChangeApplyDetails()` 校验变更流程状态（仅允许"待签约"/"已完成"）
- 图纸查询增加 `projectChangeNo` 和临时图纸状态过滤条件
- `buildSignableOrderInfos` 返回空列表（变更单不通过此方式构建可签约单据）
- `checkPersonalCanCreate` 返回 `false`

**SubOrderSigningSourceStrategy（S单策略）**
- 通过 `SubOrderFeignService.batchQuerySubOrderByNo()` 批量查询子单并校验状态
- `buildSignableOrderInfos` 包含完整的可签约 S 单筛选逻辑：
  1. 获取状态有效的子单
  2. 排除变更中的子单
  3. 排除已绑定合同的子单
  4. 排除套餐已签约的子单
- `checkPersonalCanCreate` 会放宽草稿合同过滤（兼容编辑场景），只要有可签约单据即返回 `true`
- 额外依赖 `MdmRpc` 获取公司主体名称、`PackageQueryFeignService` 获取套餐名称

### 2. PersonalRelationHandler — 关联关系处理器

```mermaid
classDiagram
    class PersonalRelationHandler {
        <<interface>>
        +revokeCooperQuotation(String, String, Long) void
    }

    class PersonalRelationHandlerImpl {
        -lockService LockService
        -contractService ContractService
        -commonContractService CommonContractService
        -quotationRelationCommonService QuotationRelationCommonService
        -contractQuotationRelationService ContractQuotationRelationService
        -homeAndPcCommonService HomeAndPcCommonService
        -contractRelationService ContractRelationService
        -contractFieldHandler ContractFieldHandler
        -subOrderFeignService SubOrderFeignService
        -contractBindLogService ContractBindLogService
        +revokeCooperQuotation(String, String, Long) void
        -unbindCooperQuotationFromContract(Contract, String, String, Long) void
        -unbindSubOrderFromContract(String, String, Long) void
        -determineRevocationActionForDirectBound(List, String) ContractRevocationAction
        -determineRevocationActionForSubOrder(List, Set) ContractRevocationAction
        -executeRevocationAction(ContractRevocationAction, Contract, String, List, Long) void
        -undoContractIfNeeded(Contract, Long) void
        -cleanFormalContractDraftFields(Contract, String, List) void
    }

    class ContractRevocationAction {
        <<enumeration>>
        CANCEL_CONTRACT
        UNBIND_AND_UNDO
        SKIP
    }

    PersonalRelationHandler <|.. PersonalRelationHandlerImpl
    PersonalRelationHandlerImpl --> ContractRevocationAction
```

`PersonalRelationHandlerImpl` 处理协同报价单撤回时的合同关联解绑，核心入口方法为 `revokeCooperQuotation`。

## 数据流

### 签约源数据查询流

```mermaid
sequenceDiagram
    participant Router as ContractSigningSourceRouter
    participant Strategy as 签约源策略
    participant Abs as AbstractContractSigningSource
    participant External as 外部服务

    Router->>Strategy: 路由到具体策略(bindType)
    Strategy->>Strategy: hasInvalidStatusOrders(BindOrderInfo)
    alt 校验失败
        Strategy-->>Router: 抛出业务异常
    end
    Strategy->>Abs: queryPersonalQuoteInfo(BindOrderInfo)
    Abs->>Strategy: buildParam(BindOrderInfo)
    Abs->>External: 查询个性化报价数据
    Abs->>Strategy: filterByCompanyCode(BindOrderInfo, data)
    Strategy-->>Router: 返回个性化报价数据
```

### 协同报价单撤回流程

```mermaid
flowchart TD
    A[revokeCooperQuotation 入口] --> B{获取分布式锁}
    B -->|失败| Z[抛出异常]
    B -->|成功| C[查询直接绑定该报价单的合同]
    C --> D{存在直接绑定合同?}

    D -->|是| E[遍历合同 - unbindCooperQuotationFromContract]
    D -->|否| F[通过S单处理 - unbindSubOrderFromContract]

    E --> G{合同状态检查}
    G -->|已作废/已签署/已确认后申请用章| H[跳过]
    G -->|有效状态| I[查询合同关联的所有单据]
    I --> J{判断撤回动作}
    J -->|仅绑定该报价单| K[CANCEL_CONTRACT: 作废合同]
    J -->|还绑定其他单据| L[UNBIND_AND_UNDO: 解除关联并撤回]

    F --> M[获取报价单对应的S单号]
    M --> N{存在S单?}
    N -->|否| O[跳过]
    N -->|是| P[查询S单是否关联合同]
    P --> Q{存在绑定?}
    Q -->|否| R[跳过]
    Q -->|是| S[按合同分组处理]
    S --> T{判断S单撤回动作}
    T -->|绑定了报价单或变更单| L
    T -->|所有S单都在撤回列表中| K
    T -->|绑定了其他S单| L

    K --> U[cleanFormalContractDraftFields]
    L --> U
    U --> V[结束]
```

### 撤回动作判定逻辑

```mermaid
flowchart TD
    subgraph 直接绑定判定
        A1[合同仅绑定了该报价单] -->|是| B1[CANCEL_CONTRACT]
        A1 -->|否| C1[UNBIND_AND_UNDO]
    end

    subgraph S单绑定判定
        A2[合同是否绑定了报价单或变更单] -->|是| B2[UNBIND_AND_UNDO]
        A2 -->|否| C2{合同绑定的S单<br>是否全部在撤回列表中}
        C2 -->|是| D2[CANCEL_CONTRACT]
        C2 -->|否| E2[UNBIND_AND_UNDO]
    end
```

## 组件交互图

```mermaid
graph LR
    subgraph PersonalBinding模块
        PRH[PersonalRelationHandler]
        BSS[BillSigningSourceStrategy]
        COSS[ChangeOrderSigningSourceStrategy]
        SOS[SubOrderSigningSourceStrategy]
    end

    subgraph ContractCore模块
        CDS[ContractDetailService]
        CFC[ContractFieldCheckService]
        CSRS[ContractScriptCreateService]
    end

    subgraph ContractAspect模块
        CCA[ContractContextAspect]
        CDA[ContractDetailAspect]
    end

    subgraph 数据层
        CS[ContractService]
        CQRS[ContractQuotationRelationService]
        CRHS[ContractRelationService]
    end

    subgraph 外部RPC
        ABR[AtomBudgetRpc]
        SFS[SubOrderFeignService]
        PQS[ProductQueryService]
        MDM[MdmRpc]
    end

    CCA -->|路由调用| BSS
    CCA -->|路由调用| COSS
    CCA -->|路由调用| SOS
    PRH -->|读写| CS
    PRH -->|读写| CQRS
    PRH -->|读写| CRHS
    BSS --> ABR
    BSS --> PQS
    COSS --> ABR
    COSS --> PQS
    SOS --> SFS
    SOS --> MDM
    PRH -->|解绑后清理| CDS
```

## 关键设计模式

### 策略模式（Strategy Pattern）

`ContractSigningSource` 接口定义了统一的签约源数据操作契约，三个策略实现分别处理报价单、变更单和 S 单三种绑定类型。通过 `ContractSigningSourceRouter`（在 [ContractAspect](ContractAspect.md) 模块中）根据 `BindTypeEnum` 动态路由到具体策略，使得新增绑定类型只需添加新的策略实现类，无需修改调用方代码。

### 模板方法模式（Template Method Pattern）

`AbstractContractSigningSource` 抽象类封装了数据获取的公共流程（参数构建 → 数据查询 → 公司过滤 → 结果组装），子类通过实现 `buildParam()`、`filterByCompanyCode()`、`buildProductItemCodes()`、`buildDrawingQuery()` 四个钩子方法来定制差异化逻辑，避免了流程代码的重复。

### 策略枚举 + 状态机模式（Revocation Action）

`PersonalRelationHandlerImpl` 内部定义了 `ContractRevocationAction` 枚举（`CANCEL_CONTRACT` / `UNBIND_AND_UNDO` / `SKIP`），将撤回操作的判定逻辑与执行逻辑分离。`determineRevocationAction*` 方法负责根据业务规则判定动作类型，`executeRevocationAction` 统一执行对应动作，逻辑清晰且易于扩展。

## 依赖关系

| 依赖方向 | 模块/组件 | 用途 |
|---------|---------|------|
| 依赖（被本模块调用） | [ContractCore](ContractCore.md) | 合同作废 (`CommonContractService.cancelCurrentContract`)、合同回退 (`HomeAndPcCommonService.undoContract`)、字段处理 (`ContractFieldHandler`) |
| 依赖（被本模块调用） | [ContractAspect](ContractAspect.md) | AOP 切面通过 Router 调用签约源策略 |
| 依赖（外部RPC） | `AtomBudgetRpc` | 查询报价单状态、变更单详情 |
| 依赖（外部RPC） | `SubOrderFeignService` | 查询子单信息、变更中的子单 |
| 依赖（外部RPC） | `ProductQueryService` | 查询报价单/变更单的商品 SKU 信息 |
| 依赖（外部RPC） | `MdmRpc` | 获取公司主体中文名称 |
| 依赖（基础服务） | `LockService` | 分布式锁，保证协同报价单撤回与换绑操作的互斥 |
| 依赖（基础服务） | `ContractBindLogService` | 记录解绑操作的审计日志 |
| 被依赖（调用本模块） | [ContractAspect](ContractAspect.md) | 合同上下文切面在创建/编辑合同流程中调用签约源策略 |
| 被依赖（调用本模块） | [ContractCore](ContractCore.md) | 合同保存/提交流程中调用 `PersonalRelationHandler` 处理关联关系 |