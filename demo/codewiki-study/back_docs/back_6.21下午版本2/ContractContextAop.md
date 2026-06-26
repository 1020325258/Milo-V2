# ContractContextAop 模块

## 1. 模块概述

ContractContextAop 是合同子系统中基于 Spring AOP 的**数据预加载与上下文管理模块**。该模块通过切面编程机制，在合同保存草稿、提交、详情查询等核心操作执行前，自动从多个远程服务和数据源并行拉取项目信息、报价信息、图纸信息、存管账户信息等，填充到线程级上下文对象中，供下游业务逻辑直接消费。执行完毕后自动清理上下文，防止线程内存泄漏。

该模块的核心价值在于：
- **统一数据准备**：将合同操作所需的多源数据聚合逻辑从各业务方法中抽离，避免重复代码
- **并行化加载**：通过 `ParallelTaskService` 并行调用多个 RPC 服务，显著降低接口响应时间
- **线程安全隔离**：基于 `ThreadLocal` 的上下文管理确保并发场景下数据不串扰
- **参数预处理**：在数据准备阶段统一清理无效字段、校验前置条件，降低下游复杂度

## 2. 架构总览

```mermaid
graph TD
    subgraph ContractContextAop[ContractContextAop 模块]
        CA[ContractContextAspect]
        CH[ContractContextHandler]
        DA[ContractDetailAspect]
        DH[ContractDetailContextHandler]
    end

    subgraph Annotations[自定义注解]
        CDP[ContractDataPrepare 注解]
        CDDP[ContractDetailDataPrepare 注解]
    end

    subgraph ContextObjects[上下文对象]
        CC[ContractContext]
        CDC[ContractDetailContext]
    end

    subgraph DownstreamServices[下游合同服务]
        CS[ContractSaveDraftService]
        CE[ContractEscrowService]
        CSS[ContractCompanySignService]
        CD[ContractDetailService]
        CB[ContractButtonConfigService]
    end

    subgraph DataSources[外部数据源]
        PRJ[ProjectInfoReadService]
        QFS[QuotationFeignService]
        ADR[AtomDrawingRpc]
        ABR[AtomBudgetRpc]
        ACR[AtomChangeRpc]
        ESD[EscrowDomain]
        ORS[OrderStandardQueryRpc]
        HOD[HomeOrderDataConversionService]
    end

    CDP -->|触发| CA
    CDDP -->|触发| DA

    CA -->|读写| CH
    CH -->|持有| CC
    DA -->|读写| DH
    DH -->|持有| CDC

    CA -->|并行调用| PRJ
    CA -->|并行调用| QFS
    CA -->|并行调用| ADR
    CA -->|并行调用| ABR
    CA -->|并行调用| ACR
    CA -->|并行调用| ESD
    CA -->|并行调用| ORS
    CA -->|并行调用| HOD

    DA -->|并行调用| PRJ
    DA -->|并行调用| QFS
    DA -->|并行调用| ADR
    DA -->|并行调用| ACR
    DA -->|并行调用| ORS
    DA -->|并行调用| HOD

    CA -.->|数据准备后| CS
    CA -.->|数据准备后| CE
    DA -.->|数据准备后| CD
    DA -.->|数据准备后| CB
```

## 3. 核心组件详解

### 3.1 ContractContextAspect — 合同操作数据准备切面

**职责**：拦截所有标注了 `@ContractDataPrepare` 注解的合同保存/提交方法，在方法执行前完成全量数据准备。

**切面生命周期**：

```mermaid
sequenceDiagram
    participant Client as 客户端请求
    participant AOP as ContractContextAspect
    participant Handler as ContractContextHandler
    participant Parallel as ParallelTaskService
    participant RPC as 远程服务

    Client->>AOP: @Before - beforeHandle()
    AOP->>Handler: initContext() 创建 ThreadLocal 上下文
    AOP->>AOP: preHandleParam() 参数预处理
    AOP->>AOP: dealReContractLaunch() 处理重复发起撤销

    Note over AOP,Parallel: 并行数据准备阶段
    AOP->>Parallel: addNewTask - dealBaseInfo()
    AOP->>Parallel: addNewTask - dealPlanAllDTO()
    AOP->>Parallel: addNewTask - dealComboInfo()
    AOP->>Parallel: addNewTask - dealProjectInfo()
    AOP->>Parallel: addNewTask - getOperatorName()
    AOP->>Parallel: addNewTask - dealDrawingDTO()
    AOP->>Parallel: addNewTask - dealEscrowDTO()
    AOP->>Parallel: addNewTask - dealStandardDesignAmountDTO()
    AOP->>Parallel: addNewTask - dealMultiCompanyInfo()

    Parallel->>RPC: 并行调用多个远程服务
    RPC-->>Parallel: 返回结果
    Parallel-->>AOP: 全部任务完成

    AOP->>AOP: 后置处理(城市公司配置/合同模式/设计费合并)
    AOP-->>Client: 数据准备完成，执行目标方法

    Note over AOP,Handler: @After / @AfterThrowing
    AOP->>Handler: clearContext() 清除 ThreadLocal
```

**并行数据准备任务清单**：

| 任务 | 数据来源 | 条件 | 输出到 Context |
|------|---------|------|---------------|
| `dealBaseInfo` | ContractUnifyService | 始终执行 | `developerChannel` |
| `dealPlanAllDTO` | AtomBudgetRpc / HomeOrderDataConversionService / ContractDependentDataService | 按合同类型分支 | `planAllDTO`, `contractSourceDataBO`, `designQuoteFeeDTO` |
| `dealComboInfo` | OrderStandardQueryRpc | 仅 V2.5 流程 + 房产证业务 + 正签合同 | `comboDTOList` |
| `dealProjectInfo` | ProjectInfoReadService | 始终执行 | `projectInfoDTO` |
| `getOperatorName` | HomeAndPcCommonService | 始终执行 | `operatorName` |
| `dealDrawingDTO` | AtomDrawingRpc / ContractBusinessService | 正签/图纸/个人合同 + V2.5 | `drawingDTO` |
| `dealEscrowDTO` | EscrowDomain | 资金存管类合同 | `escrowInfo` |
| `dealStandardDesignAmountDTO` | HomeAndPcCommonService | 设计费合同 + 特定城市 | 回写到请求参数 |
| `dealMultiCompanyInfo` | EscrowRpc / MdmDataRpc / MdmRpc | 资金存管合同 | `contractCompanyList` |

**参数预处理逻辑 (`preHandleParam`)**：

```mermaid
graph TD
    A[接收 ContractReqDTO] --> B{是否合同提交请求}
    B -->|是| C[标记 contractSubmit=true]
    B -->|否| D[跳过]
    C --> E[处理签约信息 preHandleSignInfoParam]
    D --> E
    E --> F[处理承诺信息 promiseInfo]
    F --> G[处理项目信息 preHandleProjectParam]
    G --> H[参数预处理完成]

    subgraph PreHandleSignInfo[签约信息预处理]
        E1{签约形式?}
        E1 -->|公对公| E2[清空个人签约数据]
        E1 -->|个人签约| E3[清空公对公数据]
        E2 --> E4{是否有代理人}
        E3 --> E4
        E4 -->|无| E5[清空代理人数据]
        E4 -->|有| E6[保留]
        E5 --> E7{房产证类型}
        E6 --> E7
        E7 --> E8[清空其他权属证明字段]
    end
```

**报价信息获取的分支策略 (`dealPlanAllDTO`)**：

```mermaid
graph TD
    Start[开始获取报价] --> CT{合同类型}
    CT -->|首期款| ADV[首期款分支]
    CT -->|正签/变更/图纸/个人| STD[标准分支]
    CT -->|其他| SKIP[跳过]

    ADV --> RF{翻新全案?}
    RF -->|是| SKIP
    RF -->|否| APQ{支持预估报价?}
    APQ -->|是| APQ_RPC[调用报价单接口校验]
    APQ -->|否| ADV_CALC[本地计算预估合同额]

    STD --> CO{变更订单+V2.5?}
    CO -->|是| CHG[buildAtomChangeQuotation]
    CO -->|否| PER{个人合同?}
    PER -->|是| PER_Q[queryPersonalQuoteInfoV2]
    PER -->|否| COMMON[通用报价获取 contractSourceDate]

    CHG --> SET[设置到 context]
    PER_Q --> SET
    COMMON --> SET
    ADV_CALC --> SET
```

**关键设计决策**：

1. **流程版本判断（V2.5）**：通过 `commonBusinessService.isPROCESS_V2_5()` 区分新旧流程，V2.5 流程走协同报价、变更报价等新逻辑
2. **业务类型细分**：通过 `businessType` 区分房产证、整装、翻新全案等业务，不同业务的数据准备路径差异显著
3. **设计费来源合并**：正签合同发起时，如果设计费来自报价，则将报价中的设计费信息回写到请求参数，实现数据对齐

### 3.2 ContractContextHandler — 合同上下文持有者

**职责**：基于 `ThreadLocal<ContractContext>` 提供线程安全的上下文存取，作为切面与下游业务之间的数据桥梁。

**核心机制**：

```mermaid
classDiagram
    class ContractContextHandler {
        -ThreadLocal~ContractContext~ CONTEXT
        +initContext() void
        +clearContext() void
        +getContext() ContractContext
        +setContractReq(ContractReqDTO) void
        +getContractReq() ContractReqDTO
        +setProjectInfo(ProjectInfoDTO) void
        +getProjectInfo() ProjectInfoDTO
        +setPlanAllDTO(PlanAllDTO) void
        +getPlanAllDTO() PlanAllDTO
        +setContractSourceDataBO(ContractSourceDataBO) void
        +getContractSourceDataBO() ContractSourceDataBO
        +setOperatorName(String) void
        +getOperatorName() String
        +setContractCityCompanyInfo(ContractCityCompanyInfo) void
        +getContractCityCompanyInfo() ContractCityCompanyInfo
        +setDrawingDTO(DeliverDrawingDTO) void
        +getDrawingDTO() DeliverDrawingDTO
    }

    class ContractContext {
        -ProjectInfoDTO projectInfoDTO
        -PlanAllDTO planAllDTO
        -ContractSourceDataBO contractSourceDataBO
        -ContractReqDTO contractReq
        -ContractCityCompanyInfo contractCityCompanyInfo
        -DrawingDTO.DeliverDrawingDTO drawingDTO
        -ContractContextEscrowInfo escrowInfo
        -List~ContractCompanyAspectInfo~ contractCompanyList
        -DesignQuoteFeeDTO designQuoteFeeDTO
        -List~ComboDTO~ comboDTOList
        -String operatorName
        -boolean processV25
        -Byte businessType
        -boolean developerChannel
    }

    ContractContextHandler --> ContractContext : ThreadLocal 持有
```

**设计要点**：
- **静态方法模式**：所有方法均为 `static`，任何业务代码均可通过 `ContractContextHandler.getContext()` 获取当前线程上下文，无需注入
- **防御性空值检查**：getter 方法对 `CONTEXT.get() == null` 进行判断，避免切面未执行或异常时 NPE
- **生命周期管理**：由切面的 `@Before` 和 `@After`/`@AfterThrowing` 保证 `init` 和 `clear` 配对，避免 ThreadLocal 泄漏

### 3.3 ContractDetailAspect — 合同详情查询数据准备切面

**职责**：拦截标注了 `@ContractDetailDataPrepare` 注解的合同详情查询方法，在详情展示前预加载所需数据。

**与 ContractContextAspect 的差异**：

| 维度 | ContractContextAspect | ContractDetailAspect |
|------|----------------------|---------------------|
| 触发注解 | `@ContractDataPrepare` | `@ContractDetailDataPrepare` |
| 上下文类型 | `ContractContext` | `ContractDetailContext` |
| Handler | `ContractContextHandler` | `ContractDetailContextHandler` |
| 核心场景 | 合同保存/提交 | 合同详情查询 |
| 首屏优化 | 无 | 支持 `isFirstScreen` 分级加载 |
| 额外数据 | 存管账户、多公司信息 | 款项实收、风控审核、变更范围、备件信息 |

**首屏分级加载策略**：

```mermaid
graph TD
    Start[详情查询请求] --> FS{isFirstScreen?}

    FS -->|首屏=true| FIRST[轻量加载]
    FS -->|非首屏| FULL[全量加载]

    FIRST --> F1[项目信息]
    FIRST --> F2[备件信息]
    FIRST --> F3[设计费金额]

    FULL --> F1
    FULL --> F2
    FULL --> F3
    FULL --> F4[报价信息]
    FULL --> F5[套餐信息]
    FULL --> F6[款项实收金额]
    FULL --> F7[图纸信息]
    FULL --> F8[风控审核信息]
```

首屏模式下只加载首屏渲染所必需的 3 项数据（项目信息、备件信息、设计费金额），其余数据延迟到非首屏请求时再加载，优化首屏响应速度。

**变更报价获取 (`buildAtomChangeQuotation`)**：

该方法处理 V2.5 协同签约模式下的变更合同报价获取，与 `ContractContextAspect` 中的同名方法逻辑相似但有细微差异：

```mermaid
graph TD
    Start[变更报价获取] --> SCOPE[获取变更范围列表]
    SCOPE --> HAS_Q{包含报价变更?}

    HAS_Q -->|是| PARALLEL[并行执行]
    HAS_Q -->|否| PRE_BILL[获取变更前报价]

    PARALLEL --> P1[quoteBillDiff.getQuoteBill]
    PARALLEL --> P2[获取变更硬装PDF]

    P1 --> CONVERT[转换为 PlanAllDTO]
    P2 --> CONVERT
    PRE_BILL --> CONVERT

    CONVERT --> RESULT[返回 PlanAllDTO]

    subgraph DifferenceWithContractAspect[与 ContractContextAspect 的差异]
        D1[额外获取图纸变更范围]
        D2[设置 drawingUrl 到 context]
        D3[设置 atomChangeScopeList 到 context]
    end
```

关键差异：`ContractDetailAspect.buildAtomChangeQuotation` 额外处理了 `ChangeScopeEnum.DRAWING` 的变更范围，将图纸 URL 和变更范围列表设置到详情上下文中，用于详情页面展示变更对比信息。

### 3.4 ContractDetailContextHandler — 合同详情上下文持有者

**职责**：基于 `ThreadLocal<ContractDetailContext>` 提供合同详情查询场景的线程安全上下文管理。

与 `ContractContextHandler` 结构完全对称，但持有不同的上下文对象 `ContractDetailContext`，包含详情场景特有的字段：

- `drawingUrl`：变更图纸 URL（详情展示变更对比用）
- `atomChangeScopeList`：变更范围列表（报价变更/图纸变更）
- `firstScreen`：是否首屏加载标志
- `preQuotationDTO`：首期款预报价信息
- `relateFundInfo`：关联款项信息
- `auditDetailDTO`：风控审核详情
- `changeOrderList`：变更单列表
- `attachInfoDetail`：备件详情信息
- `designSignPriceInfo`：设计费签约价格信息

## 4. 模块间依赖关系

```mermaid
graph LR
    subgraph Upstream[上游调用方]
        SDS[ContractSaveDraftService]
        SES[ContractEscrowService]
        SCS[ContractCompanySignService]
        SSS[ContractSelfSealService]
        CDS[ContractDetailService]
        CBC[ContractButtonConfigService]
    end

    subgraph ContractContextAop[ContractContextAop]
        CA[ContractContextAspect]
        CH[ContractContextHandler]
        DA[ContractDetailAspect]
        DH[ContractDetailContextHandler]
    end

    subgraph Dependencies[被依赖模块]
        CU[ContractUnifyService]
        CCU[ChangeContractUnifyService]
        HC[HomeAndPcCommonService]
        CB[CommonBusinessService]
        CCS[CommonContractService]
        CDS2[ContractDependentDataService]
        CSR[ContractSigningSourceRouter]
    end

    subgraph RPC_Services[RPC 服务]
        PIS[ProjectInfoReadService]
        QFS[QuotationFeignService]
        ADR[AtomDrawingRpc]
        ABR[AtomBudgetRpc]
        ACR[AtomChangeRpc]
        ED[EscrowDomain]
        ORS[OrderStandardQueryRpc]
        HOD[HomeOrderDataConversionService]
        MDR[MdmDataRpc]
        MR[MdmRpc]
        ER[EscrowRpc]
        PS[ParallelTaskService]
    end

    SDS -->|DataPrepare 注解| CA
    SES -->|DataPrepare 注解| CA
    SCS -->|DataPrepare 注解| CA
    SSS -->|DataPrepare 注解| CA

    CDS -->|DetailDataPrepare 注解| DA
    CBC -->|DetailDataPrepare 注解| DA

    CA --> CH
    DA --> DH

    CA --> CU
    CA --> CCU
    CA --> HC
    CA --> CB
    CA --> CCS
    CA --> CDS2
    CA --> CSR

    DA --> CU
    DA --> CCU
    DA --> HC
    DA --> CB
    DA --> CDS2
    DA --> CSR

    CA --> PIS
    CA --> QFS
    CA --> ADR
    CA --> ABR
    CA --> ACR
    CA --> ED
    CA --> ORS
    CA --> HOD
    CA --> MDR
    CA --> MR
    CA --> ER
    CA --> PS

    DA --> PIS
    DA --> QFS
    DA --> ADR
    DA --> ACR
    DA --> ORS
    DA --> HOD
    DA --> PS
```

**关键依赖说明**：

| 依赖服务 | 用途 | 被哪些切面使用 |
|---------|------|--------------|
| `ProjectInfoReadService` | 获取项目基础信息（客户、地址、公司编码） | CA + DA |
| `QuotationFeignService` | 查询套餐信息和设计费配置 | CA + DA |
| `AtomDrawingRpc` | 获取图纸列表（正签/变更/个人） | CA + DA |
| `AtomBudgetRpc` | 获取报价单信息（首期款预报价） | CA |
| `AtomChangeRpc` | 获取变更申请信息和变更范围 | CA + DA |
| `EscrowDomain` | 查询资金存管账户开户信息 | CA |
| `ParallelTaskService` | 并行任务编排和执行 | CA + DA |
| `ContractUnifyService` | 合同业务工具方法（字段配置、公司信息等） | CA + DA |
| `ChangeContractUnifyService` | 变更合同专用工具（报价差异计算等） | CA + DA |
| `ContractDependentDataService` | 个人合同报价数据构建 | CA + DA |
| `ContractSigningSourceRouter` | 个人合同签约来源路由（报价单/子订单/变更单） | CA + DA |
| `HomeOrderDataConversionService` | 家装订单数据转换（通用报价获取） | CA + DA |

## 5. 数据流详解

### 5.1 合同保存/提交数据流

```mermaid
graph TD
    REQ[客户端请求: 合同保存/提交] --> AOP[ContractContextAspect.beforeHandle]

    AOP --> INIT[initContext: 创建 ContractContext]
    INIT --> PRE[preHandleParam: 参数预处理]
    PRE --> PRE1[签约信息清洗]
    PRE --> PRE2[承诺信息处理]
    PRE --> PRE3[项目信息默认值填充]

    PRE --> PARALLEL[并行数据准备]

    subgraph ParallelTasks[并行任务]
        T1[项目信息]
        T2[报价信息]
        T3[套餐信息]
        T4[基础信息]
        T5[操作人姓名]
        T6[图纸信息]
        T7[存管账户]
        T8[设计费金额]
        T9[多公司信息]
    end

    PARALLEL --> T1
    PARALLEL --> T2
    PARALLEL --> T3
    PARALLEL --> T4
    PARALLEL --> T5
    PARALLEL --> T6
    PARALLEL --> T7
    PARALLEL --> T8
    PARALLEL --> T9

    T1 --> POST[后置处理]
    T2 --> POST
    T3 --> POST
    T4 --> POST
    T5 --> POST
    T6 --> POST
    T7 --> POST
    T8 --> POST
    T9 --> POST

    POST --> POST1[获取城市公司配置]
    POST --> POST2[计算合同模式]
    POST --> POST3[设计费合并处理]

    POST1 --> TARGET[执行目标方法: saveDraft/submit]
    POST2 --> TARGET
    POST3 --> TARGET

    TARGET --> CLEANUP[afterHandle: clearContext]
```

### 5.2 合同详情查询数据流

```mermaid
graph TD
    REQ[客户端请求: 合同详情] --> AOP[ContractDetailAspect.beforeHandle]
    AOP --> INIT[initContext: 创建 ContractDetailContext]
    INIT --> FS{isFirstScreen?}

    FS -->|是| LIGHT[轻量并行]
    FS -->|否| FULL[全量并行]

    LIGHT --> L1[项目信息]
    LIGHT --> L2[备件信息]
    LIGHT --> L3[设计费金额]

    FULL --> L1
    FULL --> L2
    FULL --> L3
    FULL --> F4[报价信息]
    FULL --> F5[套餐信息]
    FULL --> F6[款项实收]
    FULL --> F7[图纸信息]
    FULL --> F8[风控审核]

    L1 --> EXEC[执行目标方法: detail]
    L2 --> EXEC
    L3 --> EXEC
    F4 --> EXEC
    F5 --> EXEC
    F6 --> EXEC
    F7 --> EXEC
    F8 --> EXEC

    EXEC --> CLEANUP[afterHandle: clearContext]
```

### 5.3 上下文数据消费链路

```mermaid
graph LR
    subgraph DataPreparation[数据准备阶段 - 切面]
        A[ContractContextAspect]
    end

    subgraph ContextStorage[上下文存储]
        H[ContractContextHandler]
        C[ContractContext]
    end

    subgraph DataConsumption[数据消费阶段 - 业务服务]
        S1[ContractSaveDraftService]
        S2[ContractSubmitService]
        S3[ContractUnifyService]
        S4[ContractPdfBuildService]
    end

    A -->|填充| H
    H -->|ThreadLocal| C

    C -->|getProjectInfoDTO| S1
    C -->|getPlanAllDTO| S2
    C -->|getContractReq| S3
    C -->|getDrawingDTO| S4
    C -->|getOperatorName| S3
    C -->|getContractCityCompanyInfo| S3
```

## 6. 关键设计模式

### 6.1 AOP 拦截器模式

模块采用 `@Aspect` + 自定义注解的方式实现横切关注点的分离：

```mermaid
graph TD
    subgraph Pattern[AOP 拦截器模式]
        ANN[自定义注解 ContractDataPrepare] -->|标注| BIZ[业务方法: saveDraft/submit]
        ASPECT[ContractContextAspect] -->|拦截| BIZ
        ASPECT -->|Before 通知| PREPARE[数据准备]
        ASPECT -->|After 通知| CLEANUP[上下文清理]
        ASPECT -->|AfterThrowing 通知| CLEANUP_ERR[异常时清理]
    end
```

**优势**：业务方法（如 `ContractSaveDraftService.saveDraft`）只需加一行注解，即可获得完整的数据准备能力，无需感知数据来源和加载策略。

### 6.2 ThreadLocal 上下文模式

```mermaid
graph TD
    subgraph ThreadLocalPattern[ThreadLocal 上下文模式]
        REQ1[请求1 - Thread-A] -->|initContext| TL1[ThreadLocal Context-A]
        REQ2[请求2 - Thread-B] -->|initContext| TL2[ThreadLocal Context-B]
        REQ3[请求3 - Thread-C] -->|initContext| TL3[ThreadLocal Context-C]

        TL1 -->|getContext| BIZ1[业务方法 - Thread-A]
        TL2 -->|getContext| BIZ2[业务方法 - Thread-B]
        TL3 -->|getContext| BIZ3[业务方法 - Thread-C]

        BIZ1 -->|clearContext| TL1
        BIZ2 -->|clearContext| TL2
        BIZ3 -->|clearContext| TL3
    end
```

每个请求线程拥有独立的上下文副本，通过 `init → 使用 → clear` 的生命周期管理，确保线程安全且无内存泄漏。

### 6.3 并行任务编排模式

```mermaid
sequenceDiagram
    participant Main as 主线程
    participant PTS as ParallelTaskService
    participant T1 as 任务1-项目信息
    participant T2 as 任务2-报价信息
    participant T3 as 任务3-图纸信息

    Main->>PTS: newParallelTasks()
    Main->>PTS: addNewTask(任务1)
    Main->>PTS: addNewTask(任务2)
    Main->>PTS: addNewTask(任务3)
    Main->>PTS: execTasks()

    par 并行执行
        PTS->>T1: 执行
        PTS->>T2: 执行
        PTS->>T3: 执行
    end

    T1-->>PTS: 完成
    T2-->>PTS: 完成
    T3-->>PTS: 完成

    PTS-->>Main: awaitTasksResult - 全部完成
```

所有数据准备任务通过 `ParallelTaskService` 并行执行，使用 `awaitTasksResult` 阻塞等待全部完成后再继续。这将原本串行的多次 RPC 调用（可能耗时数秒）压缩到最慢单次调用的时间。

### 6.4 策略分支模式（报价获取）

报价信息获取根据合同类型、业务类型、流程版本的不同组合，走不同的数据获取策略。这是一种**隐式策略模式**，通过条件分支而非策略接口实现：

| 条件组合 | 获取策略 | 数据来源 |
|---------|---------|---------|
| 首期款 + 非翻新全案 + 支持预估报价 | 报价单实时校验 | `AtomBudgetRpc.getPreQuotationByBillCode` |
| 首期款 + 非翻新全案 + 不支持预估报价 | 本地计算 | `HomeAndPcCommonService.getExpectContractAmount` |
| 变更合同 + V2.5 协同 | 变更报价构建 | `ChangeContractUnifyService.getQuoteBillDiff` |
| 个人合同 | 个人报价查询 | `ContractDependentDataService.queryPersonalQuoteInfoV2` |
| 其他（正签/图纸等） | 通用报价获取 | `HomeOrderDataConversionService.contractSourceDate` |

## 7. 关注点与设计约束

### 7.1 线程安全性

- `ContractContext` 和 `ContractDetailContext` 通过 `ThreadLocal` 存储，天然线程安全
- 切面 `@After` 和 `@AfterThrowing` 均调用 `clearContext()`，确保异常场景下也不泄漏
- `ContractContextHandler` 的 getter 方法进行空值判断，防止切面未触发时调用方 NPE

### 7.2 性能优化

- **并行加载**：9 项数据准备任务并行执行，理论耗时 = max(单任务耗时)，而非 sum(所有任务耗时)
- **条件短路**：每个数据准备方法内部根据合同类型、业务类型等条件提前 `return`，避免不必要的 RPC 调用
- **首屏分级**：`ContractDetailAspect` 支持首屏轻量加载，首屏只加载 3 项核心数据

### 7.3 可维护性风险

- **上下文膨胀**：`ContractContext` 承载了越来越多的字段（当前 13+ 个），随着业务扩展可能继续膨胀
- **隐式依赖**：下游业务通过 `ContractContextHandler.getContext()` 静态方法获取数据，这种隐式依赖难以在编译期发现
- **分支复杂度**：`dealPlanAllDTO` 方法内含多层嵌套条件分支（合同类型 × 业务类型 × 流程版本），维护难度较高
- **代码重复**：`ContractContextAspect` 和 `ContractDetailAspect` 在报价获取、图纸获取等逻辑上有大量相似代码，但因上下文类型不同难以直接复用

## 8. 与其他模块的关系

| 相关模块 | 关系 | 说明 |
|---------|------|------|
| [ContractOperations](ContractOperations.md) | 上游消费方 | `ContractSaveDraftService`、`ContractEscrowService` 等通过注解触发数据准备 |
| [ChangeContractStrategy](ChangeContractStrategy.md) | 间接依赖 | 变更合同策略执行前，由切面预加载变更报价数据 |
| [SigningSourceBinding](SigningSourceBinding.md) | 数据提供 | `ContractSigningSourceRouter` 被切面调用，为个人合同提供图纸数据 |
| [ContractFieldValidation](ContractFieldValidation.md) | 后置消费 | 字段校验依赖切面预填充的上下文数据 |
| [ContractPdfGeneration](ContractPdfGeneration.md) | 数据消费 | PDF 生成服务通过 `ContractContextHandler` 获取报价、图纸等数据 |
