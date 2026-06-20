# contract_core_services 模块概览

## 1. 模块目的

`contract_core_services` 模块是合同系统的核心业务逻辑层，负责管理合同的完整生命周期。其核心目标是为上层应用（如前端、API层）提供创建、查看、编辑、保存草稿、校验、签署、盖章等核心合同业务能力。该模块通过组合多个功能明确、职责单一的子模块，实现了高度内聚、松散耦合的合同业务处理逻辑。

## 2. 模块架构

下图展示了 `contract_core_services` 模块的整体架构、内部子模块的构成及其与外部功能模块的依赖关系。

```mermaid
graph TB
    subgraph “contract_core_services 模块”
        subgraph “内部子模块 (Internal Submodules)”
            CDDC[“contract_detail_and_config<br>详情与配置”]
            CSSS[“contract_seal_and_sign<br>签署与盖章”]
            CDCP[“contract_draft_and_process_control<br>草稿与流程控制”]
        end

        SRV[“合同核心服务层<br>(ContractCoreService Facade/Controllers)”]
    end

    subgraph “外部功能子模块 (External Functional Submodules)”
        CC[“contract_context<br>上下文管理”]
        PB[“personal_binding<br>个性化签约源”]
        PCS[“pdf_self_creation_strategy<br>PDF生成策略”]
        CMS[“contract_modification_strategy<br>合同变更策略”]
        TS[“terminal_pdf_and_material<br>终端PDF与物料”]
        UC[“utility_and_check<br>工具与检查”]
        ES[“escrow_scripting<br>托管脚本”]
    end

    SRV --> CDDC
    SRV --> CSSS
    SRV --> CDCP

    CDDC -- “使用数据验证与配置” --> CC
    CSSS -- “使用详情与按钮服务” --> CDDC
    CSSS -- “触发PDF生成” --> PCS
    CDCP -- “依赖上下文与个性化” --> CC
    CDCP -- “依赖个性化拆分” --> PB
    CDCP -- “涉及合同变更” --> CMS

    CDDC --> TS
    CDDC --> UC
    CSSS --> TS
    CSSS --> ES

    style CDDC fill:#e1f5fe
    style CSSS fill:#e1f5fe
    style CDCP fill:#e1f5fe
```

**架构说明：**
1.  **核心服务层**：作为统一的业务入口（Facade），协调和编排内部三个核心子模块以完成复杂的合同业务流程。
2.  **内部子模块**：
    *   **contract_detail_and_config**：负责合同数据的聚合展示、交互按钮的动态配置以及提交前的数据校验，是面向视图和输入的控制层。
    *   **contract_seal_and_sign**：负责处理在线签署（特别是对公签约的授权协议书）和自助盖章等签署环节的关键业务。
    *   **contract_draft_and_process_control**：负责合同数据的持久化（保存草稿）以及响应特定业务事件（如主订单号变更）对合同数据进行流程控制。
3.  **外部功能子模块**：为内部子模块提供基础能力支持，如上下文管理、策略模式实现、PDF生成等。这些模块与 `contract_core_services` 存在依赖关系，但其设计目标更侧重于提供通用或特定领域的工具与策略。
4.  **数据流与依赖**：请求主要流向 `contract_core_services` 内部。内部子模块间存在协作，例如“签署与盖章”模块依赖“详情与配置”模块获取按钮状态。所有业务模块都依赖“上下文管理”等基础模块来完成具体工作。

## 3. 子模块文档引用

本模块的核心功能由以下内部子模块文档详细定义，它们是理解 `contract_core_services` 具体实现逻辑的关键：

*   **contract_detail_and_config 模块文档**
    *   **核心功能**：合同详情组装、交互按钮配置、数据字段校验。
    *   **文档链接**：`contract_detail_and_config` 模块文档

*   **contract_seal_and_sign 模块文档**
    *   **核心功能**：对公签约与授权协议书管理、自助盖章服务。
    *   **文档链接**：`contract_seal_and_sign` 模块文档

*   **contract_draft_and_process_control 模块文档**
    *   **核心功能**：合同草稿保存、主订单号变更等业务事件响应与数据处理。
    *   **文档链接**：`contract_draft_and_process_control` 模块文档