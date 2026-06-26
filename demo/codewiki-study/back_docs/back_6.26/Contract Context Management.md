# Contract Context Management 模块概览

## 1. 模块目的

**Contract Context Management** 是合同管理系统的**数据准备基础设施层**，负责在合同业务操作执行前，通过 AOP 切面机制自动收集、聚合来自项目、报价、图纸、存管、审核等多个外部服务的数据，并将其缓存到线程级上下文（ThreadLocal）中，供下游业务组件免重复查询地使用。

该模块解决的核心痛点：

- **一次合同操作涉及十余种外部数据源**（项目信息、报价数据、图纸信息、存管账户、套餐数据、审核信息等），串行调用会导致接口响应过慢
- **不同合同类型（正签、变更、解约、设计、存管协议等）所需数据组合各异**，数据准备逻辑分散在业务代码中难以维护
- **数据加载与业务逻辑耦合**，新增数据源需要修改业务代码

模块通过 **声明式注解 + 并行拉取 + ThreadLocal 缓存** 的三层架构，将数据准备逻辑从业务代码中彻底剥离，实现：

- **声明式触发**：业务方法只需添加注解即可自动获得完整数据准备能力
- **并行执行**：所有独立的 RPC 调用通过线程池并发执行，总耗时约等于最慢单个调用
- **零侵入传递**：下游通过静态工具类读取上下文，无需方法签名传参

---

## 2. 子模块组成

本模块包含两个采用相同架构模式的子模块，分别服务于不同的业务场景：

| 子模块 | 触发注解 | 业务场景 | 并行任务数 | 核心特色 |
|--------|---------|---------|-----------|---------|
| **Contract Context Handler** | `@ContractDataPrepare` | 合同提交、预览、保存草稿 | 9 个 | 复杂的参数预处理（个人/公司、线上/线下、权属证明类型等维度清洗） |
| **Contract Detail Context Handler** | `@ContractDetailDataPrepare` | 合同详情查询 | 最多 8 个 | 首屏/非首屏分层加载优化，首屏仅加载 3 个轻量任务 |

两个子模块共享以下基础设施：

- **设计模式**：ThreadLocal Holder 模式（单例静态工具类 + 线程隔离数据）
- **并行编排**：`ParallelTaskService`（addNewTask → execTasks → awaitTasksResult 三步范式）
- **生命周期管理**：AOP `@Before` 初始化、`@After` / `@AfterThrowing` 清除

---

## 3. 模块架构

### 3.1 整体架构图

```mermaid
graph TD
    subgraph 请求入口层
        R1[合同提交/预览请求]
        R2[合同详情查询请求]
    end

    subgraph 声明式拦截层
        A1["ContractContextAspect<br/>@ContractDataPrepare"]
        A2["ContractDetailAspect<br/>@ContractDetailDataPrepare"]
    end

    subgraph 上下文管理层
        H1["ContractContextHandler<br/>ThreadLocal&lt;ContractContext&gt;"]
        H2["ContractDetailContextHandler<br/>ThreadLocal&lt;ContractDetailContext&gt;"]
    end

    subgraph 并行任务编排层
        PTS["ParallelTaskService"]
    end

    subgraph 外部数据源
        E1[ProjectInfoReadService<br/>项目信息]
        E2[QuotationFeignService<br/>报价查询]
        E3[AtomDrawingRpc<br/>图纸服务]
        E4[EscrowDomain<br/>存管服务]
        E5[AtomChangeRpc<br/>变更服务]
        E6[AtomBudgetRpc<br/>预算报价]
        E7[MdmDataRpc / MdmRpc<br/>主数据]
        E8[OrderStandardQueryRpc<br/>套餐查询]
        E9[AuditRpc<br/>风控审核]
        E10[FundInfoService<br/>款项信息]
    end

    subgraph 下游消费方
        D1[ContractCoreServices<br/>合同保存/校验/草稿]
        D2[ContractPDFGeneration<br/>PDF生成]
        D3[ContractDetailService<br/>详情组装]
    end

    R1 --> A1
    R2 --> A2

    A1 -->|init/clear| H1
    A2 -->|init/clear| H2

    A1 -->|并行任务| PTS
    A2 -->|并行任务| PTS

    PTS --> E1
    PTS --> E2
    PTS --> E3
    PTS --> E4
    PTS --> E5
    PTS --> E6
    PTS --> E7
    PTS --> E8
    PTS --> E9
    PTS --> E10

    PTS -->|写入| H1
    PTS -->|写入| H2

    H1 -->|getContext| D1
    H1 -->|getContext| D2
    H2 -->|getContext| D3
```

### 3.2 子模块协作关系

```mermaid
graph LR
    subgraph Contract_Context_Management["Contract Context Management"]
        CCH["Contract Context Handler<br/>合同提交/预览场景"]
        CDCH["Contract Detail Context Handler<br/>合同详情查询场景"]
    end

    subgraph 相关模块
        CCS["Contract Core Services"]
        CPF["Contract PDF Generation"]
        CRS["Contract Change Strategy"]
        PRS["Personal Relation & Signing"]
    end

    CCH -->|数据提供| CCS
    CCH -->|数据提供| CPF
    CDCH -->|调用| CCS
    CDCH -->|触发| CPF
    CDCH -->|查询| CRS
    CDCH -->|查询| PRS

    CCH -.->|共享设计模式| CDCH
    CCH -.->|共享 ContractDetailService| CDCH
```

### 3.3 请求全链路数据流

```mermaid
sequenceDiagram
    participant FE as 前端
    participant Ctrl as Controller
    participant Aspect as AOP 切面
    participant Handler as ContextHandler
    participant PTS as ParallelTaskService
    participant RPC as 外部 RPC 服务
    participant CTX as Context 数据载体
    participant Biz as 下游业务服务

    FE->>Ctrl: HTTP 请求
    Ctrl->>Aspect: @Before 拦截
    Aspect->>Handler: initContext()
    Aspect->>Aspect: 参数预处理（Contract Context Handler 特有）

    Aspect->>PTS: 提交并行数据拉取任务
    par 并行执行
        PTS->>RPC: 任务 1（项目信息）
        PTS->>RPC: 任务 2（报价信息）
        PTS->>RPC: 任务 3（图纸/存管/审核等）
    end
    RPC-->>CTX: 写入 Context
    PTS-->>Aspect: 全部任务完成

    Aspect->>Aspect: 后置处理（城市配置/合同模式等）
    Aspect->>Ctrl: 执行目标方法

    Ctrl->>Biz: 业务逻辑
    Biz->>Handler: getContext() 读取数据
    Handler-->>Biz: 返回 Context
    Biz-->>Ctrl: 返回结果
    Ctrl-->>FE: HTTP 响应

    Aspect->>Handler: @After → clearContext()
```

---

## 4. 关键设计模式

### 4.1 ThreadLocal 上下文模式

每个请求线程拥有独立的数据副本，通过 `initContext()` → 业务执行 → `clearContext()` 的生命周期保证数据隔离和内存安全。

```mermaid
flowchart LR
    subgraph Thread1[线程 A]
        T1C[Context A]
    end
    subgraph Thread2[线程 B]
        T2C[Context B]
    end
    subgraph Thread3[线程 C]
        T3C[Context C]
    end

    Handler[ContextHandler]
    Handler -->|CONTEXT.get| T1C
    Handler -->|CONTEXT.get| T2C
    Handler -->|CONTEXT.get| T3C
```

### 4.2 AOP 拦截器模式

```mermaid
flowchart TD
    A["业务方法标注注解"] --> B["Spring AOP 代理拦截"]
    B --> C["@Before: 数据准备（并行加载）"]
    C --> D["执行业务方法（数据已在 Context 中）"]
    D --> E["@After: 清除 Context"]
    D -.-> F["@AfterThrowing: 异常时也清除 Context"]
```

### 4.3 并行任务编排模式

所有独立的远程调用通过 `ParallelTaskService` 并发执行，总耗时约等于最慢单个调用。典型场景下从串行的 2-3 秒降至约 500ms。

### 4.4 条件短路过滤

每个数据准备方法内部通过合同类型、业务模式等条件判断是否需要执行，不满足条件直接返回，避免无意义的 RPC 调用。

---

## 5. 子模块文档索引

| 子模块 | 说明 |
|--------|------|
| [Contract Context Handler](Contract Context Handler.md) | 合同提交/预览场景的数据准备模块，9 个并行任务，含复杂参数预处理逻辑 |
| [Contract Detail Context Handler](./Contract%20Detail%20Handler.md) | 合同详情查询场景的数据准备模块，首屏/非首屏分层加载优化，15+ 数据字段的详情组装 |

---

## 6. 与系统其他模块的关系

| 模块 | 关系 | 说明 |
|------|------|------|
| **Contract Core Services** | 上游消费方 | 通过 `ContractContextHandler.getContext()` 获取已准备的数据，执行合同保存、校验、草稿等核心操作 |
| **Contract PDF Generation** | 上游消费方 | 依赖上下文中的图纸、报价、项目信息生成 PDF 合同文档 |
| **Contract Change Strategy** | 协作方 | 变更合同的报价差异计算在 Context 模块中触发，策略选择在变更策略模块中完成 |
| **Personal Relation & Signing** | 协作方 | 个人合同的图纸获取通过 `ContractSigningSourceRouter` 路由到该模块的策略实现 |