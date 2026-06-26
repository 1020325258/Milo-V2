# Contract Detail Context Handler

## 模块概述

**Contract Detail Context Handler** 是合同详情查询子系统中的核心数据准备模块，负责在合同详情接口调用时，通过 AOP 切面拦截机制，**并行加载**来自项目服务、报价系统、风控审核、款项系统等多个外部服务的数据，并将结果缓存在基于 `ThreadLocal` 的请求级上下文中，供下游 `ContractDetailService` 的各 `build*` 方法读取并组装最终响应。

本模块解决的核心问题是：合同详情页面需要聚合十余个外部数据源，如果串行调用会导致接口响应时间过长。通过 AOP + 并行任务编排 + ThreadLocal 上下文的三层架构，实现了数据加载的**声明式触发**、**并行执行**和**零侵入传递**。

---

## 模块在系统中的位置

```mermaid
graph TD
    subgraph 前端请求层
        FE[前端页面]
    end

    subgraph Controller层
        CC[ContractController]
    end

    subgraph AOP数据准备层
        CA[ContractDetailAspect]
        CDCH[ContractDetailContextHandler]
        CDO[ContractDetailContext 数据载体]
        PTS[ParallelTaskService]
    end

    subgraph 业务服务层
        CDS[ContractDetailService]
        CUS[ContractUnifyService]
        CBUS[ContractBusinessService]
    end

    subgraph 外部数据源
        PIRS[ProjectInfoReadService]
        QFS[QuotationFeignService]
        ACR[AtomChangeRpc]
        AUR[AuditRpc]
        FIS[FundInfoService]
        CRR[CeresRpc]
        ADR[AtomDrawingRpc]
    end

    FE --> CC
    CC -->|ContractDetailDataPrepare注解| CA
    CA -->|initContext| CDCH
    CDCH -->|持有| CDO
    CA -->|并行任务| PTS
    PTS --> PIRS
    PTS --> QFS
    PTS --> ACR
    PTS --> AUR
    PTS --> FIS
    PTS --> CRR
    PTS --> ADR
    PTS -->|结果写入| CDO
    CA -->|触发业务方法| CDS
    CDS -->|读取上下文| CDCH
    CDCH -->|返回| CDO
```

---

## 架构设计

### 三层架构

```mermaid
graph LR
    subgraph 第一层_声明式拦截
        AOP[ContractDetailAspect<br>AOP切面]
        ANNO[ContractDetailDataPrepare注解<br>自定义注解]
        ANNO -->|标记| AOP
    end

    subgraph 第二层_上下文管理
        HANDLER[ContractDetailContextHandler<br>ThreadLocal静态工具类]
        CTX[ContractDetailContext<br>数据载体对象]
        HANDLER -->|持有| CTX
    end

    subgraph 第三层_业务组装
        SERVICE[ContractDetailService<br>构建各模块响应]
        BUILD[build 方法族<br>项目/报价/签约/附件等]
        SERVICE --> BUILD
    end

    AOP -->|init/clear| HANDLER
    AOP -->|数据写入| CTX
    SERVICE -->|get 读取| HANDLER
```

---

## 核心组件详解

### 1. ContractDetailContextHandler — 上下文管理器

**职责**：通过 `ThreadLocal<ContractDetailContext>` 管理请求级的合同详情数据上下文的生命周期。

**设计模式**：ThreadLocal Holder 模式（单例静态工具类 + 线程隔离数据）

```mermaid
classDiagram
    class ContractDetailContextHandler {
        -ThreadLocal~ContractDetailContext~ CONTEXT$
        +initContext()$ void
        +clearContext()$ void
        +setContext(ContractDetailContext)$ void
        +getContext()$ ContractDetailContext
        +setProjectInfo(ProjectInfoDTO)$ void
        +getProjectInfo()$ ProjectInfoDTO
        +setPlanAllDTO(PlanAllDTO)$ void
        +getPlanAllDTO()$ PlanAllDTO
        +getContractSourceDataBO()$ ContractSourceDataBO
        +setDrawingUrl(String)$ void
        +getDrawingUrl()$ String
        +setAtomChangeScopeList(List~Integer~)$ void
        +getAtomChangeScopeList()$ List~Integer~
        +setFirstScreen(boolean)$ void
        +isFirstScreen()$ boolean
    }

    class ContractDetailContext {
        -ProjectInfoDTO projectInfoDTO
        -PlanAllDTO planAllDTO
        -DrawingDTO.DeliverDrawingDTO drawingDTO
        -ContractSourceDataBO contractSourceDataBO
        -LightQuotationDTO.LightQuotationItem preQuotationDTO
        -List~Integer~ atomChangeScopeList
        -String drawingUrl
        -FundInfo relateFundInfo
        -AuditDetailDto auditDetailDTO
        -List~ChangeListDTO~ changeOrderList
        -AttachInfoDetail attachInfoDetail
        -DesignSignPriceInfo designSignPriceInfo
        -List~ComboDTO~ comboDTOList
        -boolean isFirstScreen
        -Byte businessType
        -boolean processV25
        -DesignQuoteFeeDTO designQuoteFeeDTO
    }

    ContractDetailContextHandler --> ContractDetailContext : ThreadLocal 持有
```

**关键设计决策**：

| 设计点 | 说明 |
|--------|------|
| 全静态方法 | 无实例化需求，任意位置可直接调用 `ContractDetailContextHandler.getContext()` |
| ThreadLocal 隔离 | 每个请求线程拥有独立上下文，避免并发数据串扰 |
| 生命周期由 AOP 管理 | `initContext()` 在 `@Before` 中调用，`clearContext()` 在 `@After` 和 `@AfterThrowing` 中调用，确保无内存泄漏 |
| 便捷访问方法 | 提供 `set/getProjectInfo`、`set/getPlanAllDTO` 等快捷方法，避免调用方直接操作 Context 对象 |

**内存安全机制**：

```mermaid
sequenceDiagram
    participant Req as 请求线程
    participant Aspect as ContractDetailAspect
    participant Handler as ContextHandler
    participant TL as ThreadLocal

    Req->>Aspect: 方法被 @ContractDetailDataPrepare 拦截
    Aspect->>Handler: initContext()
    Handler->>TL: set(new ContractDetailContext())

    Note over Req,TL: 并行数据加载阶段 — 多个子线程写入 Context

    Aspect->>Handler: getContext()
    Handler-->>Aspect: 返回 context 引用

    alt 正常结束
        Aspect->>Handler: clearContext()
        Handler->>TL: remove()
    else 异常抛出
        Aspect->>Handler: clearContext() @AfterThrowing
        Handler->>TL: remove()
    end
```

> **关联文档**：[Contract Context Handler](Contract Context Handler.md) 描述了同层的通用合同上下文处理器（`ContractContextHandler`），两者共享相同的 ThreadLocal Holder 设计模式，但管理不同粒度的上下文数据。

---

### 2. ContractDetailAspect — AOP 数据准备切面

**职责**：拦截标注了 `@ContractDetailDataPrepare` 注解的方法，在目标方法执行前并行加载所有依赖数据到上下文，并在方法结束后清理上下文。

**切入点定义**：
```java
@Pointcut("@annotation(com.ke.utopia.nrs.salesproject.service.contract.annotation.ContractDetailDataPrepare)")
public void pointCut() {}
```

**核心数据准备流程**：

```mermaid
flowchart TD
    START([beforeHandle 入口]) --> INIT[initContext 初始化空上下文]
    INIT --> EXTRACT[解析方法参数<br>projectOrderId / contractType / changeOrderId<br>isFirstScreen / billCodeInfoList 等]
    EXTRACT --> META[设置元信息<br>processV25 / businessType]
    META --> CREATE[创建 ParallelTasksContext]
    CREATE --> P1[任务1: dealProjectInfo<br>项目信息]
    CREATE --> P2[任务2: dealAttachInfo<br>备件信息]
    CREATE --> P3[任务3: dealStandardDesignAmountDTO<br>设计费金额]

    P1 --> CHECK{是否首屏?}
    P2 --> CHECK
    P3 --> CHECK

    CHECK -->|非首屏| P4[任务4: dealPlanAllDTO<br>报价信息]
    CHECK -->|非首屏| P5[任务5: dealComboInfo<br>套餐信息]
    CHECK -->|非首屏| P6[任务6: dealRelateFundInfo<br>款项实收金额]
    CHECK -->|非首屏| P7[任务7: dealDrawingDTO<br>图纸信息]
    CHECK -->|非首屏| P8[任务8: dealAuditInfo<br>风控审核信息]
    CHECK -->|首屏| EXEC

    P4 --> EXEC[execTasks + awaitTasksResult]
    P5 --> EXEC
    P6 --> EXEC
    P7 --> EXEC
    P8 --> EXEC
    EXEC --> END([数据准备完成, 执行目标方法])

    style CHECK fill:#FFF3CD,stroke:#FFC107
    style START fill:#D4EDDA,stroke:#28A745
    style END fill:#D4EDDA,stroke:#28A745
```

**首屏优化策略**：

首屏（`isFirstScreen=true`）仅加载 3 个核心数据任务，跳过报价、套餐、款项、图纸、审核等重量级 RPC 调用，确保首屏渲染速度：

| 数据任务 | 首屏 | 非首屏 | 说明 |
|---------|------|--------|------|
| `dealProjectInfo` | 加载 | 加载 | 项目基础信息，必需 |
| `dealAttachInfo` | 加载 | 加载 | 仅正签合同需要 |
| `dealStandardDesignAmountDTO` | 加载 | 加载 | 仅设计合同需要 |
| `dealPlanAllDTO` | 跳过 | 加载 | 报价信息，涉及多 RPC 调用 |
| `dealComboInfo` | 跳过 | 加载 | 套餐信息，需查询中控 |
| `dealRelateFundInfo` | 跳过 | 加载 | 款项信息 |
| `dealDrawingDTO` | 跳过 | 加载 | 图纸信息，大文件 |
| `dealAuditInfo` | 跳过 | 加载 | 风控审核，仅正签需要 |

**各数据准备方法的条件过滤逻辑**：

```mermaid
flowchart LR
    subgraph dealPlanAllDTO
        direction TB
        PT1{contractType<br>在允许列表中?}
        PT1 -->|否| SKIP1[跳过]
        PT1 -->|是| PT2{翻新全案<br>首期款?}
        PT2 -->|是| SKIP1
        PT2 -->|否| PT3{合同类型分支}
        PT3 -->|ADVANCE| ADV[预报价查询]
        PT3 -->|PERSONAL| PER[个性化报价]
        PT3 -->|变更+2.5协同| ATM[中控变更报价]
        PT3 -->|其他| STD[通用报价准备]
    end

    subgraph dealComboInfo
        direction TB
        CI1{套餐合同类型?}
        CI1 -->|否| SKIP2[跳过]
        CI1 -->|是| CI2{主订单快照<br>查询开关?}
        CI2 -->|否| SKIP2
        CI2 -->|是| CI3{有变更单号?}
        CI3 -->|是| CHG[查询变更套餐]
        CI3 -->|否| NML[查询正签套餐]
    end

    subgraph dealAuditInfo
        direction TB
        AI1{正签合同?}
        AI1 -->|否| SKIP3[跳过]
        AI1 -->|是| AI2{存在已完成合同?}
        AI2 -->|否| SKIP3
        AI2 -->|是| AI3{2.5协同模式?}
        AI3 -->|否| SKIP3
        AI3 -->|是| LOAD[加载审核+变更单]
    end
```

**切面生命周期保障**：

```mermaid
sequenceDiagram
    participant Caller as Controller 调用方
    participant Aspect as ContractDetailAspect
    participant CtxHandler as ContextHandler
    participant Target as 目标方法

    Caller->>Aspect: @Before
    Aspect->>CtxHandler: initContext()
    Aspect->>Aspect: 并行加载数据
    Aspect-->>Aspect: 数据写入 Context

    Aspect->>Target: 执行目标方法
    Target->>CtxHandler: getContext() 读取数据
    Target-->>Caller: 返回 ContractDetailResp

    alt 正常返回
        Aspect->>CtxHandler: @After → clearContext()
    else 异常
        Aspect->>CtxHandler: @AfterThrowing → clearContext()
    end
```

---

### 3. ContractDetailContext — 数据载体

**职责**：作为请求级的数据容器，聚合来自多个外部服务的数据，供下游服务构建各模块的详情响应。

**字段与数据来源映射**：

| 字段 | 类型 | 数据来源 | 写入方法 |
|------|------|---------|---------|
| `projectInfoDTO` | `ProjectInfoDTO` | ProjectInfoReadService | `dealProjectInfo` |
| `planAllDTO` | `PlanAllDTO` | QuotationFeignService / HomeOrderDataConversionService | `dealPlanAllDTO` |
| `contractSourceDataBO` | `ContractSourceDataBO` | HomeOrderDataConversionService / ContractDependentDataService | `dealPlanAllDTO` |
| `drawingDTO` | `DrawingDTO.DeliverDrawingDTO` | AtomDrawingRpc / ContractBusinessService | `dealDrawingDTO` |
| `preQuotationDTO` | `LightQuotationDTO.LightQuotationItem` | AtomBudgetRpc | `dealPlanAllDTO` (ADVANCE) |
| `atomChangeScopeList` | `List<Integer>` | AtomChangeRpc | `buildAtomChangeQuotation` |
| `drawingUrl` | `String` | AtomDrawingRpc | `buildAtomChangeQuotation` |
| `relateFundInfo` | `FundInfo` | FundInfoService | `dealRelateFundInfo` |
| `auditDetailDTO` | `AuditDetailDto` | AuditRpc | `dealAuditInfo` |
| `changeOrderList` | `List<ChangeListDTO>` | AtomChangeRpc | `dealAuditInfo` |
| `attachInfoDetail` | `AttachInfoDetail` | AttachCommonService | `dealAttachInfo` |
| `designSignPriceInfo` | `DesignSignPriceInfo` | CeresRpc + QuotationFeignService | `dealStandardDesignAmountDTO` |
| `comboDTOList` | `List<ComboDTO>` | OrderStandardQueryRpc | `dealComboInfo` |
| `isFirstScreen` | `boolean` | 请求参数 | `beforeHandle` |
| `businessType` | `Byte` | CommonBusinessService | `beforeHandle` |
| `processV25` | `boolean` | CommonBusinessService | `beforeHandle` |
| `designQuoteFeeDTO` | `DesignQuoteFeeDTO` | HomeOrderDataConversionService | `dealPlanAllDTO` (PACKAGE_FORMAL) |

---

### 4. ContractDetailService — 业务组装服务

**职责**：从 `ContractDetailContextHandler` 读取预加载的数据，结合数据库中的合同持久化数据，构建合同详情页所需的各模块响应对象。

**主要构建方法与上下文数据读取关系**：

```mermaid
flowchart TD
    subgraph Context读取
        CTX[ContractDetailContext]
    end

    subgraph build方法族
        BPRJ[buildContractProjectInfoDetail<br>项目信息详情]
        BBASE[buildContractBaseInfoDetail<br>合同基础信息详情]
        BSIGN[buildContractSignInfoDetail<br>签约信息详情]
        BQUOTE[buildQuotationDetail<br>报价信息详情]
        BPERS[buildPersonalQuotationDetail<br>个性化报价详情]
        BPROM[buildPromiseInfoDetail<br>承包约定信息]
        BACT[buildActivityInfoDetail<br>优惠活动信息]
        BPROC[buildProcessInfoDetail<br>审核流程信息]
        BATT[buildContractAttachInfo<br>合同附件信息]
        BAMT[buildAmountInfoDetail<br>金额信息详情]
        BPCOL[buildPersonalCollectionPlanInfo<br>定软电收款计划]
        BSUP[buildSupplementItemInfo<br>补充协议信息]
        BSTL[buildSettlementItemInfo<br>和解协议信息]
    end

    CTX -->|projectInfoDTO| BPRJ
    CTX -->|planAllDTO + businessType + processV25| BBASE
    CTX -->|planAllDTO + contractSourceDataBO| BSIGN
    CTX -->|planAllDTO + atomChangeScopeList| BQUOTE
    CTX -->|contractSourceDataBO| BPERS
    CTX -->|designQuoteFeeDTO| BPROM
    CTX -->|planAllDTO| BACT
    CTX -->|auditDetailDTO + changeOrderList| BPROC
    CTX -->|attachInfoDetail| BATT
    CTX -->|relateFundInfo| BAMT
    CTX -->|contractSourceDataBO| BPCOL
```

**入口方法 `initContractDetail` 的组装流程**：

```mermaid
flowchart TD
    INIT([initContractDetail 入口]) --> BPI[buildContractProjectInfoDetail<br>构建项目信息]
    BPI --> BSI[buildContractSignInfoDetail<br>构建签约信息]
    BSI --> BAI[buildContractAttachInfo<br>构建附件信息]
    BAI --> MERGE[mergeContractAttachInfoTOSignInfo<br>合并附件到签约信息]

    MERGE --> CHECK{是否首屏?}
    CHECK -->|是| FIRST[返回精简响应<br>signInfo + contractBaseInfo<br>+ businessInfo + projectInfo]
    CHECK -->|否| FULL[完整数据组装]

    FULL --> BQD[buildQuotationDetail<br>报价信息]
    BQD --> BPQ[buildPersonalQuotationDetail<br>个性化报价]
    BPQ --> BPCP[buildPersonalCollectionPlanInfo<br>收款计划]
    BPCP --> BSI2[buildSupplementItemInfo<br>补充协议]
    BSI2 --> BSTI[buildSettlementItemInfo<br>和解协议]
    BSTI --> RESP[构建完整 ContractDetailResp]

    style CHECK fill:#FFF3CD,stroke:#FFC107
    style FIRST fill:#CCE5FF,stroke:#0D6EFD
    style RESP fill:#D4EDDA,stroke:#28A745
```

---

## 依赖关系

### 外部服务依赖

```mermaid
graph LR
    subgraph 本模块
        ASPECT[ContractDetailAspect]
        SERVICE[ContractDetailService]
    end

    subgraph RPC远程服务
        PIRS[ProjectInfoReadService<br>项目信息]
        QFS[QuotationFeignService<br>报价查询]
        ACR[AtomChangeRpc<br>变更服务]
        ABR[AtomBudgetRpc<br>预算报价]
        ADR[AtomDrawingRpc<br>图纸服务]
        AUR[AuditRpc<br>风控审核]
        CRR[CeresRpc<br>服务者中心]
        OSQR[OrderStandardQueryRpc<br>中控标准查询]
    end

    subgraph 本地DAO服务
        CS[ContractService<br>合同表]
        CFS[ContractFieldService<br>合同字段表]
        FIS[FundInfoService<br>款项表]
        CUS[ContractUserService<br>签约人表]
        CMS[ContractMaterialService<br>甲供材料表]
        CRS[ContractRelationService<br>合同关联表]
        CAS[ContractAttachService<br>合同附件表]
    end

    subgraph 业务服务
        CBS[CommonBusinessService<br>通用业务]
        HCPS[HomeAndPcCommonService<br>家装通用]
        CUCS[ContractUnifyService<br>合同统一服务]
        CCUS[ChangeContractUnifyService<br>变更统一服务]
        PTS[ParallelTaskService<br>并行任务]
        ACS[AttachCommonService<br>备件通用]
        CAC[ContractApolloConfig<br>Apollo配置]
        HOCS[HomeOrderDataConversionService<br>主订单数据转换]
        CDDS[ContractDependentDataService<br>合同依赖数据]
    end

    ASPECT --> PIRS
    ASPECT --> QFS
    ASPECT --> ACR
    ASPECT --> AUR
    ASPECT --> CRR
    ASPECT --> ADR
    ASPECT --> PTS
    ASPECT --> CBS
    ASPECT --> ACS
    ASPECT --> CAC

    SERVICE --> CS
    SERVICE --> CFS
    SERVICE --> FIS
    SERVICE --> CUS
    SERVICE --> CMS
    SERVICE --> CRS
    SERVICE --> CUCS
    SERVICE --> CBS
    SERVICE --> HCPS
    SERVICE --> ACS
    SERVICE --> CAC
    SERVICE --> ACR
    SERVICE --> AUR
    SERVICE --> QFS
    SERVICE --> CRR
    SERVICE --> ABR
    SERVICE --> OSQR
```

### 模块间依赖

```mermaid
graph TD
    CDH[Contract Detail Context Handler<br>当前模块]
    CCH[Contract Context Handler<br>通用上下文模块]
    CCS[Contract Core Services<br>核心服务层]
    CPF[Contract PDF Generation<br>PDF生成模块]
    CRS[Contract Change Strategy<br>变更策略模块]
    PRS[Personal Relation and Signing<br>个性化签约模块]

    CDH -.->|同层设计模式参考| CCH
    CDH -->|调用核心服务| CCS
    CDH -->|触发PDF预览| CPF
    CDH -->|查询变更策略| CRS
    CDH -->|个性化合同图纸| PRS

    style CDH fill:#D4EDDA,stroke:#28A745
    style CCH fill:#CCE5FF,stroke:#0D6EFD
```

---

## 数据流图

### 请求全链路数据流

```mermaid
sequenceDiagram
    participant FE as 前端
    participant CC as ContractController
    participant AS as ContractDetailAspect
    participant PTS as ParallelTaskService
    participant RPC as 外部RPC服务
    participant CTX as ContractDetailContext
    participant HDL as ContextHandler
    participant SVC as ContractDetailService
    participant DB as 数据库

    FE->>CC: GET /contract/detail
    CC->>AS: @Before 拦截
    AS->>HDL: initContext()
    AS->>PTS: 创建并行任务组

    par 并行数据加载
        PTS->>RPC: dealProjectInfo
        RPC-->>CTX: projectInfoDTO
    and
        PTS->>RPC: dealPlanAllDTO
        RPC-->>CTX: planAllDTO + contractSourceDataBO
    and
        PTS->>RPC: dealComboInfo
        RPC-->>CTX: comboDTOList
    and
        PTS->>RPC: dealRelateFundInfo
        RPC-->>CTX: relateFundInfo
    and
        PTS->>RPC: dealDrawingDTO
        RPC-->>CTX: drawingDTO
    and
        PTS->>RPC: dealAuditInfo
        RPC-->>CTX: auditDetailDTO + changeOrderList
    and
        PTS->>RPC: dealAttachInfo
        RPC-->>CTX: attachInfoDetail
    and
        PTS->>RPC: dealStandardDesignAmountDTO
        RPC-->>CTX: designSignPriceInfo
    end

    AS->>CC: 执行目标Controller方法
    CC->>SVC: initContractDetail()

    SVC->>HDL: getProjectInfo()
    HDL-->>SVC: projectInfoDTO
    SVC->>DB: 查询合同/字段/附件
    DB-->>SVC: 持久化数据

    SVC->>HDL: getPlanAllDTO()
    HDL-->>SVC: planAllDTO
    SVC->>HDL: getContext().getAuditDetailDTO()
    HDL-->>SVC: auditDetailDTO
    SVC->>HDL: getContractSourceDataBO()
    HDL-->>SVC: contractSourceDataBO

    SVC->>SVC: 组装 ContractDetailResp
    SVC-->>CC: ContractDetailResp
    CC-->>FE: JSON 响应

    AS->>HDL: @After → clearContext()
```

### 报价信息数据流（dealPlanAllDTO 分支路由）

```mermaid
flowchart TD
    ENTRY([dealPlanAllDTO]) --> COND1{合同类型?}

    COND1 -->|ADVANCE 首期款| ADV[contractDetailService.getAdvanceQuote]
    ADV --> ADV_SET[context.setPreQuotationDTO]

    COND1 -->|PERSONAL 个性化| PER[contractDependentDataService<br>.queryPersonalQuoteInfoV2]
    PER --> PER_SET[context.setContractSourceDataBO]

    COND1 -->|变更+2.5协同| ATM[buildAtomChangeQuotation]
    ATM --> ATM_SET[context.setPlanAllDTO<br>+ setContractSourceDataBO]

    COND1 -->|其他套餐类型| STD[homeOrderDataConversionService<br>.contractSourceDate]
    STD --> STD_SET[context.setPlanAllDTO]
    STD --> STD_DESIGN{有设计费报价?}
    STD_DESIGN -->|是| DESIGN_SET[context.setDesignQuoteFeeDTO]
    STD_DESIGN -->|否| PERSONAL[构建个性化报价数据]
    PERSONAL --> P_SET[context.setContractSourceDataBO]
```

---

## 关键设计模式

### 1. AOP 拦截 + ThreadLocal 上下文（Context Object Pattern）

```mermaid
flowchart LR
    subgraph 声明式触发
        ANNO["ContractDetailDataPrepare注解<br>标注在Controller方法上"]
    end

    subgraph 横切关注点
        ASPECT["ContractDetailAspect<br>Before: init + 并行加载<br>After: clear<br>AfterThrowing: clear"]
    end

    subgraph 上下文容器
        HANDLER["ContractDetailContextHandler<br>ThreadLocal 静态工具类"]
        CTX["ContractDetailContext<br>聚合15+数据字段"]
    end

    subgraph 业务消费者
        SERVICE["ContractDetailService<br>build* 方法族"]
    end

    ANNO --> ASPECT
    ASPECT --> HANDLER
    HANDLER --> CTX
    CTX -.->|静态方法读取| SERVICE
```

**优势**：
- 业务方法无需感知数据加载细节，只需通过 `ContractDetailContextHandler.getContext()` 获取
- 新增数据源只需在 Aspect 中添加并行任务，下游代码零修改
- ThreadLocal 确保线程安全，AOP 确保生命周期安全

### 2. 首屏/非首屏分层加载

通过 `isFirstScreen` 标志实现渐进式数据加载，首屏仅加载 3 个轻量任务（项目信息、备件信息、设计费），非首屏再追加 5 个重量级 RPC 调用：

```mermaid
graph LR
    subgraph 首屏渲染-快速响应
        S1[项目信息-必需]
        S2[备件信息-仅正签]
        S3[设计费-仅设计合同]
        S1 --> S2
        S2 --> S3
    end

    subgraph 非首屏加载-完整数据
        N1[报价信息]
        N2[套餐信息]
        N3[款项信息]
        N4[图纸信息]
        N5[审核信息]
    end

    S3 -.->|用户交互触发| N1
```

### 3. 条件短路过滤（Guard Clause）

每个数据准备方法内部通过合同类型、业务模式等条件判断是否需要执行，不满足条件直接 `return`，避免无意义的 RPC 调用：

```mermaid
flowchart TD
    START([数据准备方法入口]) --> G1{合同类型匹配?}
    G1 -->|否| SKIP[直接返回]
    G1 -->|是| G2{业务模式匹配?}
    G2 -->|否| SKIP
    G2 -->|是| G3{已启用开关?}
    G3 -->|否| SKIP
    G3 -->|是| EXEC[执行RPC调用并写入Context]
```

### 4. 并行任务编排

通过 `ParallelTaskService` 实现任务并行化，所有独立的数据加载任务在同一个 `ParallelTasksContext` 中并发执行：

```mermaid
sequenceDiagram
    participant Main as 主线程
    participant PTS as ParallelTaskService
    participant T1 as 任务1-项目
    participant T2 as 任务2-备件
    participant T3 as 任务3-设计费
    participant T4 as 任务4-报价
    participant T5 as 任务5-套餐

    Main->>PTS: addNewTask x N
    Main->>PTS: execTasks
    par 并行执行
        PTS->>T1: 执行
        PTS->>T2: 执行
        PTS->>T3: 执行
        PTS->>T4: 执行
        PTS->>T5: 执行
    end
    T1-->>PTS: 完成
    T2-->>PTS: 完成
    T3-->>PTS: 完成
    T4-->>PTS: 完成
    T5-->>PTS: 完成
    PTS->>Main: awaitTasksResult 阻塞等待全部完成
```

### 5. 多来源数据融合

`ContractDetailService` 的各 build 方法需要融合两种数据：
- **实时数据**：来自 Context 中缓存的 RPC 调用结果
- **持久化数据**：来自数据库中的合同字段（`ContractField` 表以 key-value 形式存储）

初始化时优先使用实时数据，编辑时优先使用已保存的持久化数据（通过 `fieldMap` 回填）：

```mermaid
flowchart LR
    subgraph 数据融合策略
        CHECK{contract == null?}
        CHECK -->|初始化| REALTIME[使用 Context 实时数据<br>+ 项目信息默认值]
        CHECK -->|编辑| PERSIST[使用 fieldMap 持久化数据<br>+ Context 补充实时字段]
    end

    subgraph fieldMap来源
        DB[(ContractField表<br>key-value结构)]
        DB --> PERSIST
    end

    subgraph Context来源
        CTX[(ContractDetailContext<br>RPC实时数据)]
        CTX --> REALTIME
        CTX -->|部分字段覆盖| PERSIST
    end
```

---

## 合同类型支持矩阵

不同合同类型触发不同的数据准备分支和构建逻辑：

| 合同类型 | 报价信息 | 套餐信息 | 图纸信息 | 审核信息 | 设计费 | 款项信息 |
|---------|---------|---------|---------|---------|--------|---------|
| ADVANCE 首期款 | 预报价 | - | - | - | - | 支持 |
| PACKAGE_FORMAL 正签 | 完整报价 | 支持 | 团装2.5 | 2.5协同 | 报价来源 | 支持 |
| PACKAGE_CHANGE 变更 | 变更报价 | 变更套餐 | - | - | - | 支持 |
| PERSONAL 个性化 | 个性化报价 | - | 个性化图纸 | - | - | 支持 |
| DESIGN 设计 | - | - | - | - | 标准设计费 | - |
| DRAWING 施工图纸 | 完整报价 | - | - | - | - | 支持 |

---

## 异常处理策略

| 场景 | 处理方式 | 影响范围 |
|------|---------|---------|
| 项目信息获取失败 | 抛出 `UtopiaBussinessException`，中断所有任务 | 整个请求失败 |
| 风控审核信息获取失败 | `try-catch` 捕获，日志记录，流程信息不展示 | 仅审核流程模块缺失 |
| 报价信息不匹配 | 按合同类型短路返回，不写入 Context | 报价模块不展示 |
| 切面方法异常 | `@AfterThrowing` 确保 Context 被清理 | 无内存泄漏 |
| 设计师职级查询失败 | 抛出 `NrsBusinessException`，提示用户 | 设计费模块不可用 |
