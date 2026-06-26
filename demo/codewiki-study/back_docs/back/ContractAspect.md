Based on the core component codes already provided, I have sufficient information to generate the comprehensive documentation. Let me proceed directly.

# ContractAspect 模块文档

## 1. 模块概述

ContractAspect 是合同服务（Contract Service）中的**横切关注点（Cross-Cutting Concern）模块**，基于 Spring AOP 实现。该模块的核心职责是在合同业务操作执行**之前**，自动完成数据预加载和上下文初始化，将分散在各业务 Service 中的数据准备逻辑统一收敛到切面层，实现**数据准备与业务逻辑的解耦**。

该模块管理两个独立的 AOP 切面流：

- **合同保存/提交流**（`ContractContextAspect`）：拦截标注了 `@ContractDataPrepare` 注解的方法，在合同保存草稿、提交、签约等操作前并行加载项目信息、报价信息、图纸信息、存管账户信息等。
- **合同详情查询流**（`ContractDetailAspect`）：拦截标注了 `@ContractDetailDataPrepare` 注解的方法，在查询合同详情前并行加载项目信息、报价信息、备件信息、款项信息、风控审核信息等。

两个切面各配合一个基于 `ThreadLocal` 的上下文 Handler（`ContractContextHandler` / `ContractDetailContextHandler`），确保同一线程内的下游 Service 可以直接获取预加载数据，无需重复查询。

## 2. 架构设计

### 2.1 模块在整体系统中的位置

```mermaid
graph TD
    subgraph ClientLayer[客户端层]
        HomeApp[Home APP]
        PCWeb[PC Web]
    end

    subgraph ControllerLayer[Controller 层]
        HomeContractCtrl[Home 合同 Controller]
        PCContractCtrl[PC 合同 Controller]
        HomeDetailCtrl[Home 详情 Controller]
        PCDetailCtrl[PC 详情 Controller]
    end

    subgraph AspectLayer[ContractAspect 模块]
        CDA[ContractDataPrepare 注解]
        CDPA[ContractDetailDataPrepare 注解]
        CCA[ContractContextAspect]
        CDA_A[ContractDetailAspect]
        CCH[ContractContextHandler]
        CDCH[ContractDetailContextHandler]
    end

    subgraph CoreLayer[ContractCore 模块]
        SaveDraft[ContractSaveDraftService]
        Escrow[ContractEscrowService]
        CompanySign[ContractCompanySignService]
        SelfSeal[ContractSelfSealService]
        Detail[ContractDetailService]
        BtnConfig[ContractButtonConfigService]
    end

    subgraph RpcLayer[RPC / 外部服务]
        ProjectRPC[ProjectInfoReadService]
        QuotaRPC[QuotationFeignService]
        DrawRPC[AtomDrawingRpc]
        EscrowRPC[EscrowRpc]
        ChangeRPC[AtomChangeRpc]
        AuditRPC[AuditRpc]
        FundRPC[FundInfoService]
        OrderRPC[OrderStandardQueryRpc]
    end

    HomeApp --> HomeContractCtrl
    PCWeb --> PCContractCtrl
    HomeApp --> HomeDetailCtrl
    PCWeb --> PCDetailCtrl

    HomeContractCtrl --> CDA
    PCContractCtrl --> CDA
    HomeDetailCtrl --> CDPA
    PCDetailCtrl --> CDPA

    CDA --> CCA
    CDPA --> CDA_A

    CCA --> CCH
    CDA_A --> CDCH

    CCA --> SaveDraft
    CCA --> Escrow
    CCA --> CompanySign
    CCA --> SelfSeal
    CDA_A --> Detail
    CDA_A --> BtnConfig

    CCA --> ProjectRPC
    CCA --> QuotaRPC
    CCA --> DrawRPC
    CCA --> EscrowRPC
    CCA --> ChangeRPC

    CDA_A --> ProjectRPC
    CDA_A --> QuotaRPC
    CDA_A --> DrawRPC
    CDA_A --> FundRPC
    CDA_A --> AuditRPC
    CDA_A --> ChangeRPC
    CDA_A --> OrderRPC
```

### 2.2 核心组件关系

```mermaid
classDiagram
    class ContractDataPrepare {
        <<annotation>>
        标注需要数据准备的合同保存/提交方法
    }

    class ContractDetailDataPrepare {
        <<annotation>>
        标注需要数据准备的合同详情查询方法
    }

    class ContractContextAspect {
        -ProjectInfoReadService projectInfoReadService
        -QuotationFeignService quotationFeignService
        -ParallelTaskService parallelTaskService
        -ContractUnifyService contractUnifyService
        +beforeHandle(JoinPoint) void
        +afterHandle() void
        +afterThrowing() void
        -dealBaseInfo() void
        -dealPlanAllDTO() void
        -dealComboInfo() void
        -dealDrawingDTO() void
        -dealEscrowDTO() void
        -dealProjectInfo() void
        -dealMultiCompanyInfo() void
        -dealStandardDesignAmountDTO() void
        -preHandleParam() void
    }

    class ContractContextHandler {
        -ThreadLocal~ContractContext~ CONTEXT$
        +initContext() void$
        +clearContext() void$
        +getContext() ContractContext$
        +setContractReq(ContractReqDTO) void$
        +getContractReq() ContractReqDTO$
        +setPlanAllDTO(PlanAllDTO) void$
        +getPlanAllDTO() PlanAllDTO$
        +setProjectInfo(ProjectInfoDTO) void$
        +getProjectInfo() ProjectInfoDTO$
        +setDrawingDTO(DeliverDrawingDTO) void$
        +getDrawingDTO() DeliverDrawingDTO$
    }

    class ContractDetailAspect {
        -ProjectInfoReadService projectInfoReadService
        -ParallelTaskService parallelTaskService
        -ContractDetailService contractDetailService
        -AttachCommonService attachCommonService
        -FundInfoService fundInfoService
        -AuditRpc auditRpc
        +beforeHandle(JoinPoint) void
        +afterHandle() void
        +afterThrowing() void
        -dealProjectInfo() void
        -dealPlanAllDTO() void
        -dealComboInfo() void
        -dealDrawingDTO() void
        -dealRelateFundInfo() void
        -dealAuditInfo() void
        -dealAttachInfo() void
        -dealStandardDesignAmountDTO() void
    }

    class ContractDetailContextHandler {
        -ThreadLocal~ContractDetailContext~ CONTEXT$
        +initContext() void$
        +clearContext() void$
        +getContext() ContractDetailContext$
        +setPlanAllDTO(PlanAllDTO) void$
        +getPlanAllDTO() PlanAllDTO$
        +setDrawingUrl(String) void$
        +getDrawingUrl() String$
        +setAtomChangeScopeList(List) void$
        +getAtomChangeScopeList() List$
        +setFirstScreen(boolean) void$
        +isFirstScreen() boolean$
    }

    class ContractContext {
        -ContractReqDTO contractReq
        -ProjectInfoDTO projectInfoDTO
        -PlanAllDTO planAllDTO
        -ContractSourceDataBO contractSourceDataBO
        -DrawingDTO.DeliverDrawingDTO drawingDTO
        -ContractCityCompanyInfo contractCityCompanyInfo
        -DesignQuoteFeeDTO designQuoteFeeDTO
        -ContractContextEscrowInfo escrowInfo
        -String operatorName
        -boolean processV25
        -Byte businessType
        -boolean developerChannel
        -List~ComboDTO~ comboDTOList
        -List~ContractCompanyAspectInfo~ contractCompanyList
    }

    class ContractDetailContext {
        -ProjectInfoDTO projectInfoDTO
        -PlanAllDTO planAllDTO
        -ContractSourceDataBO contractSourceDataBO
        -DrawingDTO.DeliverDrawingDTO drawingDTO
        -String drawingUrl
        -List~Integer~ atomChangeScopeList
        -DesignQuoteFeeDTO designQuoteFeeDTO
        -DesignSignPriceInfo designSignPriceInfo
        -AttachInfoDetail attachInfoDetail
        -FundInfo relateFundInfo
        -AuditDetailDto auditDetailDTO
        -LightQuotationItem preQuotationDTO
        -List~ComboDTO~ comboDTOList
        -List~ChangeListDTO~ changeOrderList
        -boolean firstScreen
        -boolean processV25
        -Byte businessType
    }

    ContractDataPrepare ..> ContractContextAspect : 触发
    ContractDetailDataPrepare ..> ContractDetailAspect : 触发
    ContractContextAspect --> ContractContextHandler : 写入上下文
    ContractDetailAspect --> ContractDetailContextHandler : 写入上下文
    ContractContextHandler --> ContractContext : 持有
    ContractDetailContextHandler --> ContractDetailContext : 持有
```

## 3. 核心组件详解

### 3.1 ContractContextAspect — 合同保存/提交切面

`ContractContextAspect` 是标注了 `@Aspect` 和 `@Component` 的 Spring Bean，通过 AOP 拦截所有标注了 `@ContractDataPrepare` 注解的方法。其生命周期如下：

| AOP 通知 | 方法 | 职责 |
|----------|------|------|
| `@Before` | `beforeHandle()` | 初始化上下文、参数预处理、并行加载数据、设置上下文 |
| `@After` | `afterHandle()` | 清除 ThreadLocal 上下文 |
| `@AfterThrowing` | `afterThrowing()` | 异常时也清除 ThreadLocal 上下文，防止内存泄漏 |

#### 3.1.1 数据准备流程

```mermaid
graph TD
    Start[beforeHandle 触发] --> Init[initContext 初始化 ThreadLocal]
    Init --> PreHandle[preHandleParam 参数预处理]
    PreHandle --> DealReContract[处理可重复发起合同的前置撤销]
    DealReContract --> SetReq[setContractReq 设置请求到上下文]
    SetReq --> DetectProcess[检测 processV25 和 businessType]

    DetectProcess --> Parallel[并行任务启动]

    subgraph ParallelTasks[并行数据加载]
        T1[dealBaseInfo 基础信息]
        T2[dealPlanAllDTO 报价信息]
        T3[dealComboInfo 套餐信息]
        T4[dealProjectInfo 项目信息]
        T5[getOperatorName 操作人姓名]
        T6[dealDrawingDTO 图纸信息]
        T7[dealEscrowDTO 存管账户信息]
        T8[dealStandardDesignAmountDTO 设计费金额]
        T9[dealMultiCompanyInfo 合同主体信息]
    end

    Parallel --> T1
    Parallel --> T2
    Parallel --> T3
    Parallel --> T4
    Parallel --> T5
    Parallel --> T6
    Parallel --> T7
    Parallel --> T8
    Parallel --> T9

    T1 --> Await[awaitTasksResult 等待所有任务完成]
    T2 --> Await
    T3 --> Await
    T4 --> Await
    T5 --> Await
    T6 --> Await
    T7 --> Await
    T8 --> Await
    T9 --> Await

    Await --> CityConfig[获取合同城市分公司配置]
    CityConfig --> ContractMode[计算当前合同模式]
    ContractMode --> DesignFee[设计费预处理]
    DesignFee --> End[数据准备完成]

    End --> Clear[afterHandle: clearContext]
```

#### 3.1.2 参数预处理逻辑

`preHandleParam()` 方法在并行数据加载之前执行，负责根据业务规则清理和规范化请求参数：

```mermaid
flowchart TD
    Start[preHandleParam 开始] --> SubmitCheck{是否合同提交请求?}
    SubmitCheck -->|是| SetSubmit[标记 contractSubmit = true]
    SubmitCheck -->|否| SetSubmitN[contractSubmit = false]

    SetSubmit --> SignCheck{签约信息存在?}
    SetSubmitN --> SignCheck

    SignCheck -->|是| PreSign[preHandleSignInfoParam]
    SignCheck -->|否| PromiseCheck

    PreSign --> ObjType{签约对象类型}
    ObjType -->|公对公| ClearPerson[清空个人签约数据]
    ObjType -->|个人签约| ClearCompany[清空公对公数据]

    ClearPerson --> AgentCheck
    ClearCompany --> AgentCheck

    AgentCheck{有代理人?}
    AgentCheck -->|否| ClearAgent[清空代理人数据]
    AgentCheck -->|是| AgentDoc{有委托证明?}
    AgentDoc -->|否| ClearAgentDoc[清空委托证明]
    AgentDoc -->|是| SignChannel

    SignChannel{签约渠道}
    SignChannel -->|线上| ClearOffline[清空线下合同字段]
    SignChannel -->|线下| HouseProve

    HouseProve{房产证明类型} --> |房产证| ClearOther1[清空其他权属证明]
    HouseProve --> |其他权属| ClearOther2[清空房产证]
    HouseProve --> |购房合同| ClearOther3[清空其余证明]
    HouseProve --> |契税票| ClearOther4[清空其余证明]

    ClearAgent --> PromiseCheck{承诺信息处理}
    AgentDoc --> PromiseCheck
    ClearOffline --> PromiseCheck
    ClearOther1 --> PromiseCheck
    ClearOther2 --> PromiseCheck
    ClearOther3 --> PromiseCheck
    ClearOther4 --> PromiseCheck

    PromiseCheck --> ProjectParam[preHandleProjectParam 项目参数补零]
    ProjectParam --> DocCodeCompat[兼容处理永久 DocumentCode]
    DocCodeCompat --> Done[预处理完成]
```

#### 3.1.3 报价信息准备（dealPlanAllDTO）

报价信息的获取路径根据合同类型和业务类型有多条分支：

```mermaid
flowchart TD
    Start[dealPlanAllDTO] --> TypeCheck{合同类型判断}

    TypeCheck -->|首期款 ADVANCE| AdvCheck{翻新全案?}
    AdvCheck -->|是| Return1[返回，页面上传]
    AdvCheck -->|否| PreQuotationCheck{支持预估报价单?}
    PreQuotationCheck -->|是| DealAdvancePre[dealAdvancePreQuotation 校验报价单]
    PreQuotationCheck -->|否| DealAdvanceStd[标准首期款报价获取]

    TypeCheck -->|正签 PACKAGE_FORMAL / DRAWING| StdQuote[通用报价获取]
    TypeCheck -->|变更 PACKAGE_CHANGE| V25Check{processV25 且协同模式?}
    V25Check -->|是| AtomChange[buildAtomChangeQuotation]
    V25Check -->|否| StdQuote
    TypeCheck -->|个人 PERSONAL| PersonalQuote[queryPersonalQuoteInfoV2]

    StdQuote --> DesignFeeExtract[提取设计费信息]
    AtomChange --> SetContext1[设置变更报价到上下文]
    PersonalQuote --> SetContext2[设置个人合同数据到上下文]
    DesignFeeExtract --> SetContext3[设置通用报价到上下文]
    DealAdvanceStd --> SetContext4[设置首期款报价到上下文]
```

### 3.2 ContractContextHandler — 合同保存上下文管理器

`ContractContextHandler` 是一个纯静态工具类，基于 `ThreadLocal<ContractContext>` 实现线程安全的上下文传递：

| 特性 | 说明 |
|------|------|
| **线程隔离** | 每个请求线程拥有独立的 `ContractContext` 实例 |
| **生命周期管理** | `@Before` 初始化 → 业务方法使用 → `@After` / `@AfterThrowing` 清除 |
| **防泄漏保障** | 异常路径也会执行 `clearContext()` |
| **空安全** | getter 方法先检查 `CONTEXT.get() == null`，防止 NPE |

### 3.3 ContractDetailAspect — 合同详情查询切面

`ContractDetailAspect` 的结构与 `ContractContextAspect` 类似，但面向**合同详情查询**场景，增加了首屏优化和更多详情相关数据的加载。

#### 3.3.1 首屏优化策略

```mermaid
flowchart LR
    subgraph FirstScreen[首屏加载 isFirstScreen=true]
        FS1[项目信息]
        FS2[备件信息]
        FS3[设计费金额]
    end

    subgraph FullLoad[完整加载 isFirstScreen=false]
        FL1[项目信息]
        FL2[备件信息]
        FL3[设计费金额]
        FL4[报价信息]
        FL5[套餐信息]
        FL6[款项实收金额]
        FL7[图纸信息]
        FL8[风控审核信息]
    end

    Request[详情查询请求] --> ScreenCheck{isFirstScreen?}
    ScreenCheck -->|true| FirstScreen
    ScreenCheck -->|false| FullLoad
```

首屏模式下仅加载 3 项基础数据，减少首屏响应时间；非首屏时并行加载全部 8 项数据。

#### 3.3.2 详情查询额外数据

与合同保存切面相比，详情切面额外加载以下数据：

| 数据项 | 方法 | 说明 |
|--------|------|------|
| 款项实收金额 | `dealRelateFundInfo()` | 根据合同类型映射关联款项类型，查询实际收款金额 |
| 风控审核信息 | `dealAuditInfo()` | 仅合并发起的正签合同，获取审核详情和变更单列表 |
| 备件信息 | `dealAttachInfo()` | 仅正签合同，获取项目级备件信息 |
| 预估报价单 | `dealPlanAllDTO()` 中首期款分支 | 获取 `LightQuotationDTO` 预估报价 |

### 3.4 ContractDetailContextHandler — 合同详情上下文管理器

与 `ContractContextHandler` 结构相同，操作 `ThreadLocal<ContractDetailContext>`。额外暴露了详情特有的访问方法：

- `setDrawingUrl(String)` / `getDrawingUrl()` — 变更图纸 URL
- `setAtomChangeScopeList(List<Integer>)` / `getAtomChangeScopeList()` — 变更范围列表
- `setFirstScreen(boolean)` / `isFirstScreen()` — 首屏标记

## 4. 数据流

### 4.1 合同保存/提交数据流

```mermaid
sequenceDiagram
    participant Client as 客户端
    participant Ctrl as Controller
    participant CCA as ContractContextAspect
    participant CCH as ContractContextHandler
    participant Ctx as ContractContext
    participant RPC as 外部 RPC 服务
    participant Core as ContractCore Service

    Client->>Ctrl: 提交合同请求
    Ctrl->>CCA: @Before 切面拦截
    CCA->>CCH: initContext()
    CCH->>Ctx: new ContractContext()

    CCA->>CCA: preHandleParam(ContractReqDTO)
    Note over CCA: 参数规范化：清理无关字段、兼容处理

    par 并行数据加载
        CCA->>RPC: 项目信息
        RPC-->>CCA: ProjectInfoDTO
    and
        CCA->>RPC: 报价信息
        RPC-->>CCA: PlanAllDTO / ContractSourceDataBO
    and
        CCA->>RPC: 图纸信息
        RPC-->>CCA: DrawingDTO
    and
        CCA->>RPC: 存管账户信息
        RPC-->>CCA: EscrowAccountDetailDTO
    and
        CCA->>RPC: 套餐信息
        RPC-->>CCA: List[ComboDTO]
    and
        CCA->>RPC: 操作人姓名
        RPC-->>CCA: String operatorName
    end

    CCA->>CCH: setContractReq / setPlanAllDTO / ...
    CCH->>Ctx: 存储到 ThreadLocal

    CCA->>Core: 执行业务方法 (saveDraft / submit / sign)
    Core->>CCH: 从 ThreadLocal 读取预加载数据
    CCH-->>Core: ContractContext
    Core->>Core: 执行核心业务逻辑
    Core-->>Ctrl: 返回结果
    Ctrl-->>Client: 响应

    CCA->>CCH: clearContext()
    CCH->>Ctx: ThreadLocal.remove()
```

### 4.2 合同详情查询数据流

```mermaid
sequenceDiagram
    participant Client as 客户端
    participant Ctrl as Controller
    participant CDA as ContractDetailAspect
    participant CDCH as ContractDetailContextHandler
    participant Ctx as ContractDetailContext
    participant RPC as 外部 RPC 服务
    participant Core as ContractDetailService

    Client->>Ctrl: 查询合同详情
    Ctrl->>CDA: @Before 切面拦截
    CDA->>CDCH: initContext()
    CDCH->>Ctx: new ContractDetailContext()

    alt 首屏查询 (isFirstScreen = true)
        par 仅加载基础数据
            CDA->>RPC: 项目信息
            CDA->>RPC: 备件信息
            CDA->>RPC: 设计费金额
        end
    else 非首屏查询 (isFirstScreen = false)
        par 并行加载全部数据
            CDA->>RPC: 项目信息
            CDA->>RPC: 备件信息
            CDA->>RPC: 设计费金额
            CDA->>RPC: 报价信息
            CDA->>RPC: 套餐信息
            CDA->>RPC: 款项实收金额
            CDA->>RPC: 图纸信息
            CDA->>RPC: 风控审核信息
        end
    end

    CDA->>CDCH: 存储到 ThreadLocal
    CDA->>Core: 执行详情查询方法
    Core->>CDCH: 从 ThreadLocal 读取数据
    CDCH-->>Core: ContractDetailContext
    Core-->>Ctrl: 返回合同详情
    Ctrl-->>Client: 响应

    CDA->>CDCH: clearContext()
```

## 5. 依赖关系

### 5.1 模块间依赖

```mermaid
graph LR
    subgraph CurrentModule[ContractAspect 当前模块]
        CCA[ContractContextAspect]
        CDA[ContractDetailAspect]
        CCH[ContractContextHandler]
        CDCH[ContractDetailContextHandler]
    end

    subgraph ContractCore[ContractCore 模块]
        CDS[ContractDetailService]
        CSSS[ContractSaveDraftService]
        CES[ContractEscrowService]
        CCSS[ContractCompanySignService]
        CSSf[ContractSelfSealService]
        CBSCfg[ContractButtonConfigService]
    end

    subgraph PersonalBinding[PersonalBinding 模块]
        CSRR[ContractSigningSourceRouter]
    end

    subgraph ChangeContract[ChangeContract 模块]
        CCUF[ChangeContractUnifyService]
    end

    subgraph CommonService[公共服务层]
        PRLS[ProjectInfoReadService]
        QFS[QuotationFeignService]
        HPC[HomeAndPcCommonService]
        PBS[ParallelTaskService]
        CBS[CommonBusinessService]
        CUVS[ContractUnifyService]
        CCS[CommonContractService]
        CCVS[ContractConfigVersionService]
        HDDCS[HomeOrderDataConversionService]
        CDDS[ContractDependentDataService]
        CBusS[ContractBusinessService]
    end

    subgraph RPC[RPC 层]
        ACR[AtomChangeRpc]
        ABR[AtomBudgetRpc]
        ADR[AtomDrawingRpc]
        ER[EscrowRpc]
        AR[AuditRpc]
        CR[CeresRpc]
        FF[FundInfoService]
        OSQR[OrderStandardQueryRpc]
    end

    CCA --> CUVS
    CCA --> PRLS
    CCA --> QFS
    CCA --> HPC
    CCA --> PBS
    CCA --> CBS
    CCA --> CCS
    CCA --> CCVS
    CCA --> CDDS
    CCA --> HDDCS
    CCA --> CBusS
    CCA --> CSRR

    CDA --> PRLS
    CDA --> QFS
    CDA --> HPC
    CDA --> PBS
    CDA --> CBS
    CDA --> CUVS
    CDA --> CCS
    CDA --> CDDS
    CDA --> HDDCS
    CDA --> CBusS
    CDA --> CSRR
    CDA --> CDS
    CDA --> CSRR

    CCA --> ACR
    CCA --> ABR
    CCA --> ADR
    CCA --> ER

    CDA --> ACR
    CDA --> ADR
    CDA --> AR
    CDA --> FF

    CCA --> CSSS
    CCA --> CES
    CCA --> CCSS
    CCA --> CSSf

    CDA --> CBSCfg
```

### 5.2 外部 RPC 依赖清单

| RPC 服务 | 所属系统 | 调用切面 | 用途 |
|----------|---------|---------|------|
| `ProjectInfoReadService` | 项目服务 | 两个切面 | 获取项目信息 |
| `QuotationFeignService` | 中控报价 | 两个切面 | 获取报价单和套餐信息 |
| `AtomDrawingRpc` | 图纸服务 (Atom) | 两个切面 | 获取施工图纸 |
| `AtomChangeRpc` | 变更服务 (Atom) | 两个切面 | 获取变更申请信息和变更列表 |
| `AtomBudgetRpc` | 预算服务 (Atom) | ContextAspect | 获取预估报价单 |
| `EscrowDomain` / `EscrowRpc` | 存管服务 | ContextAspect | 获取存管账户开户信息 |
| `OrderStandardQueryRpc` | 工单标准查询 | 两个切面 | 获取套餐信息（2.5 流程） |
| `FundInfoService` | 款项服务 | DetailAspect | 获取关联款项实收金额 |
| `AuditRpc` | 审计服务 | DetailAspect | 获取风控审核信息 |
| `CeresRpc` | 服务者中心 | DetailAspect | 获取设计师人员信息 |
| `MdmDataRpc` / `MdmRpc` | MDM 主数据 | ContextAspect | 获取分公司信息 |
| `HomeOrderDataConversionService` | 工单转换 | 两个切面 | 获取正签/变更报价源数据 |
| `ContractDependentDataService` | 合同依赖数据 | 两个切面 | 构建个人合同报价数据 |

## 6. 关键设计模式

### 6.1 AOP + ThreadLocal 上下文模式

```mermaid
graph TD
    subgraph Pattern[设计模式：AOP + ThreadLocal Context]
        A1[注解标记方法] --> A2[AOP 切面拦截]
        A2 --> A3[初始化 ThreadLocal 上下文]
        A3 --> A4[并行数据加载到上下文]
        A4 --> A5[执行目标业务方法]
        A5 --> A6[目标方法从 ThreadLocal 读取数据]
        A6 --> A7[清除 ThreadLocal 上下文]
    end

    subgraph Benefits[收益]
        B1[业务 Service 无需感知数据加载逻辑]
        B2[数据加载可并行化]
        B3[上下文线程隔离，无并发问题]
        B4[异常路径也能清除上下文]
    end

    Pattern --> Benefits
```

**优势**：
- **关注点分离**：ContractCore 中的 Service（如 `ContractSaveDraftService`）只需通过 `ContractContextHandler.getContext()` 获取预加载数据，无需了解数据如何获取
- **并行加速**：通过 `ParallelTaskService` 并行执行多个 RPC 调用，显著降低总耗时
- **线程安全**：`ThreadLocal` 保证每个请求线程有独立的上下文副本

**风险与缓解**：
- **内存泄漏**：通过 `@After` + `@AfterThrowing` 双重保障清除
- **Long-lived 线程**：仅在 HTTP 请求线程中使用，不涉及线程池复用场景

### 6.2 策略分发模式 — 合同类型路由

报价信息获取（`dealPlanAllDTO`）和图纸信息获取（`dealDrawingDTO`）根据合同类型和业务类型走不同分支，本质上是一种策略分发：

| 合同类型 | 报价来源 | 图纸来源 |
|---------|---------|---------|
| 首期款 (ADVANCE) | 预估报价单 / `AtomBudgetRpc` | 不获取 |
| 正签 (PACKAGE_FORMAL) | `HomeOrderDataConversionService` | 2.5 团装走 `getGroupDrawingDTO`，其他走 `AtomDrawingRpc` |
| 变更 (PACKAGE_CHANGE) | 2.5 协同模式走 `buildAtomChangeQuotation`，其他走通用 | `AtomDrawingRpc.getChangeListDrawings` |
| 图纸合同 (DRAWING) | 通用报价 | `AtomDrawingRpc.listDrawings` |
| 个人 (PERSONAL) | `ContractDependentDataService` | `ContractSigningSourceRouter` 策略路由 |
| 设计合同 (DESIGN) | 不获取报价 | 不获取图纸 |
| 存管 (FUND_ESCROW) | 不获取报价 | 不获取图纸 |
| 解约 (TERMINAL) | 不获取报价 | 不获取图纸 |

### 6.3 首屏优化模式

`ContractDetailAspect` 引入 `isFirstScreen` 标记，实现分阶段加载：

- **首屏**（`isFirstScreen = true`）：仅加载项目信息、备件信息、设计费金额 3 项轻量数据，快速返回页面首屏所需内容
- **完整加载**（`isFirstScreen = false`）：并行加载全部 8 项数据，包括报价、图纸、审核等重量级数据

该模式有效降低了合同详情页面的首屏加载时间。

## 7. 与 ContractCore 模块的交互

ContractAspect 模块与 [ContractCore](ContractCore.md) 模块形成**数据准备 → 业务消费**的协作关系：

```mermaid
graph LR
    subgraph Aspect[ContractAspect 数据准备]
        CCA[ContractContextAspect]
        CDA[ContractDetailAspect]
    end

    subgraph Core[ContractCore 业务消费]
        subgraph Detail[ContractDetail]
            CDS[ContractDetailService]
            CBSCfg[ContractButtonConfigService]
            CHONC[ContractHomeOrderNoChangeService]
        end
        subgraph Validation[ContractValidation]
            CFCS[ContractFieldCheckService]
            WTCS[WorkerTypeCheckService]
        end
        subgraph Submission[ContractSubmission]
            CSSS[ContractSaveDraftService]
            CES[ContractEscrowService]
        end
        subgraph Signing[ContractSigning]
            CCSS[ContractCompanySignService]
            CSSf[ContractSelfSealService]
        end
        subgraph Creation[ContractCreation]
            CSCS[ContractScriptCreateService]
        end
    end

    CCA -->|预加载数据到 ContractContext| Submission
    CCA -->|预加载数据到 ContractContext| Signing
    CCA -->|预加载数据到 ContractContext| Validation
    CCA -->|预加载数据到 ContractContext| Creation
    CDA -->|预加载数据到 ContractDetailContext| Detail
```

ContractCore 中的 Service 通过 `ContractContextHandler.getContext()` 和 `ContractDetailContextHandler.getContext()` 获取切面预加载的数据，避免了重复的 RPC 调用。