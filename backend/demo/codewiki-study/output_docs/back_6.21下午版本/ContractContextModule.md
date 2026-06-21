# ContractContextModule 模块文档

## 1. 模块概述

ContractContextModule 是合同系统的**数据预处理核心模块**，基于 Spring AOP 切面编程实现，在合同业务操作（保存/提交/查询详情）执行前，自动完成多源异构数据的并行采集与上下文装配。该模块通过 ThreadLocal 机制管理请求级别的上下文数据，使下游业务组件无需重复查询外部系统，实现数据准备与业务逻辑的解耦。

### 核心职责

- **数据预编排**：在合同保存/提交前，并行拉取项目信息、报价数据、图纸信息、存管账户等十余种外部数据源
- **参数预处理**：对前端入参进行清洗与标准化（签约人信息、附件字段、设计费参数等）
- **上下文传递**：通过 ThreadLocal 在 AOP 切面与业务方法之间共享已准备好的数据
- **详情查询优化**：为合同详情查询提供首屏/非首屏的分层数据加载策略

## 2. 架构总览

```mermaid
graph TD
    subgraph ControllerLayer[Controller 层]
        ContractSave[合同保存/提交]
        ContractDetail[合同详情查询]
    end

    subgraph AOPAspect[ContractContextModule]
        CCA[ContractContextAspect<br/>保存提交切面]
        CDA[ContractDetailAspect<br/>详情查询切面]
        CCH[ContractContextHandler<br/>提交上下文持有者]
        CDCH[ContractDetailContextHandler<br/>详情上下文持有者]
    end

    subgraph Annotation[自定义注解]
        CDP["@ContractDataPrepare"]
        CDDP["@ContractDetailDataPrepare"]
    end

    subgraph ContextBO[上下文数据对象]
        CC[ContractContext]
        CDC[ContractDetailContext]
    end

    subgraph Downstream[下游业务组件]
        CU[ContractUnifyService]
        CS[ContractSaveDraftService]
        CSub[ContractSubmitService]
        CD[ContractDetailService]
    end

    ContractSave --> CDP
    CDP --> CCA
    CCA --> CCH
    CCH --> CC
    CC --> Downstream

    ContractDetail --> CDDP
    CDDP --> CDA
    CDA --> CDCH
    CDCH --> CDC
    CDC --> Downstream
```

## 3. 核心组件详解

### 3.1 ContractContextAspect — 保存/提交数据预处理切面

该切面拦截所有标注 `@ContractDataPrepare` 注解的方法，在业务逻辑执行前完成数据准备，执行后清理上下文。

#### 生命周期

```mermaid
sequenceDiagram
    participant Caller as 调用方
    participant Aspect as ContractContextAspect
    participant Handler as ContractContextHandler
    participant Parallel as ParallelTaskService
    participant RPC as 外部 RPC 服务

    Caller->>Aspect: @Before 触发
    Aspect->>Handler: initContext()
    Aspect->>Aspect: preHandleParam(ContractReqDTO)
    Aspect->>Aspect: dealReContractLaunch()
    Aspect->>Handler: setContractReq(reqDTO)

    Aspect->>Parallel: 创建并行任务组
    Note over Aspect,RPC: 9个并行任务同时执行
    Aspect->>RPC: dealBaseInfo()
    Aspect->>RPC: dealPlanAllDTO()
    Aspect->>RPC: dealComboInfo()
    Aspect->>RPC: dealProjectInfo()
    Aspect->>RPC: getOperatorName()
    Aspect->>RPC: dealDrawingDTO()
    Aspect->>RPC: dealEscrowDTO()
    Aspect->>RPC: dealStandardDesignAmountDTO()
    Aspect->>RPC: dealMultiCompanyInfo()
    Parallel-->>Aspect: 全部完成

    Aspect->>Aspect: 设置城市分公司配置
    Aspect->>Aspect: 计算合同模式
    Aspect->>Aspect: 设计费预处理
    Aspect-->>Caller: 数据准备完成，执行业务方法

    Caller->>Aspect: @After 触发
    Aspect->>Handler: clearContext()
```

#### 并行数据采集任务清单

| 任务 | 方法 | 数据来源 | 适用条件 |
|------|------|---------|---------|
| 基础信息 | `dealBaseInfo()` | ContractUnifyService | 所有合同类型 |
| 报价信息 | `dealPlanAllDTO()` | 中控报价 / HomeOrderDataConversion | 正签/变更/图纸/个人 |
| 套餐信息 | `dealComboInfo()` | OrderStandardQueryRpc | 2.5流程 & 户证业务 & 正签 |
| 项目信息 | `dealProjectInfo()` | ProjectInfoReadService | 所有合同类型 |
| 操作人姓名 | `getOperatorName()` | HomeAndPcCommonService | 所有合同类型 |
| 图纸信息 | `dealDrawingDTO()` | AtomDrawingRpc / ContractBusinessService | 正签/图纸/个人 & 2.5 |
| 存管账户 | `dealEscrowDTO()` | EscrowDomain | 含存管的合同类型 |
| 设计费金额 | `dealStandardDesignAmountDTO()` | HomeAndPcCommonService | 设计合同 & 特定城市 |
| 合同主体 | `dealMultiCompanyInfo()` | FundEscrowService / MdmDataRpc | 存管协议合同 |

#### 参数预处理逻辑 (`preHandleParam`)

```mermaid
flowchart TD
    Start[入参 ContractReqDTO] --> IsSubmit{是否提交请求?}
    IsSubmit -->|是| SetSubmit[标记 contractSubmit=true]
    IsSubmit -->|否| SignCheck

    SetSubmit --> SignCheck{有签约信息?}
    SignCheck -->|是| PreSign[签约参数预处理]
    SignCheck -->|否| PromiseCheck

    PreSign --> ObjectType{签约对象类型?}
    ObjectType -->|公对公| ClearPerson[清空个人签约数据]
    ObjectType -->|个人| ClearCompany[清空公对公数据]
    ClearPerson --> AgentCheck
    ClearAgent[无代理人] --> ClearAgentData[清空代理人数据]
    ClearCompany --> AgentCheck

    AgentCheck{有代理人?}
    AgentCheck -->|无| ClearAgentData
    AgentCheck -->|有| EntrustCheck

    EntrustCheck --> ChannelCheck{签约渠道?}
    ChannelCheck -->|线上| ClearOffline[清空线下合同字段]
    ChannelCheck -->|线下| HouseProveCheck

    HouseProveCheck --> HouseType{房产证明类型}
    HouseType -->|房产证| ClearOthers1[清空其他权属证明]
    HouseType -->|其他| ClearOthers2[清空房产证相关]
    HouseType -->|购房合同| ClearOthers3[清空其他类型]
    HouseType -->|契税票| ClearOthers4[清空其他类型]

    ClearOffline --> PromiseCheck
    ClearOthers1 --> PromiseCheck
    ClearOthers2 --> PromiseCheck
    ClearOthers3 --> PromiseCheck
    ClearOthers4 --> PromiseCheck

    PromiseCheck{有承诺信息?}
    PromiseCheck -->|是| DesignFee{未约定设计费?}
    DesignFee -->|是| ClearDesignAmount[清空设计费金额]
    DesignFee -->|否| SetDesignAmount[同步设计费到项目信息]
    ClearDesignAmount --> MaterialCheck
    SetDesignAmount --> MaterialCheck

    MaterialCheck{甲供材料模式?}
    MaterialCheck -->|是| ClearMaterial[清空材料清单]
    MaterialCheck -->|否| ProjectParam

    PromiseCheck -->|否| ProjectParam
    ClearMaterial --> ProjectParam
    ProjectParam[参数项目信息处理] --> End[预处理完成]
```

#### 报价信息获取策略 (`dealPlanAllDTO`)

```mermaid
flowchart TD
    Start[开始] --> ContractType{合同类型?}

    ContractType -->|首期款| Advance{翻新全案?}
    Advance -->|是| Return1[直接返回，不查报价]
    Advance -->|否| PreQuotation{支持预估报价?}
    PreQuotation -->|是| DealAdvancePre[dealAdvancePreQuotation<br/>校验报价单一致性]
    PreQuotation -->|否| ComboPrice[查询套餐价格<br/>计算预估合同额]

    ContractType -->|正签/图纸/个人/变更| PlanAllTypes[进入通用报价流程]

    PlanAllTypes --> V25House{2.5流程且变更?}
    V25House -->|是| AtomChange[buildAtomChangeQuotation<br/>中控变更报价]

    V25House -->|否| Personal{个人合同?}
    Personal -->|是| PersonalQuote[queryPersonalQuoteInfoV2<br/>个人C端报价]

    Personal -->|否| GeneralQuote[通用报价准备<br/>homeOrderDataConversionService<br/>contractSourceDate]
    GeneralQuote --> DesignFeeInfo{正签且有设计费?}
    DesignFeeInfo -->|是| BuildDesignQuote[构建 DesignQuoteFeeDTO]
    DesignFeeInfo -->|否| SetContext

    AtomChange --> SetContext
    PersonalQuote --> SetContext
    BuildDesignQuote --> SetContext
    SetContext[设置到 ContractContext] --> End[完成]
```

#### 异常与清理机制

切面通过 `@After` 和 `@AfterThrowing` 两个通知确保 ThreadLocal 被正确清理，防止内存泄漏：

- **正常完成**：`@After` 触发 `clearContext()`
- **异常抛出**：`@AfterThrowing` 触发 `clearContext()`
- **线程安全**：每个请求线程持有独立的 `ContractContext` 实例，互不干扰

### 3.2 ContractContextHandler — 提交上下文持有者

基于 `ThreadLocal<ContractContext>` 的静态工具类，为合同保存/提交流程提供上下文的存取能力。

#### 存储结构

```mermaid
classDiagram
    class ContractContextHandler {
        -ThreadLocal~ContractContext~ CONTEXT$
        +initContext()$
        +clearContext()$
        +getContext() ContractContext$
        +setContractReq(ContractReqDTO)$
        +getContractReq() ContractReqDTO$
        +setProjectInfo(ProjectInfoDTO)$
        +getProjectInfo() ProjectInfoDTO$
        +setPlanAllDTO(PlanAllDTO)$
        +getPlanAllDTO() PlanAllDTO$
        +setOperatorName(String)$
        +getOperatorName() String$
        +setContractCityCompanyInfo(ContractCityCompanyInfo)$
        +getContractCityCompanyInfo() ContractCityCompanyInfo$
        +setDrawingDTO(DeliverDrawingDTO)$
        +getDrawingDTO() DeliverDrawingDTO$
        +getContractSourceDataBO() ContractSourceDataBO$
    }

    class ContractContext {
        -ContractReqDTO contractReq
        -ProjectInfoDTO projectInfoDTO
        -PlanAllDTO planAllDTO
        -DrawingDTO.DeliverDrawingDTO drawingDTO
        -ContractSourceDataBO contractSourceDataBO
        -DesignQuoteFeeDTO designQuoteFeeDTO
        -ContractCityCompanyInfo contractCityCompanyInfo
        -ContractContextEscrowInfo escrowInfo
        -String operatorName
        -boolean processV25
        -Byte businessType
        -boolean developerChannel
        -List~ComboDTO~ comboDTOList
        -List~ContractCompanyAspectInfo~ contractCompanyList
    }

    ContractContextHandler --> ContractContext : ThreadLocal 存储
```

#### 设计要点

- **全静态方法**：无需注入，任何层级的组件均可直接调用
- **空值防护**：getter 方法在 `CONTEXT.get()` 为 null 时返回 null，而非抛出 NPE
- **生命周期由切面管理**：调用方无需手动 init/clear

### 3.3 ContractDetailAspect — 详情查询数据预处理切面

该切面拦截所有标注 `@ContractDetailDataPrepare` 注解的方法，为合同详情查询准备数据。与 `ContractContextAspect` 的核心差异：

| 维度 | ContractContextAspect | ContractDetailAspect |
|------|----------------------|---------------------|
| 用途 | 合同保存/提交 | 合同详情查询 |
| 注解 | `@ContractDataPrepare` | `@ContractDetailDataPrepare` |
| 上下文类型 | ContractContext | ContractDetailContext |
| 参数来源 | ContractReqDTO（第一个参数） | 方法签名的第2-8个参数 |
| 分层加载 | 无 | 首屏/非首屏分层加载 |
| 额外数据 | 存管账户、合同主体信息 | 款项实收、风控审核、变更单列表 |

#### 分层加载策略

```mermaid
graph TD
    subgraph AlwaysLoad[始终加载 - 首屏+非首屏]
        P[项目信息 ProjectInfoDTO]
        A[备件信息 AttachInfoDetail]
        SD[设计费金额 DesignSignPriceInfo]
    end

    subgraph DeferredLoad[延迟加载 - 仅非首屏]
        Q[报价信息 PlanAllDTO]
        C[套餐信息 ComboDTO列表]
        F[款项实收 FundInfo]
        D[图纸信息 DeliverDrawingDTO]
        AU[风控审核 AuditDetailDto + 变更单列表]
    end

    Init[beforeHandle 触发] --> AlwaysLoad
    Init --> isFirstScreen{isFirstScreen?}
    isFirstScreen -->|true| Parallel1[并行执行3个任务]
    isFirstScreen -->|false| Parallel2[并行执行8个任务]
    Parallel1 --> Await1[等待完成]
    Parallel2 --> Await2[等待完成]
```

#### 变更报价构建 (`buildAtomChangeQuotation`)

```mermaid
flowchart TD
    Start[变更报价构建] --> GetChange[getChangeApplyInfo<br/>获取变更申请信息]
    GetChange --> HasQuotation{变更范围含报价?}

    HasQuotation -->|是| Parallel[并行获取]
    Parallel --> QuoteDiff[getQuoteBillDiff<br/>报价差异]
    Parallel --> ChangePdf[changeHardDecorationFileData<br/>硬装变更PDF]

    HasQuotation -->|否| PreQuoteBill[getPreQuoteBill<br/>变更前报价]

    QuoteDiff --> Convert[atomChangeQuotationConvertToPlanAllDTO<br/>转换为PlanAllDTO]
    ChangePdf --> Convert
    PreQuoteBill --> Convert

    Convert --> HasDrawing{变更范围含图纸?}
    HasDrawing -->|是| SetDrawing[设置 drawingUrl]
    HasDrawing -->|否| SetScope

    SetDrawing --> SetScope[设置变更范围列表]
    SetScope --> Return[返回 PlanAllDTO]
```

### 3.4 ContractDetailContextHandler — 详情上下文持有者

基于 `ThreadLocal<ContractDetailContext>` 的静态工具类，结构与 `ContractContextHandler` 类似，但持有的是 `ContractDetailContext` 实例。

#### 与 ContractContextHandler 的对比

| 特性 | ContractContextHandler | ContractDetailContextHandler |
|------|----------------------|---------------------------|
| 上下文类型 | ContractContext | ContractDetailContext |
| 管理切面 | ContractContextAspect | ContractDetailAspect |
| 额外字段 | escrowInfo, contractCompanyList, operatorName | drawingUrl, atomChangeScopeList, isFirstScreen |
| 用途场景 | 写操作（保存/提交） | 读操作（详情查询） |
| 空值防护 | 有 | getter 缺少空值防护（潜在风险点） |

## 4. 模块间依赖关系

```mermaid
graph LR
    subgraph ContractContextModule[ContractContextModule]
        CCA[ContractContextAspect]
        CDA[ContractDetailAspect]
        CCH[ContractContextHandler]
        CDCH[ContractDetailContextHandler]
    end

    subgraph ContractCore[ContractCore 模块]
        CU[ContractUnifyService]
        CCU[ChangeContractUnifyService]
        CS[ContractDetailService]
        CB[ContractBusinessService]
        CC[CommonContractService]
    end

    subgraph ExternalServices[外部服务]
        PIS[ProjectInfoReadService]
        QFS[QuotationFeignService]
        ACR[AtomChangeRpc]
        ABR[AtomBudgetRpc]
        ADR[AtomDrawingRpc]
        ED[EscrowDomain]
        FES[FundEscrowService]
        MDR[MdmDataRpc]
        MR[MdmRpc]
        ER[EscrowRpc]
        OSR[OrderStandardQueryRpc]
    end

    subgraph CommonServices[公共服务]
        PTS[ParallelTaskService]
        CBS[CommonBusinessService]
        HPC[HomeAndPcCommonService]
        CVS[ContractConfigVersionService]
        ACS[AttachCommonService]
        HODC[HomeOrderDataConversionService]
        CDS[ContractDependentDataService]
    end

    subgraph ApolloConfig[配置]
        CAC[ContractApolloConfig]
    end

    CCA --> CU
    CCA --> CCU
    CCA --> CS
    CCA --> CB
    CCA --> CC
    CCA --> PIS
    CCA --> QFS
    CCA --> ACR
    CCA --> ABR
    CCA --> ADR
    CCA --> ED
    CCA --> FES
    CCA --> MDR
    CCA --> MR
    CCA --> ER
    CCA --> PTS
    CCA --> CBS
    CCA --> HPC
    CCA --> CVS
    CCA --> ACS
    CCA --> HODC
    CCA --> CDS
    CCA --> CAC
    CCA --> OSR

    CDA --> CU
    CDA --> CCU
    CDA --> CS
    CDA --> CB
    CDA --> CC
    CDA --> PIS
    CDA --> QFS
    CDA --> ACR
    CDA --> ABR
    CDA --> ADR
    CDA --> PTS
    CDA --> CBS
    CDA --> ACS
    CDA --> HODC
    CDA --> CDS
    CDA --> CAC
    CDA --> OSR
    CDA --> HPC

    CCH --> ContractContext[ContractContext BO]
    CDCH --> ContractDetailContext[ContractDetailContext BO]
```

## 5. 数据流全景

### 5.1 合同保存/提交数据流

```mermaid
flowchart TD
    subgraph Input[输入]
        Req[ContractReqDTO<br/>前端请求参数]
        HttpReq[HttpServletRequest<br/>URI 判断是否提交]
    end

    subgraph ContextModule[ContractContextModule]
        PreHandle[preHandleParam<br/>参数预处理]
        Parallel[ParallelTaskService<br/>并行数据采集]
        Context[ContractContext<br/>装配后的上下文]
    end

    subgraph DataSources[外部数据源]
        Project[项目系统<br/>ProjectInfoReadService]
        Quotation[报价系统<br/>QuotationFeignService]
        Atom[中控系统<br/>AtomChangeRpc/BudgetRpc/DrawingRpc]
        Escrow[存管系统<br/>EscrowDomain]
        Mdm[MDM主数据<br/>MdmDataRpc/MdmRpc]
        Order[订单标准查询<br/>OrderStandardQueryRpc]
    end

    subgraph Output[输出]
        DownstreamSvc[下游服务<br/>ContractSubmitService<br/>ContractSaveDraftService]
    end

    Req --> PreHandle
    HttpReq --> PreHandle
    PreHandle --> Parallel

    Parallel --> Project
    Parallel --> Quotation
    Parallel --> Atom
    Parallel --> Escrow
    Parallel --> Mdm
    Parallel --> Order

    Project --> Context
    Quotation --> Context
    Atom --> Context
    Escrow --> Context
    Mdm --> Context
    Order --> Context

    Context --> DownstreamSvc
```

### 5.2 合同详情查询数据流

```mermaid
flowchart TD
    subgraph Input[输入]
        ProjectOrderId[项目单号]
        ContractType[合同类型]
        ChangeOrderId[变更单号]
        IsFirstScreen[是否首屏]
        BillCodeList[报价单号列表]
        SubOrderList[子订单列表]
        ChangeOrderList[变更单列表]
    end

    subgraph ContextModule[ContractContextModule]
        DetailAspect[ContractDetailAspect]
        DetailContext[ContractDetailContext]
    end

    subgraph FirstScreen[首屏加载]
        ProjectInfo[项目信息]
        AttachInfo[备件信息]
        DesignFee[设计费金额]
    end

    subgraph FullLoad[非首屏补充加载]
        QuoteInfo[报价信息]
        ComboInfo[套餐信息]
        FundInfo[款项实收]
        DrawingInfo[图纸信息]
        AuditInfo[风控审核信息]
        ChangeList[变更单列表]
    end

    Input --> DetailAspect
    DetailAspect --> FirstScreen
    DetailAspect --> FullLoad
    FirstScreen --> DetailContext
    FullLoad --> DetailContext
    DetailContext --> DetailService[ContractDetailService<br/>详情组装]
```

## 6. 关键设计模式

### 6.1 AOP + ThreadLocal 上下文模式

该模块采用经典的 **AOP + ThreadLocal 上下文** 模式：

```mermaid
sequenceDiagram
    participant Client as HTTP 请求线程
    participant Proxy as Spring AOP 代理
    participant Aspect as ContextAspect
    participant TL as ThreadLocal
    participant Service as 业务 Service 方法

    Client->>Proxy: 调用标注注解的方法
    Proxy->>Aspect: @Before 拦截
    Aspect->>TL: initContext() 创建上下文
    Aspect->>Aspect: 并行数据采集
    Aspect->>TL: 写入采集结果
    Proxy->>Service: 执行业务方法
    Service->>TL: getContext() 读取数据
    Service-->>Proxy: 返回结果
    Proxy->>Aspect: @After 清理
    Aspect->>TL: clearContext() 移除上下文
    Proxy-->>Client: 返回结果
```

**优势**：
- 业务方法通过 `ContractContextHandler.getContext()` 直接获取已准备好的数据，无需关心数据采集细节
- 新增数据源只需在切面中添加并行任务，对下游透明
- 参数预处理逻辑集中管理，避免分散在各业务方法中

### 6.2 并行任务编排模式

使用 `ParallelTaskService` 实现多数据源并行查询：

```mermaid
graph LR
    subgraph Sequential[串行阶段]
        A[initContext] --> B[preHandleParam]
        B --> C[dealReContractLaunch]
    end

    subgraph Parallel[并行阶段]
        D1[dealBaseInfo]
        D2[dealPlanAllDTO]
        D3[dealComboInfo]
        D4[dealProjectInfo]
        D5[getOperatorName]
        D6[dealDrawingDTO]
        D7[dealEscrowDTO]
        D8[dealStandardDesignAmountDTO]
        D9[dealMultiCompanyInfo]
    end

    subgraph PostProcess[后处理阶段]
        E[设置城市分公司配置]
        E --> F[计算合同模式]
        F --> G[设计费预处理]
    end

    C --> D1
    C --> D2
    C --> D3
    C --> D4
    C --> D5
    C --> D6
    C --> D7
    C --> D8
    C --> D9

    D1 --> E
    D2 --> E
    D3 --> E
    D4 --> E
    D5 --> E
    D6 --> E
    D7 --> E
    D8 --> E
    D9 --> E
```

### 6.3 条件分发模式

数据采集方法内部通过**合同类型**、**业务类型**、**流程版本**三个维度的条件组合决定实际执行逻辑：

| 维度 | 取值示例 | 影响范围 |
|------|---------|---------|
| 合同类型 (ContractTypeEnum) | ADVANCE, PACKAGE_FORMAL, PACKAGE_CHANGE, DRAWING, PERSONAL, DESIGN, FUND_ESCROW, TERMINAL | 决定哪些数据采集任务生效 |
| 业务类型 (BusinessTypeEnum) | HOUSE_CERTIFICATE, GROUP_DECORATE, REFORM_ALL | 影响报价获取路径和套餐查询 |
| 流程版本 (processV25) | true / false | 影响图纸获取方式和报价接口选择 |

### 6.4 首屏分层加载模式

`ContractDetailAspect` 采用首屏优化策略，将数据加载分为两个批次：

- **第一批次（首屏）**：仅加载项目信息、备件信息、设计费金额 — 3 个轻量任务，快速返回页面首屏所需数据
- **第二批次（非首屏）**：追加报价信息、套餐信息、款项信息、图纸信息、风控审核 — 5 个较重任务，页面滚动或交互时再展示

## 7. 与其他模块的关系

| 相关模块 | 关系描述 |
|---------|---------|
| [ContractCore](ContractCore.md) | 本模块为 ContractCore 下的 `ContractUnifyService`、`ContractDetailService` 等提供预装配的上下文数据，是这些服务执行前的数据准备层 |
| [ContractChangeStrategy](ContractChangeStrategy.md) | 变更合同的报价差异构建（`buildAtomChangeQuotation`）产生的 `PlanAllDTO` 会被变更策略使用 |
| [ContractPdfModule](ContractPdfModule.md) | PDF 生成依赖上下文中的图纸信息（`DrawingDTO`）和报价信息（`PlanAllDTO`） |
| [ContractSigningModule](ContractSigningModule.md) | 个人合同签约源路由（`ContractSigningSourceRouter`）在图纸信息采集和报价信息采集中被调用 |
| [ContractMaterialModule](ContractMaterialModule.md) | 套餐信息中的材料清单数据通过本模块采集后供材料 PDF 差异对比使用 |

## 8. 注意事项与改进建议

### 8.1 潜在风险

1. **ContractDetailContextHandler 空值防护缺失**：`getProjectInfo()`、`getPlanAllDTO()` 等方法在 `CONTEXT.get()` 为 null 时会抛出 NPE，而 `ContractContextHandler` 的对应方法已做了空值防护。建议统一补齐。

2. **并行任务异常隔离**：当前并行任务中单个任务失败会导致整个切面异常，建议评估是否需要对非关键任务（如操作人姓名、存管账户）增加容错处理。

3. **切面参数强转**：`ContractDetailAspect.beforeHandle` 中对方法参数进行强转 `(String) args[1]`，依赖被拦截方法的参数顺序，缺乏类型安全保障。建议引入参数对象封装。

### 8.2 性能优化建议

- 合同保存切面的 9 个并行任务中，部分任务有条件判断提前返回（如 `dealComboInfo` 仅 2.5 流程生效），但任务创建本身仍会产生开销，可考虑条件化任务注册
- 首屏策略已生效于详情切面，保存/提交切面可参考类似思路优化关键路径
