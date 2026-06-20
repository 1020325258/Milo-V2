# v2 仓库概览

## 1. 仓库目的

本仓库是**合同管理系统**的核心业务逻辑层，旨在提供完整的合同生命周期管理能力。其主要职责包括：

- **合同数据准备**：通过 AOP 切面在合同操作前异步获取并聚合来自多个外部服务的数据
- **合同核心业务处理**：涵盖合同创建、编辑、保存草稿、校验、签署、盖章等完整流程
- **合同变更管理**：支持不同合同类型的差异化变更处理策略
- **PDF 文档生成**：自动生成各类合同 PDF 文件（图纸合同、团装合同、翻新合同等）
- **资金存管处理**：管理资金存管合同的业务逻辑
- **业务单据绑定**：处理合同与报价单、S单、变更单之间的绑定关系管理

系统采用面向切面编程（AOP）、策略模式、并行任务执行等设计，确保高效、可扩展的合同业务处理能力。

## 2. 端到端架构

```mermaid
graph TB
    subgraph 客户端
        A[前端应用/API]
    end

    subgraph 核心业务层
        B[contract_context<br/>合同上下文管理]
        C[contract_core_services<br/>合同核心服务]
        D[contract_modification_strategy<br/>合同变更策略]
        E[personal_binding<br/>个性化绑定]
        F[pdf_self_creation_strategy<br/>PDF自生成策略]
        G[escrow_scripting<br/>资金存管脚本]
        H[terminal_pdf_and_material<br/>终端PDF与材料]
        I[utility_and_check<br/>工具与校验]
    end

    subgraph 外部服务
        J[RPC服务<br/>(项目、报价、图纸等)]
        K[文件存储服务<br/>(S3)]
        L[协议平台<br/>(Freeform)]
        M[人员信息<br/>(Ceres)]
    end

    subgraph 数据层
        N[(数据库)]
    end

    A --> C
    C --> B
    C --> D
    C --> E
    C --> F
    C --> G
    C --> H
    C --> I
    
    B --> J
    F --> K
    F --> L
    G --> K
    H --> K
    E --> J
    I --> M
    
    C --> N
    D --> N
    E --> N
    G --> N
    H --> N

    style A fill:#e1f5fe
    style B fill:#f9f,stroke:#333,stroke-width:2px
    style C fill:#e8f5e8,stroke:#1b5e20,stroke-width:2px
    style D fill:#f3e5f5,stroke:#4a148c,stroke-width:2px
    style E fill:#fff3e0,stroke:#e65100,stroke-width:2px
    style F fill:#fce4ec,stroke:#b71c1c,stroke-width:2px
    style G fill:#f1f8e9,stroke:#33691e,stroke-width:2px
    style H fill:#e0f7fa,stroke:#006064,stroke-width:2px
    style I fill:#f5f5f5,stroke:#616161,stroke-width:2px
```

**架构说明：**
1. **请求流程**：客户端请求首先到达 `contract_core_services` 模块，该模块作为业务编排层协调其他核心模块
2. **数据准备**：`contract_context` 通过 AOP 切面在业务方法执行前异步获取外部数据
3. **业务处理**：根据合同类型和操作类型，路由到不同的策略模块（如变更策略、PDF生成策略）
4. **外部集成**：通过 RPC 调用获取项目、报价、图纸等信息，通过 S3 存储和协议平台管理文档
5. **数据持久化**：所有业务数据最终持久化到数据库

## 3. 核心模块文档引用

以下是本仓库的核心模块及其文档说明：

### 3.1 合同上下文管理模块
- **模块名称**：`contract_context`
- **核心功能**：通过 AOP 切面在合同操作前异步获取、聚合和准备上下文数据
- **关键组件**：`ContractContextAspect`、`ContractDetailAspect`、`ContractContextHandler`
- **文档链接**：[contract_context 模块文档](./contract_context.md)

### 3.2 合同核心服务模块
- **模块名称**：`contract_core_services`
- **核心功能**：管理合同完整生命周期，包括详情展示、草稿保存、字段校验、签署盖章等
- **内部子模块**：
  - `contract_detail_and_config`：合同详情与配置
  - `contract_seal_and_sign`：签署与盖章
  - `contract_draft_and_process_control`：草稿与流程控制
- **文档链接**：[contract_core_services 模块文档](./contract_core_services.md)

### 3.3 合同变更策略模块
- **模块名称**：`contract_modification_strategy`
- **核心功能**：为不同类型的合同变更提供差异化的处理逻辑（策略模式）
- **关键组件**：`ChangeContractStrategyFactory`、`NormalChangeContractStrategy`、`ZQChangeContractStrategy`
- **文档链接**：[contract_modification_strategy 模块文档](./contract_modification_strategy.md)

### 3.4 个性化绑定模块
- **模块名称**：`personal_binding`
- **核心功能**：处理合同与业务单据（报价单、S单、变更单）之间的绑定关系管理
- **关键组件**：`PersonalRelationHandler`、`ContractSigningSource` 及其实现策略
- **文档链接**：[personal_binding 模块文档](./personal_binding.md)

### 3.5 PDF自生成策略模块
- **模块名称**：`pdf_self_creation_strategy`
- **核心功能**：为不同类型的合同（图纸合同、团装合同、翻新合同）提供定制化 PDF 生成策略
- **关键组件**：`DrawingContractPdfBySelfStrategy`、`GroupFormalContractPdfBySelfStrategy`
- **文档链接**：[pdf_self_creation_strategy 模块文档](./pdf_self_creation_strategy.md)

### 3.6 资金存管脚本模块
- **模块名称**：`escrow_scripting`
- **核心功能**：处理资金存管合同的业务逻辑，包括合同生成和脚本动态字段构建
- **关键组件**：`ContractEscrowService`、`ContractScriptBuildService`
- **文档链接**：[escrow_scripting 模块文档](./escrow_scripting.md)

### 3.7 终端PDF与材料模块
- **模块名称**：`terminal_pdf_and_material`
- **核心功能**：合同相关 PDF 文件（解约协议、材料清单）的生成、差异检查与处理
- **关键组件**：`TerminalContractPdfBuildService`、`MaterialPdfDiffService`
- **文档链接**：[terminal_pdf_and_material 模块文档](./terminal_pdf_and_material.md)

### 3.8 工具与校验模块
- **模块名称**：`utility_and_check`
- **核心功能**：提供数据校验和基础工具功能，当前核心为工种资格校验服务
- **关键组件**：`WorkerTypeCheckService`
- **文档链接**：[utility_and_check 模块文档](./utility_and_check.md)

## 4. 系统特点

1. **AOP 驱动的数据准备**：通过切面编程实现业务数据的透明化准备，提高代码可维护性
2. **策略模式的应用**：合同变更、PDF 生成等场景采用策略模式，支持灵活扩展
3. **并行任务优化**：数据获取采用并行任务执行，显著提升系统性能
4. **线程安全的上下文管理**：通过 `ThreadLocal` 和 `ContextHandler` 确保请求级别的数据隔离
5. **模块化设计**：各模块职责单一，通过明确的接口进行协作，便于维护和扩展

## 5. 典型业务流程

以**合同创建**为例：
1. 客户端发起合同创建请求
2. `ContractContextAspect` 拦截请求，通过并行任务获取项目、报价、图纸等数据
3. 数据存储在线程安全的 `ContractContext` 中
4. `ContractSaveDraftService` 执行草稿保存逻辑
5. 根据合同类型选择 PDF 生成策略，生成合同文档
6. 通过 S3 上传文档，通过协议平台关联文档
7. 返回合同创建结果

该仓库为合同管理系统提供了坚实的技术基础，支撑了复杂多变的业务需求。