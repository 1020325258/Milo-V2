# contract_detail_and_config 模块概览

## 1. 模块目的
`contract_detail_and_config` 模块是合同服务的核心业务模块之一，主要负责**合同详情的呈现、交互状态的控制以及数据提交前的业务规则校验**。它是连接复杂后端逻辑与用户界面的“翻译层”和“控制层”，旨在为前端页面（如Home App、PC端）提供结构化的详情数据和动态的按钮配置，同时确保提交的数据符合业务规范。

## 2. 模块架构
该模块由三个紧密协作的核心子模块构成，共同支撑合同详情页面的完整生命周期。

```mermaid
graph TD
    subgraph “contract_detail_and_config 模块”
        CDS[“ContractDetailService<br>详情数据组装”]
        CBCS[“ContractButtonConfigService<br>按钮规则引擎”]
        CFCS[“ContractFieldCheckService<br>数据验证器”]
    end

    subgraph “依赖的基础设施与数据”
        CTX[“ContractDetailContextHandler<br>上下文处理器”]
        BO[“ContractDetailContext<br>上下文数据对象”]
        CFG[“MultidimensionalConfigService<br>多维配置服务”]
        APO[“ContractApolloConfig<br>动态配置”]
        SVC[“其他合同服务<br>（项目、资金、附件等）”]
    end

    subgraph “前端与API层”
        UI[“前端页面”]
        API[“合同API层”]
    end

    UI -- 请求详情/按钮 --> API
    API -- 调用 --> CDS
    API -- 调用 --> CBCS
    API -- 提交数据时调用 --> CFCS

    CDS -- 使用 --> CTX
    CTX -- 管理并预加载数据到 --> BO
    BO -- 聚合数据来自 --> SVC
    CBCS -- 使用规则与表达式配置 --> CFG
    CBCS -- 使用动态阈值 --> APO
    CFCS -- 校验时依赖上下文与配置 --> CTX
    CFCS -- 校验时使用动态规则 --> APO
```

### 架构图说明
1.  **前端请求路径**：前端界面通过API层发起两种主要请求：获取合同详情数据、获取按钮显示状态。
2.  **核心服务组件**：
    *   `ContractDetailService`：负责响应“详情数据”请求。它通过`ContractDetailContextHandler`预加载并获取一个包含多源数据的上下文对象（`ContractDetailContext`），然后组装成结构化的`ContractDetailResp`返回。
    *   `ContractButtonConfigService`：负责响应“按钮配置”请求。它利用基于`Aviator`表达式引擎的规则系统，结合从配置服务和动态配置中读取的规则，计算并返回当前场景下应显示的按钮列表。
    *   `ContractFieldCheckService`：在数据提交流程中被调用。它通过反射机制动态执行一系列校验方法（如`checkIdCardInfo`、`checkBrandList`），依赖上下文信息和配置服务获取校验所需的数据与规则，确保数据合法性。
3.  **数据流**：数据从多个底层服务（如项目、资金、报价服务）汇集到上下文对象，供`ContractDetailService`和`ContractFieldCheckService`消费。配置信息从`MultidimensionalConfigService`和`ContractApolloConfig`流向`ContractButtonConfigService`和`ContractFieldCheckService`。

## 3. 子模块文档引用
本模块的功能由以下两个核心子模块文档详细阐述，它们共同定义了模块的行为细节和实现逻辑：

*   **[展示与交互 模块文档]** (`展示与交互`子模块)
    *   **核心组件**：`ContractDetailService`， `ContractButtonConfigService`
    *   **文档内容**：详细描述了如何聚合多源数据组装合同详情、如何通过规则引擎动态控制按钮显示逻辑，是理解本模块**数据输出和视图控制**能力的关键。

*   **[数据验证 模块文档]** (`数据验证`子模块)
    *   **核心组件**：`ContractFieldCheckService`
    *   **文档内容**：详细说明了采用反射机制的校验框架设计、各种具体校验规则（如身份证校验、金额校验）的实现逻辑及其依赖，是理解本模块**数据输入质量控制**能力的关键。