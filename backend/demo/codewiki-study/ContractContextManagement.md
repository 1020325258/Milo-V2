# ContractContextManagement 模块文档

## 1. 模块概述

ContractContextManagement 是合同服务（ContractCore）的**数据准备与上下文管理**子模块。它基于 Spring AOP + ThreadLocal 模式，在合同操作（保存/提交/查询详情）执行前，自动聚合来自多个外部服务的数据，并将其存入线程级上下文对象，供下游业务逻辑直接读取。

### 核心职责

| 职责 | 说明 |
|------|------|
| **数据预聚合** | 在合同操作前，通过切面拦截并行获取项目信息、报价信息、图纸信息、存管账户等多维度数据 |
| **线程上下文管理** | 通过 ThreadLocal 持有请求级别的 `ContractContext` / `ContractDetailContext`，实现无参传递 |
| **参数预处理** | 对前端传入的请求参数进行清洗、裁剪（如根据签约形式清空无关字段） |
| **生命周期保障** | 在 `@After` / `@AfterThrowing` 中确保上下文清除，防止内存泄漏 |

---

## 2. 架构设计

### 2.1 组件总览

```mermaid
graph TD
    subgraph AOP_Interceptors[AOP 拦截层]
        CA[ContractContextAspect<br/>合同保存/提交切面]
        DA[ContractDetailAspect<br/>合同详情查询切面]
    end

    subgraph Context_Management[上下文管理层]
        CH[ContractContextHandler<br/>合同上下文持有者]
        DH[ContractDetailContextHandler<br/>详情上下文持有者]
    end

    subgraph Context_POJO[上下文数据对象]
        CC[ContractContext<br/>合同操作上下文]
        DC[ContractDetailContext<br/>详情查询上下文]
    end

    subgraph External_Services[外部数据源]
        RPC1[ProjectInfoReadService]
        RPC2[QuotationFeignService]
        RPC3[AtomDrawingRpc]
        RPC4[EscrowDomain]
        RPC5[HomeOrderDataConversionService]
        RPC6[ContractDependentDataService]
        RPC7[AttachCommonService]
        RPC8[OrderStandardQueryRpc]
    end

    CA -->|initContext / setContext| CH
    CA -->|写入数据| CC
    DA -->|initContext / setContext| DH
    DA -->|写入数据| DC

    CC --> CH
    DC --> DH

    CA -->|并行调用| RPC1
    CA -->|并行调用| RPC2
    CA -->|并行调用| RPC3
    CA -->|并行调用| RPC4
    CA -->|并行调用| RPC5
    CA -->|并行调用| RPC6
    CA -->|并行调用| RPC7
    CA -->|并行调用| RPC8
    DA -->|并行调用| RPC1
    DA -->|并行调用| RPC2
    DA -->|并行调用| RPC3
    DA -->|并行调用| RPC5
    DA -->|并行调用| RPC6
    DA -->|并行调用| RPC7
    DA -->|并行调用| RPC8
```

### 2.2 上下文类继承关系

```mermaid
classDiagram
    class ContractContext {
        +ProjectInfoDTO projectInfoDTO
        +PlanAllDTO planAllDTO
        +ContractSourceDataBO contractSourceDataBO
        +DrawingDTO drawingDTO
        +ContractCityCompanyInfo contractCityCompanyInfo
        +ContractReqDTO contractReq
        +String operatorName
        +ContractContextEscrowInfo escrowInfo
        +DesignQuoteFeeDTO designQuoteFeeDTO
        +List~ComboDTO~ comboDTOList
        +List~ContractCompanyAspectInfo~ contractCompanyList
        +boolean processV25
        +Byte businessType
        +boolean developerChannel
    }

    class ContractDetailContext {
        +ProjectInfoDTO projectInfoDTO
        +PlanAllDTO planAllDTO
        +ContractSourceDataBO contractSourceDataBO
        +DrawingDTO drawingDTO
        +AttachInfoDetail attachInfoDetail
        +FundInfo relateFundInfo
        +AuditDetailDto auditDetailDTO
        +List~ChangeListDTO~ changeOrderList
        +DesignSignPriceInfo designSignPriceInfo
        +LightQuotationItem preQuotationDTO
        +List~ComboDTO~ comboDTOList
        +String drawingUrl
        +List~Integer~ atomChangeScopeList
        +DesignQuoteFeeDTO designQuoteFeeDTO
        +boolean processV25
        +Byte businessType
        +boolean firstScreen
    }

    class ContractContextHandler {
        -ThreadLocal CONTEXT
        +initContext() void
        +clearContext() void
        +getContext() ContractContext
        +getProjectInfo() ProjectInfoDTO
        +getPlanAllDTO() PlanAllDTO
        +getContractReq() ContractReqDTO
        +getDrawingDTO() DrawingDTO
        +getOperatorName() String
        +getContractCityCompanyInfo() ContractCityCompanyInfo
    }

    class ContractDetailContextHandler {
        -ThreadLocal CONTEXT
        +initContext() void
        +clearContext() void
        +getContext() ContractDetailContext
        +getProjectInfo() ProjectInfoDTO
        +getPlanAllDTO() PlanAllDTO
        +getContractSourceDataBO() ContractSourceDataBO
        +getDrawingUrl() String
        +getAtomChangeScopeList() List~Integer~
        +isFirstScreen() boolean
    }

    ContractContextHandler --> ContractContext : ThreadLocal 持有
    ContractDetailContextHandler --> ContractDetailContext : ThreadLocal 持有
```

---

## 3. 核心组件详解

### 3.1 ContractContextAspect（合同保存/提交切面）

**切面点**：拦截所有标注 `@ContractDataPrepare` 注解的方法。

#### 执行流程

```mermaid
graph TD
    Start[目标方法被调用] --> Before["@Before 切面触发"]
    Before --> Init[初始化 ContractContext]
    Init --> PreHandle[参数预处理 preHandleParam]
    PreHandle --> DealReContract[处理可重复发起合同的前置撤销]
    DealReContract --> SetReq[设置请求参数到 Context]
    SetReq --> Parallel[启动并行任务]

    subgraph Parallel_Tasks[并行数据准备 9个任务]
        T1[获取基础信息<br/>dealBaseInfo]
        T2[获取报价信息<br/>dealPlanAllDTO]
        T3[获取套餐信息<br/>dealComboInfo]
        T4[获取项目信息<br/>dealProjectInfo]
        T5[获取操作人姓名]
        T6[获取图纸信息<br/>dealDrawingDTO]
        T7[获取存管账户信息<br/>dealEscrowDTO]
        T8[获取标准设计费<br/>dealStandardDesignAmountDTO]
        T9[获取合同主体信息<br/>dealMultiCompanyInfo]
    end

    Parallel --> Parallel_Tasks
    Parallel_Tasks --> Await[等待所有任务完成]
    Await --> CityConfig[设置城市分公司配置]
    CityConfig --> ComputeMode[计算合同模式]
    ComputeMode --> DesignFee[设计费预处理]
    DesignFee --> After["@After / @AfterThrowing<br/>清除上下文"]

    style Parallel_Tasks fill:#e8f4fd,stroke:#2196F3
```

#### 参数预处理规则

参数预处理 (`preHandleParam`) 是一个复杂的决策树，根据合同类型、签约形式等条件裁剪请求参数：

```mermaid
graph TD
    Input[ContractReqDTO] --> IsSubmit{是否提交请求?}
    IsSubmit -->|是| SetSubmit[标记 contractSubmit=true]

    SetSubmit --> HasSign{有签约信息?}
    HasSign -->|是| ObjType{签约对象类型?}

    ObjType -->|公对公 COMPANY| ClearPersonal[清空个人签约数据<br/>证件/代理人/委托等]
    ObjType -->|个人 PERSON| ClearCompany[清空公对公数据<br/>营业执照/法人等]

    ClearPersonal --> CheckRole{签约角色?}
    CheckRole -->|法人 LEGAL| ClearAgent[清空公司代理人信息]
    CheckRole -->|公司代理| KeepAgent[保留公司代理人信息]

    ClearCompany --> HasAgent{有代理人?}
    ClearAgent --> HasAgent
    HasAgent -->|NO| ClearAgentData[清空代理人全部数据]
    HasAgent -->|YES| AgentSign{有委托证明?}
    AgentSign -->|否| ClearEntrust[清空委托证明]
    AgentSign -->|是| KeepEntrust[保留]

    Input --> SignChannel{签约渠道?}
    SignChannel -->|线上 ONLINE| ClearOffline[清空线下合同字段]
    SignChannel -->|线下| HouseProve{房产证明类型?}

    HouseProve -->|房产证| ClearOtherHouse[清空其他权属证明]
    HouseProve -->|其他权属| ClearHouseCert[清空房产证等]
    HouseProve -->|购房合同| ClearOthers1[清空非购房合同附件]
    HouseProve -->|认购合同| ClearOthers2[清空非认购合同附件]
    HouseProve -->|契税票| ClearOthers3[清空非契税票附件]
    HouseProve -->|特殊房产| ClearOthers4[清空非特殊房产附件]
```

#### 合同类型与数据获取的关系

不同合同类型需要获取的数据维度不同：

| 数据维度 | PACKAGE_FORMAL | PACKAGE_CHANGE | ADVANCE | DRAWING | PERSONAL | DESIGN | TERMINAL | FUND_ESCROW |
|----------|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|
| 报价信息 | Y | Y | Y | Y | Y | - | - | - |
| 图纸信息 | Y | Y | - | Y | Y | - | - | - |
| 套餐信息 | Y(2.5) | - | - | - | - | - | - | - |
| 存管账户 | - | - | - | - | - | - | - | - |
| 设计费 | - | - | - | - | - | Y | - | - |
| 合同主体 | - | - | - | - | - | - | - | Y |

> 具体的合同类型枚举含义请参考枚举定义类 `ContractTypeEnum`，不要仅凭名称推测业务含义。

---

### 3.2 ContractContextHandler（合同上下文持有者）

基于 **ThreadLocal** 模式的上下文管理器，提供静态方法访问当前线程的 `ContractContext`。

```mermaid
sequenceDiagram
    participant Controller as Controller
    participant Aspect as ContractContextAspect
    participant Handler as ContractContextHandler
    participant ThreadLocal as ThreadLocal存储
    participant Service as 下游Service

    Controller->>Aspect: @Before 拦截
    Aspect->>Handler: initContext()
    Handler->>ThreadLocal: set(new ContractContext())

    Aspect->>Handler: setContractReq(dto)
    Handler->>ThreadLocal: get().setContractReq(dto)

    Aspect->>Handler: getContext()
    Handler-->>Aspect: ContractContext

    Aspect->>Service: 执行目标方法
    Service->>Handler: getPlanAllDTO / getProjectInfo 等
    Handler->>ThreadLocal: get().getXxx()
    Handler-->>Service: 数据

    Service-->>Aspect: 方法返回
    Aspect->>Handler: clearContext()
    Handler->>ThreadLocal: remove()
```

#### 线程安全设计

| 设计要点 | 说明 |
|---------|------|
| ThreadLocal 隔离 | 每个请求线程持有独立的 `ContractContext` 实例，无共享状态 |
| 生命周期明确 | `@Before` 初始化，`@After` / `@AfterThrowing` 清除 |
| 空值保护 | 所有 getter 方法均先检查 `CONTEXT.get() == null`，避免 NPE |
| 异常安全 | `@AfterThrowing` 确保异常路径也能清除上下文 |

---

### 3.3 ContractDetailAspect（合同详情查询切面）

**切面点**：拦截所有标注 `@ContractDetailDataPrepare` 注解的方法。

#### 执行流程

```mermaid
graph TD
    Start[查询详情方法被调用] --> Before["@Before 切面触发"]
    Before --> Init[初始化 ContractDetailContext]
    Init --> ParseArgs[解析方法参数:<br/>projectOrderId, contractType,<br/>changeOrderId, isFirstScreen,<br/>billCodeInfoList, subOrderInfoList,<br/>changeOrderInfoList]
    ParseArgs --> SetFlags[设置 processV25 和 businessType]
    SetFlags --> Parallel[启动并行任务]

    subgraph FirstScreen[首屏数据 - 始终加载]
        F1[项目信息]
        F2[合同备件信息]
        F3[设计费金额]
    end

    subgraph NonFirstScreen[非首屏数据 - 按需加载]
        N1[报价信息]
        N2[套餐信息]
        N3[款项实收金额]
        N4[图纸信息]
        N5[风控审核信息]
    end

    Parallel --> FirstScreen
    Parallel --> NonFirstScreen
    FirstScreen --> Await[等待所有任务完成]
    NonFirstScreen --> Await
    Await --> After["@After / @AfterThrowing<br/>清除上下文"]

    style FirstScreen fill:#e8f5e9,stroke:#4CAF50
    style NonFirstScreen fill:#fff3e0,stroke:#FF9800
```

#### 首屏优化策略

`ContractDetailAspect` 实现了**首屏优先加载**策略：

- **首屏（isFirstScreen=true）**：只加载项目信息、备件信息、设计费金额，快速返回首屏所需数据
- **非首屏（isFirstScreen=false）**：额外加载报价、套餐、图纸、款项、审核等耗时数据

这有效降低了详情页的首屏响应时间。

---

### 3.4 ContractDetailContextHandler（详情上下文持有者）

与 `ContractContextHandler` 结构完全一致，但持有的是 `ContractDetailContext` 实例。两个 Handler 互不干扰，分别服务于合同保存和详情查询两个不同场景。

---

## 4. 模块间依赖关系

```mermaid
graph LR
    subgraph ContractContextMgmt[ContractContextManagement 当前模块]
        CA[ContractContextAspect]
        DA[ContractDetailAspect]
        CH[ContractContextHandler]
        DH[ContractDetailContextHandler]
    end

    subgraph ContractCore_Other[ContractCore 其他子模块]
        CD[ContractDetail<br/>详情展示与按钮配置]
        CS[ContractSigning<br/>合同签署]
        CV[ContractValidation<br/>合同校验]
        CDS[ContractDraftAndSubmit<br/>草稿与提交]
        CPDF[ContractPdfGeneration<br/>PDF生成]
    end

    subgraph Strategy_Modules[策略模块]
        CCS[ChangeContractStrategy]
        SPDF[CreateContractPdfBySelf]
    end

    subgraph External_Related[外部关联模块]
        MP[MaterialPdf]
        CSS[ContractSigningSource]
        PB[PersonalBind]
    end

    CA -->|下游消费上下文数据| CD
    CA -->|下游消费上下文数据| CS
    CA -->|下游消费上下文数据| CV
    CA -->|下游消费上下文数据| CDS
    CA -->|下游消费上下文数据| CPDF

    DA -->|下游消费上下文数据| CD

    CA -->|调用| CCS
    CA -->|调用| CSS
    CA -->|调用| PB
    DA -->|调用| PB

    style ContractContextMgmt fill:#e3f2fd,stroke:#1565C0
```

### 4.1 对外暴露的静态 API

`ContractContextHandler` 和 `ContractDetailContextHandler` 作为静态工具类，被 ContractCore 下的多个子模块广泛引用：

| 静态方法 | 提供方 | 消费场景 |
|---------|--------|---------|
| `ContractContextHandler.getPlanAllDTO()` | ContractContextAspect | 合同保存时获取报价数据 |
| `ContractContextHandler.getProjectInfo()` | ContractContextAspect | 获取项目信息进行字段填充 |
| `ContractContextHandler.getContractReq()` | ContractContextAspect | 获取原始请求参数 |
| `ContractContextHandler.getDrawingDTO()` | ContractContextAspect | 获取图纸数据生成合同附件 |
| `ContractContextHandler.getContractCityCompanyInfo()` | ContractContextAspect | 获取城市分公司配置 |
| `ContractDetailContextHandler.getPlanAllDTO()` | ContractDetailAspect | 详情页展示报价数据 |
| `ContractDetailContextHandler.getProjectInfo()` | ContractDetailAspect | 详情页展示项目信息 |
| `ContractDetailContextHandler.isFirstScreen()` | ContractDetailAspect | 控制详情页分段加载 |

---

## 5. 并行任务编排

两个切面均使用 `ParallelTaskService` 实现数据的并行获取，大幅提升数据准备效率：

```mermaid
sequenceDiagram
    participant Aspect as 切面
    participant PTS as ParallelTaskService
    participant Pool as 线程池
    participant RPC1 as ProjectInfoService
    participant RPC2 as QuotationService
    participant RPC3 as DrawingRpc
    participant RPC4 as EscrowDomain

    Aspect->>PTS: newParallelTasks()
    PTS-->>Aspect: ParallelTasksContext

    Aspect->>PTS: addNewTask(ctx, task1)
    Aspect->>PTS: addNewTask(ctx, task2)
    Aspect->>PTS: addNewTask(ctx, task3)
    Aspect->>PTS: addNewTask(ctx, task4)

    Aspect->>PTS: execTasks(ctx)
    PTS->>Pool: 提交所有任务

    par 并行执行
        Pool->>RPC1: 查询项目信息
        Pool->>RPC2: 查询报价信息
        Pool->>RPC3: 查询图纸信息
        Pool->>RPC4: 查询存管信息
    end

    RPC1-->>Pool: 返回结果
    RPC2-->>Pool: 返回结果
    RPC3-->>Pool: 返回结果
    RPC4-->>Pool: 返回结果

    Aspect->>PTS: awaitTasksResult(ctx)
    PTS-->>Aspect: 全部完成

    Note over Aspect: 结果已写入Context<br/>下游可直接读取
```

### 并行任务清单

#### ContractContextAspect（合同保存）- 9 个并行任务

| 序号 | 任务 | 调用服务 | 条件 |
|:---:|------|---------|------|
| 1 | 获取基础信息 | `ContractUnifyService` | 始终执行 |
| 2 | 获取报价信息 | `HomeOrderDataConversionService` / `AtomChangeRpc` | 按合同类型路由 |
| 3 | 获取套餐信息 | `OrderStandardQueryRpc` | 仅 2.5 流程 + 证房业务 + 正签 |
| 4 | 获取项目信息 | `ProjectInfoReadService` | 始终执行 |
| 5 | 获取操作人姓名 | `HomeAndPcCommonService` | 始终执行 |
| 6 | 获取图纸信息 | `AtomDrawingRpc` / `ContractBusinessService` | 按合同类型路由 |
| 7 | 获取存管账户信息 | `EscrowDomain` | 仅需要展示存管的合同类型 |
| 8 | 获取标准设计费 | `HomeAndPcCommonService` | 仅设计合同 + 特定城市 |
| 9 | 获取合同主体信息 | `FundEscrowService` / `MdmRpc` | 仅存管协议 |

#### ContractDetailAspect（合同详情）- 最多 8 个并行任务

| 序号 | 任务 | 首屏加载 | 非首屏加载 |
|:---:|------|:---:|:---:|
| 1 | 项目信息 | Y | Y |
| 2 | 备件信息 | Y | Y |
| 3 | 设计费金额 | Y | Y |
| 4 | 报价信息 | - | Y |
| 5 | 套餐信息 | - | Y |
| 6 | 款项实收 | - | Y |
| 7 | 图纸信息 | - | Y |
| 8 | 风控审核 | - | Y |

---

## 6. 报价信息路由策略

报价信息的获取是两个切面中最复杂的逻辑，根据合同类型和业务模式有多条路由：

```mermaid
graph TD
    Input[报价信息准备] --> CheckType{合同类型?}

    CheckType -->|ADVANCE| AdvType{业务类型?}
    AdvType -->|翻新全案| Skip[跳过, 页面上传]
    AdvType -->|其他| AdvPreQuotation{支持预估报价?}
    AdvPreQuotation -->|是| DealAdvance[dealAdvancePreQuotation<br/>校验报价单一致性]
    AdvPreQuotation -->|否| CalcAdvance[计算预估合同额<br/>加获取套餐信息]

    CheckType -->|PACKAGE_CHANGE + 2.5协同| AtomChange[buildAtomChangeQuotation<br/>请求中控变更报价]

    CheckType -->|PERSONAL| PersonalQuote[queryPersonalQuoteInfoV2<br/>按绑定类型路由]

    CheckType -->|PACKAGE_FORMAL 或 DRAWING| GeneralQuote[contractSourceDate<br/>通用报价获取]

    GeneralQuote --> DesignFee{正签加有设计费报价?}
    DesignFee -->|是| BuildDesignDTO[构建 DesignQuoteFeeDTO]
    DesignFee -->|否| Done

    AtomChange --> Done[写入 Context]
    PersonalQuote --> Done
    BuildDesignDTO --> Done
    CalcAdvance --> Done
    DealAdvance --> Done

    style Input fill:#e3f2fd,stroke:#1565C0
    style Done fill:#e8f5e9,stroke:#4CAF50
```

### 变更合同报价的特殊处理

对于 2.5 协同模式下的变更协议（`PACKAGE_CHANGE`），报价获取路径与通用路径不同：

```mermaid
sequenceDiagram
    participant CA as ContractContextAspect
    participant ACR as AtomChangeRpc
    participant CCU as ChangeContractUnifyService
    participant HODC as HomeOrderDataConversionService

    CA->>ACR: getChangeApplyInfo(changeOrderId)
    ACR-->>CA: ChangeApplyInfoDTO 含changeScopeList

    alt 变更范围包含报价
        CA->>CCU: getQuoteBillDiff(projectOrderId, changeOrderId)
        CCU-->>CA: QuoteChangeDiffBO 含报价差异
        CA->>HODC: changeHardDecorationFileData(changeOrderId)
        HODC-->>CA: 变更硬装 PDF
    else 变更范围不包含报价
        CA->>CCU: getQuoteBillDiff(...)
        CCU-->>CA: 使用变更前报价
    end

    CA->>CCU: atomChangeQuotationConvertToPlanAllDTO(...)
    CCU-->>CA: PlanAllDTO
```

---

## 7. 上下文生命周期

```mermaid
stateDiagram-v2
    [*] --> Idle: 初始状态

    Idle --> Initialized: @Before initContext
    Initialized --> DataPreparing: 并行任务启动
    DataPreparing --> DataReady: 所有任务完成
    DataReady --> Consuming: 下游业务读取
    Consuming --> Cleared: @After clearContext

    DataPreparing --> Cleared: @AfterThrowing clearContext
    DataReady --> Cleared: @AfterThrowing clearContext
    Consuming --> Cleared: @AfterThrowing clearContext

    Cleared --> [*]: ThreadLocal.remove

    note right of Initialized
        ThreadLocal.set(new Context)
        内存分配
    end note

    note right of Cleared
        ThreadLocal.remove
        防止内存泄漏
    end note
```

---

## 8. 设计模式总结

| 模式 | 应用 | 说明 |
|------|------|------|
| **AOP + 注解驱动** | `ContractContextAspect` / `ContractDetailAspect` | 通过自定义注解标记需要数据准备的方法，切面自动拦截 |
| **ThreadLocal 上下文** | `ContractContextHandler` / `ContractDetailContextHandler` | 请求级别的隐式参数传递，避免方法签名膨胀 |
| **并行编排** | `ParallelTaskService` | 将无依赖的数据获取任务并行执行，降低总耗时 |
| **模板方法变体** | 两个 Aspect 结构相似但数据维度不同 | 共享相同的生命周期管理模式 |
| **条件路由** | 报价信息 / 图纸信息获取 | 根据合同类型、业务模式、流程版本路由到不同的获取策略 |
| **策略模式** | 通过 `ContractSigningSourceRouter` 路由 | 个性化合同的图纸获取按绑定类型走不同策略 |

---

## 9. 相关模块文档

- [ContractDetail](ContractDetail.md) - 合同详情展示与按钮配置（消费本模块上下文数据）
- [ContractSigning](ContractSigning.md) - 合同签署（消费本模块上下文数据）
- [ContractValidation](ContractValidation.md) - 合同校验（消费本模块上下文数据）
- [ContractDraftAndSubmit](ContractDraftAndSubmit.md) - 合同草稿与提交（消费本模块上下文数据）
- [ContractPdfGeneration](ContractPdfGeneration.md) - 合同 PDF 生成
- [ContractSigningSource](ContractSigningSource.md) - 签约来源路由策略（本模块调用）
- [PersonalBind](PersonalBind.md) - 个人绑定关系处理（本模块调用）
