# Contract Context 模块

## 1. 模块概述

Contract Context 是合同子系统中的**数据准备与上下文管理**模块，采用 AOP（面向切面编程）模式，在合同的保存/提交/查询等业务方法执行前，自动完成多维度数据的并行加载与预处理，并将结果存储在线程隔离的上下文中供后续业务逻辑使用。

该模块的核心设计理念是：**将数据准备（横切关注点）与业务逻辑（核心关注点）彻底分离**，通过注解驱动 + AOP 拦截的机制，让业务代码无需关心"数据从哪里来、怎么拼装"，只需从上下文中读取即可。

模块包含两大核心场景：
- **合同保存/提交场景**：`ContractContextAspect` + `ContractContextHandler`，对应注解 `@ContractDataPrepare`
- **合同详情查询场景**：`ContractDetailAspect` + `ContractDetailContextHandler`，对应注解 `@ContractDetailDataPrepare`

---

## 2. 架构总览

```mermaid
graph TD
    subgraph AnnotationLayer[注解驱动层]
        A1[ContractDataPrepare 注解]
        A2[ContractDetailDataPrepare 注解]
    end

    subgraph AOPLayer[AOP切面层]
        B1[ContractContextAspect]
        B2[ContractDetailAspect]
    end

    subgraph ContextLayer[上下文管理层]
        C1[ContractContextHandler]
        C2[ContractDetailContextHandler]
        C3[ContractContext BO]
        C4[ContractDetailContext BO]
    end

    subgraph DataLayer[数据准备层]
        D1[ParallelTaskService 并行任务编排]
        D2[报价信息准备]
        D3[项目信息准备]
        D4[图纸信息准备]
        D5[存管账户准备]
        D6[合同主体准备]
        D7[套餐信息准备]
        D8[操作人信息准备]
    end

    subgraph ExternalLayer[外部依赖层]
        E1[ProjectInfoReadService]
        E2[QuotationFeignService]
        E3[AtomDrawingRpc]
        E4[AtomChangeRpc]
        E5[EscrowDomain]
        E6[MdmDataRpc]
        E7[OrderStandardQueryRpc]
        E8[HomeOrderDataConversionService]
    end

    A1 --> B1
    A2 --> B2
    B1 --> C1
    B1 --> C3
    B2 --> C2
    B2 --> C4
    B1 --> D1
    B2 --> D1
    D1 --> D2
    D1 --> D3
    D1 --> D4
    D1 --> D5
    D1 --> D6
    D1 --> D7
    D1 --> D8
    D2 --> E2
    D2 --> E4
    D2 --> E8
    D3 --> E1
    D4 --> E3
    D5 --> E5
    D6 --> E6
    D7 --> E7
```

---

## 3. 核心组件详解

### 3.1 ContractContextHandler -- 线程级上下文容器

`ContractContextHandler` 是一个基于 `ThreadLocal` 的静态工具类，负责在当前请求线程内存储和读取合同上下文数据。

```mermaid
classDiagram
    class ContractContextHandler {
        -ThreadLocal~ContractContext~ CONTEXT
        +initContext() void
        +clearContext() void
        +getContext() ContractContext
        +setContext(ContractContext) void
        +getProjectInfo() ProjectInfoDTO
        +setProjectInfo(ProjectInfoDTO) void
        +getPlanAllDTO() PlanAllDTO
        +setPlanAllDTO(PlanAllDTO) void
        +getContractSourceDataBO() ContractSourceDataBO
        +getOperatorName() String
        +setOperatorName(String) void
        +getContractReq() ContractReqDTO
        +setContractReq(ContractReqDTO) void
        +getContractCityCompanyInfo() ContractCityCompanyInfo
        +getDrawingDTO() DeliverDrawingDTO
    }

    class ContractContext {
        +ContractReqDTO contractReq
        +ProjectInfoDTO projectInfoDTO
        +PlanAllDTO planAllDTO
        +DeliverDrawingDTO drawingDTO
        +ContractSourceDataBO contractSourceDataBO
        +DesignQuoteFeeDTO designQuoteFeeDTO
        +ContractCityCompanyInfo contractCityCompanyInfo
        +ContractContextEscrowInfo escrowInfo
        +List~ContractCompanyAspectInfo~ contractCompanyList
        +List~ComboDTO~ comboDTOList
        +String operatorName
        +boolean processV25
        +Byte businessType
        +Boolean developerChannel
        +boolean isMergeLaunch
    }

    ContractContextHandler ..> ContractContext : ThreadLocal持有
```

**关键特性：**

| 特性 | 说明 |
|------|------|
| 线程隔离 | 每个请求线程拥有独立的 `ContractContext` 实例，天然线程安全 |
| 生命周期管理 | `@Before` 初始化、业务方法执行、`@After`/`@AfterThrowing` 清除 |
| 空安全 | getter 方法在 `CONTEXT.get() == null` 时返回 null，而非抛出 NPE |
| 便捷访问 | 提供静态方法直接访问常用字段，如 `getPlanAllDTO()`、`getOperatorName()` |

### 3.2 ContractContextAspect -- 合同数据准备切面

`ContractContextAspect` 是模块的核心引擎，拦截所有标注了 `@ContractDataPrepare` 注解的方法，在方法执行前完成合同所需的全量数据准备。切面共创建 **9 个并行任务**：基础信息、报价信息、套餐信息、项目信息、操作人姓名、图纸信息、存管账户、标准设计费、合同主体。

```mermaid
sequenceDiagram
    participant Client as 业务方法
    participant Aspect as ContractContextAspect
    participant Handler as ContractContextHandler
    participant Parallel as ParallelTaskService
    participant RPC as 外部RPC服务

    Client->>Aspect: Before 拦截
    Aspect->>Handler: initContext()
    Aspect->>Aspect: preHandleParam 参数预处理
    Aspect->>Aspect: dealReContractLaunch 撤销旧合同
    Aspect->>Handler: setContractReq(reqDTO)
    Aspect->>Parallel: 创建并行任务组

    par 并行数据加载
        Aspect->>RPC: dealBaseInfo 基础信息
        Aspect->>RPC: dealPlanAllDTO 报价信息
        Aspect->>RPC: dealComboInfo 套餐信息
        Aspect->>RPC: dealProjectInfo 项目信息
        Aspect->>RPC: getOperatorName 操作人
        Aspect->>RPC: dealDrawingDTO 图纸信息
        Aspect->>RPC: dealEscrowDTO 存管账户
        Aspect->>RPC: dealStandardDesignAmountDTO 设计费
        Aspect->>RPC: dealMultiCompanyInfo 合同主体
    end

    Aspect->>Parallel: execTasks + awaitTasksResult
    Aspect->>Handler: 设置城市分公司信息
    Aspect->>Aspect: 计算合同模式
    Aspect->>Aspect: 设计费预处理

    Aspect-->>Client: 数据准备完成，执行业务方法

    Client->>Aspect: After
    Aspect->>Handler: clearContext()
```

#### 3.2.1 参数预处理流程 (preHandleParam)

参数预处理是数据准备的第一步，负责清理和规范化前端传入的请求参数：

```mermaid
flowchart TD
    A[接收 ContractReqDTO] --> B{是否为提交请求}
    B -->|是| C[标记 contractSubmit true]
    B -->|否| D[标记 contractSubmit false]
    C --> E{签章信息存在}
    D --> E
    E -->|是| F[preHandleSignInfoParam 签章预处理]
    E -->|否| G[preHandleProjectParam 项目参数处理]
    F --> G

    subgraph SignSub[签章预处理]
        F1[设计变更或正签变更 设计费来源设为合同]
        F2{签约形式}
        F2 -->|公对公| F3[清空个人签约数据]
        F2 -->|个人签约| F4[清空公对公数据]
        F3 --> F5{是否有代理人}
        F4 --> F5
        F5 -->|无| F6[清空代理人数据]
        F5 -->|有| F7[保留代理人数据]
        F6 --> F8{线上签约}
        F7 --> F8
        F8 -->|是| F9[清空线下合同字段]
        F8 -->|否| F10[保留线下字段]
        F1 --> F2
    end
```

#### 3.2.2 报价信息准备 (dealPlanAllDTO)

报价信息的准备逻辑因合同类型不同而有显著差异：

```mermaid
flowchart TD
    A[接收合同类型] --> B{合同类型}
    B -->|首期款 ADVANCE| C{是否翻新全案}
    C -->|是| C1[直接返回]
    C -->|否| C2{支持预估报价}
    C2 -->|是| C3[dealAdvancePreQuotation 实时校验报价单]
    C2 -->|否| C4[查询套餐价格获取预估合同额]

    B -->|正签或套餐变更或出图或个人| D{是否2.5变更协同签约}
    D -->|是| E[buildAtomChangeQuotation 请求中控报价]
    D -->|否| F{是否个人合同}
    F -->|是| G[queryPersonalQuoteInfoV2 个人报价查询]
    F -->|否| H[contractSourceDate 通用报价获取]

    B -->|其他类型| I[跳过报价准备]
```

#### 3.2.3 图纸信息准备 (dealDrawingDTO)

图纸信息的获取路径同样按合同类型和业务类型区分：

| 条件 | 数据来源 |
|------|---------|
| 团装2.5正签 | `contractBusinessService.getGroupDrawingDTO()` |
| 套餐变更 | `atomDrawingRpc.getChangeListDrawings()` |
| 个人合同 | `contractSigningSourceRouter.route().buildPersonalDrawing()` |
| 其他正签 | `atomDrawingRpc.listDrawings()` |

仅当合同类型属于 `[正签, 出图, 个人, 套餐变更]` 且流程版本为 V2.5 时才加载图纸数据。

### 3.3 ContractDetailContextHandler -- 合同详情上下文容器

`ContractDetailContextHandler` 是合同详情查询场景的上下文管理器，结构与 `ContractContextHandler` 类似，但存储的是详情查询专用的 `ContractDetailContext`。

```mermaid
classDiagram
    class ContractDetailContextHandler {
        -ThreadLocal~ContractDetailContext~ CONTEXT
        +initContext() void
        +clearContext() void
        +getContext() ContractDetailContext
        +getDrawingUrl() String
        +getAtomChangeScopeList() List
        +isFirstScreen() boolean
        +getPlanAllDTO() PlanAllDTO
        +getContractSourceDataBO() ContractSourceDataBO
    }

    class ContractDetailContext {
        +ProjectInfoDTO projectInfoDTO
        +PlanAllDTO planAllDTO
        +DeliverDrawingDTO drawingDTO
        +ContractSourceDataBO contractSourceDataBO
        +LightQuotationItem preQuotationDTO
        +List~Integer~ atomChangeScopeList
        +String drawingUrl
        +FundInfo relateFundInfo
        +AuditDetailDto auditDetailDTO
        +List~ChangeListDTO~ changeOrderList
        +AttachInfoDetail attachInfoDetail
        +DesignSignPriceInfo designSignPriceInfo
        +List~ComboDTO~ comboDTOList
        +boolean isFirstScreen
        +Byte businessType
        +boolean processV25
        +DesignQuoteFeeDTO designQuoteFeeDTO
    }

    ContractDetailContextHandler ..> ContractDetailContext : ThreadLocal持有
```

**首屏优化策略**：当请求参数 `isFirstScreen=true` 时，`ContractDetailAspect` 仅加载 3 项轻量数据（项目信息、附件信息、设计费），而非全量 8 项，显著缩短首屏响应时间。

**已知风险**：`ContractDetailContextHandler` 的 getter 方法缺少 null 安全检查（与 `ContractContextHandler` 不同），在上下文未初始化时存在 NPE 风险。

### 3.4 ContractDetailService -- 合同详情组装服务

`ContractDetailService` 负责将上下文中预加载的数据组装为完整的合同详情响应，主要入口方法为 `initContractDetail`。

```mermaid
flowchart TD
    A[initContractDetail] --> B{首屏请求}
    B -->|是| C[组装4个核心对象]
    B -->|否| D[组装全量12+子模块]

    C --> C1[contractBaseInfo]
    C --> C2[signInfo]
    C --> C3[businessInfo]
    C --> C4[projectInfo]

    D --> D1[buildContractProjectInfoDetail]
    D --> D2[buildContractSignInfoDetail]
    D --> D3[buildContractAttachInfo]
    D --> D4[buildQuotationDetail]
    D --> D5[buildPersonalQuotationDetail]
    D --> D6[活动信息]
    D --> D7[承诺信息]
    D --> D8[流程信息]
    D --> D9[金额信息]
    D --> D10[个人收款计划]
    D --> D11[补充项]
    D --> D12[结算项]
```

---

## 4. 模块间依赖关系

```mermaid
graph LR
    subgraph CtxMod[contract_context 核心模块]
        A1[ContractContextAspect]
        A2[ContractContextHandler]
    end

    subgraph DetMod[contract_detail 详情模块]
        B1[ContractDetailAspect]
        B2[ContractDetailContextHandler]
        B3[ContractDetailService]
    end

    subgraph ValMod[contract_validation 校验模块]
        C1[ContractFieldCheckService]
        C2[WorkerTypeCheckService]
    end

    subgraph ChgMod[change_contract_strategy 变更策略模块]
        D1[ChangeContractStrategyFactory]
        D2[NormalChangeContractStrategy]
        D3[ZQChangeContractStrategy]
    end

    subgraph PdfMod[contract_pdf_by_self 自生成PDF模块]
        E1[DrawingContractPdfBySelfStrategy]
        E2[GroupFormalContractPdfBySelfStrategy]
        E3[ReformAllFormalContractPdfBySelfStrategy]
    end

    subgraph TermMod[terminal_contract_pdf 解约PDF模块]
        F1[TerminalContractPdfBuildService]
    end

    subgraph MatMod[material_pdf 物料PDF模块]
        G1[MaterialPdfDiffService]
        G2[MaterialPdfUtil]
    end

    subgraph RelMod[personal_relation 个人关系模块]
        H1[PersonalRelationHandler]
        H2[PersonalRelationHandlerImpl]
    end

    subgraph SrcMod[contract_signing_source 签约来源模块]
        I1[ContractSigningSource]
        I2[BillSigningSourceStrategy]
        I3[ChangeOrderSigningSourceStrategy]
        I4[SubOrderSigningSourceStrategy]
    end

    A1 -->|上下文管理| A2
    A1 -->|获取设计师等级| B3
    A1 -->|变更合同报价处理| D1
    A1 -->|个人合同图纸路由| I1
    B1 -->|上下文管理| B2
    B3 -->|读取预加载数据| B2
    B3 -->|字段校验| C1
    D1 -->|设计变更策略| D2
    D1 -->|套餐变更策略| D3
```

| 依赖模块 | 依赖方式 | 说明 |
|---------|---------|------|
| [contract_detail](contract_detail.md) | `ContractDetailService.getDesignerLevelName()` | 上下文切面在设计费预处理时调用详情服务获取设计师等级 |
| [change_contract_strategy](change_contract_strategy.md) | `ChangeContractUnifyService` | 报价准备中变更合同走统一变更服务，间接使用策略工厂 |
| [contract_signing_source](contract_signing_source.md) | `ContractSigningSourceRouter` | 个人合同图纸获取时通过签约来源路由选择对应策略 |
| [contract_validation](contract_validation.md) | 间接依赖 | 校验模块在数据准备完成后执行，读取上下文中的数据进行字段校验 |
| [personal_relation](personal_relation.md) | 间接依赖 | 个人关系处理依赖上下文中已准备的签约信息 |
| [contract_pdf_by_self](contract_pdf_by_self.md) | 间接依赖 | PDF生成依赖上下文中已准备的报价、图纸等数据 |
| [terminal_contract_pdf](terminal_contract_pdf.md) | 间接依赖 | 解约PDF生成依赖上下文中的签约主体信息 |
| [material_pdf](material_pdf.md) | 间接依赖 | 物料PDF差异比对依赖上下文中的套餐/报价数据 |

---

## 5. 数据流全景

```mermaid
flowchart TD
    subgraph Entry[请求入口]
        R1[HomeController contract/submit]
        R2[PCController contract/submit]
        R3[PCController changeContract/submit]
        R4[HomeController changeContract/submit]
    end

    subgraph Phase1[数据准备 Phase 1 - 参数预处理]
        P1[识别请求类型 提交 vs 保存草稿]
        P2[签章参数规范化]
        P3[项目参数补齐默认值]
        P4[撤销可重复发起的旧合同]
    end

    subgraph Phase2[数据准备 Phase 2 - 并行RPC加载]
        Q1[基础信息 developerChannel]
        Q2[报价信息 PlanAllDTO / ContractSourceDataBO]
        Q3[套餐信息 ComboDTOList]
        Q4[项目信息 ProjectInfoDTO]
        Q5[操作人 operatorName]
        Q6[图纸信息 DrawingDTO]
        Q7[存管账户 EscrowInfo]
        Q8[标准设计费 DesignSignPriceInfo]
        Q9[合同主体 CompanyAspectInfoList]
    end

    subgraph Phase3[数据准备 Phase 3 - 后处理]
        T1[城市分公司配置]
        T2[合同模式计算]
        T3[设计费来源合并]
    end

    subgraph Ctx[上下文存储]
        CTX[ContractContext ThreadLocal]
    end

    subgraph Consumers[消费者]
        S1[ContractSaveDraftService 保存草稿]
        S2[ContractSubmitService 提交合同]
        S3[ContractFieldCheckService 字段校验]
        S4[PDF生成服务]
    end

    R1 --> P1
    R2 --> P1
    R3 --> P1
    R4 --> P1
    P1 --> P2
    P2 --> P3
    P3 --> P4
    P4 --> Q1
    P4 --> Q2
    P4 --> Q3
    P4 --> Q4
    P4 --> Q5
    P4 --> Q6
    P4 --> Q7
    P4 --> Q8
    P4 --> Q9
    Q1 --> CTX
    Q2 --> CTX
    Q3 --> CTX
    Q4 --> CTX
    Q5 --> CTX
    Q6 --> CTX
    Q7 --> CTX
    Q8 --> CTX
    Q9 --> CTX
    CTX --> T1
    T1 --> T2
    T2 --> T3
    CTX --> S1
    CTX --> S2
    CTX --> S3
    CTX --> S4
```

---

## 6. 关键设计模式

### 6.1 AOP 横切模式

模块采用 Spring AOP 的 `@Aspect` + 自定义注解模式，将数据准备逻辑从业务代码中剥离：

```mermaid
flowchart LR
    A[业务方法标注 ContractDataPrepare] --> B[AOP代理拦截]
    B --> C[ContractContextAspect.beforeHandle]
    C --> D[并行数据加载]
    D --> E[写入 ThreadLocal 上下文]
    E --> F[执行业务方法]
    F --> G[ContractContextAspect.afterHandle]
    G --> H[清除 ThreadLocal 上下文]
```

**优势**：业务代码只需声明 `@ContractDataPrepare` 注解即可获得完整的数据准备能力，无需编写任何数据获取代码。

### 6.2 并行任务编排模式

通过 `ParallelTaskService` 实现多任务并行执行，显著降低数据准备的总耗时：

```mermaid
sequenceDiagram
    participant Main as 主线程
    participant Pool as ParallelTaskService

    Main->>Pool: newParallelTasks()
    Main->>Pool: addTask(基础信息)
    Main->>Pool: addTask(报价信息)
    Main->>Pool: addTask(项目信息)
    Main->>Pool: addTask(图纸信息)
    Main->>Pool: addTask(存管账户)
    Main->>Pool: addTask(合同主体)
    Main->>Pool: addTask(操作人)
    Main->>Pool: addTask(套餐信息)
    Main->>Pool: addTask(设计费)

    Main->>Pool: execTasks()
    Note over Pool: 并行执行所有任务
    Main->>Pool: awaitTasksResult()
    Note over Main: 所有任务完成后继续
```

9 个独立的数据加载任务并行执行，总耗时约等于最慢的单个 RPC 调用耗时，而非所有调用之和。`ParallelTaskService` 底层使用 `CountDownLatch` 实现同步等待，默认超时 20 秒，支持失败重试机制。

### 6.3 策略路由模式

合同上下文模块中的数据准备逻辑根据不同合同类型、业务类型、流程版本等维度采用不同的处理策略：

| 维度 | 策略分支示例 |
|------|------------|
| 合同类型 | 正签/首期款/变更/出图/个人/设计费/存管/解约 |
| 业务类型 | 户证/团装/翻新全案 |
| 流程版本 | V2.5 vs 旧版本 |
| 签约形式 | 个人签约 vs 公对公签约 |
| 签约渠道 | 线上签约 vs 线下签约 |

这种多维度条件分支的设计使得数据准备逻辑能够精准适配每种业务场景，但也导致了较长的条件判断链。

### 6.4 ThreadLocal 上下文模式

```mermaid
stateDiagram-v2
    [*] --> 初始化 : initContext
    初始化 --> 数据填充 : 并行RPC调用
    数据填充 --> 业务执行 : 所有数据就绪
    业务执行 --> 清理 : afterHandle clearContext
    业务执行 --> 清理 : afterThrowing clearContext
    清理 --> [*]

    state 数据填充 {
        [*] --> 读取请求参数
        读取请求参数 --> 调用RPC服务
        调用RPC服务 --> 写入ThreadLocal
        写入ThreadLocal --> [*]
    }

    state 业务执行 {
        [*] --> 从ThreadLocal读取数据
        从ThreadLocal读取数据 --> 执行业务逻辑
        执行业务逻辑 --> [*]
    }
```

**生命周期保证**：
- `@Before` 初始化 + 数据填充
- 业务方法执行 从上下文读取
- `@After` + `@AfterThrowing` 双保险清除，避免 ThreadLocal 内存泄漏

---

## 7. 线程安全与风险点

| 风险项 | 说明 | 缓解措施 |
|--------|------|---------|
| ThreadLocal 内存泄漏 | 线程池复用时若上下文未清除会累积 | `@After` 和 `@AfterThrowing` 双重清除 |
| ContractDetailContextHandler 空安全 | getter 方法缺少 null 检查，上下文未初始化时 NPE | 建议参照 `ContractContextHandler` 增加 null 安全检查 |
| 并行任务异常传播 | 单个 RPC 失败可能导致整个数据准备失败 | `ParallelTaskService.awaitTasksResult` 内置异常收集与传播机制，通过 Future 获取异常并统一抛出 |
| 嵌套并行任务 | `buildAtomChangeQuotation` 内部再次创建并行任务组 | 需确保父子任务组之间不产生资源竞争 |
| 并行任务超时 | 默认超时 20 秒，超时后取消所有未完成任务 | `awaitTasksResult` 使用 `CountDownLatch.await(timeout)` 控制超时，超时后主动 cancel |
