# DemoAgent 模块

DemoAgent 是系统的示例 Agent 模块，包含两个演示性的 AI Agent 实现：**AigcAgent** 和 **ReactAgent**。它们分别展示了两种不同的 Agent 构建模式——简单流式 Agent 和基于 LangGraph 的 React 模式 Agent，为开发者提供了可参考的 Agent 开发模板。

## 架构总览

```mermaid
graph TD
    subgraph DemoAgent模块
        AigcAgent[AigcAgent - 简单流式Agent]
        ReactAgent[ReactAgent - React模式Agent]
    end

    subgraph 基础框架层
        BaseAgent[BaseAgent - Agent基类]
        BaseAgentState[BaseAgentState - 状态基类]
        ApplicationEnum[ApplicationEnum - 应用枚举]
    end

    subgraph LLM与工具层
        LLMManager[LLMManager - 模型管理]
        WeatherTool[WeatherTool - 天气工具]
        SearchTool[搜索工具 MCP]
        CustomerTool[客户信息工具]
    end

    subgraph 消息运行时
        MessagePersistence[MessagePersistence - 消息持久化]
        StageValueHandler[StageValueMessageHandler - 消息整合]
        StreamEvent[StreamEvent - 流式事件]
        ProtocolWrapper[ProtocolWrapper - 协议封装]
    end

    AigcAgent -->|继承| BaseAgent
    ReactAgent -->|继承| BaseAgent
    ReactAgent -->|扩展| BaseAgentState
    BaseAgent -->|引用| ApplicationEnum

    AigcAgent -->|调用| LLMManager
    AigcAgent -->|使用| WeatherTool
    ReactAgent -->|调用| LLMManager
    ReactAgent -->|使用| SearchTool
    ReactAgent -->|使用| CustomerTool

    AigcAgent -->|产出| StreamEvent
    ReactAgent -->|产出| StreamEvent
    AigcAgent -->|通过| StageValueHandler
    AigcAgent -->|通过| MessagePersistence
```

## 核心组件

### AigcAgent

AigcAgent 是一个**简单流式 Agent**，直接使用 LangChain 的 `create_agent` 创建 Agent 实例并以流式模式执行。它不使用 LangGraph 的 StateGraph 编排，而是直接遍历 Agent 的流式输出并转换为系统内部的 `StreamEvent`。

**关键特性：**
- 使用 `Deepseek-Chat` 模型
- 集成天气查询工具（`query_weather_tool`）
- 使用内存 Checkpointer 保持对话上下文
- 自行管理消息聚合和持久化（不走基类的 `execute_stream` 流程）

**执行流程：**

```mermaid
graph TD
    START[接收 ChatRequest] --> SAVE_USER[保存用户消息]
    SAVE_USER --> INIT_HANDLER[初始化消息整合处理器]
    INIT_HANDLER --> PARSE_PAYLOAD[解析文本载荷]
    PARSE_PAYLOAD --> STREAM[agent.astream 流式执行]
    STREAM --> PARSE_CHUNK[解析每个消息块]
    PARSE_CHUNK --> IS_LAST{是否最后一个块?}
    IS_LAST -->|否| YIELD_UPDATING[产出 UPDATING 事件]
    YIELD_UPDATING --> STREAM
    IS_LAST -->|是| YIELD_DONE[产出 DONE 事件]
    YIELD_DONE --> FLUSH[获取完整消息并保存]
    FLUSH --> END_NODE[完成]
```

> **注意：** AigcAgent **重写**了基类的 `execute_stream` 方法，直接调用 `agent.astream()` 而非通过 LangGraph StateGraph 执行。这是因为简单 Agent 无需复杂的图编排。

### ReactAgent

ReactAgent 是一个基于 **LangGraph StateGraph** 的 React 模式（Reasoning + Acting）Agent，实现了完整的思考-执行两阶段工作流。

**关键特性：**
- 使用 `Deepseek-V3.1` 模型
- 动态加载 MCP 搜索工具
- 两阶段节点：`plan_node`（规划）→ `execute_node`（执行）
- 使用 `push_reasoning_stream` 和 `push_message_stream` 便捷方法简化消息推送

**执行流程：**

```mermaid
graph TD
    START[接收 ChatRequest] --> BUILD_STATE[基类构建初始状态]
    BUILD_STATE --> EXTEND[extend_state 扩展自定义字段]
    EXTEND --> GRAPH[StateGraph 流式执行]
    GRAPH --> PLAN[plan_node - 任务规划]
    PLAN --> EXEC[execute_node - 工具执行]
    EXEC --> END_NODE[END]
```

**plan_node 内部逻辑：**

```mermaid
graph TD
    P_START[规划节点开始] --> BUILD_PROMPT[构建规划提示词]
    BUILD_PROMPT --> CALL_LLM[调用 LLM 流式生成]
    CALL_LLM --> PUSH_REASON[push_reasoning_stream 推送思考阶段]
    PUSH_REASON --> RETURN_PLAN[返回 plan_result]
```

**execute_node 内部逻辑：**

```mermaid
graph TD
    E_START[执行节点开始] --> BUILD_MSG[构建执行消息含上下文]
    BUILD_MSG --> CREATE_AGENT[create_dynamic_agent 创建含MCP工具的Agent]
    CREATE_AGENT --> STREAM[astream 流式执行]
    STREAM --> EXTRACT{提取流式内容}
    EXTRACT -->|updates 模式| LOG_TOOL[记录工具调用日志]
    EXTRACT -->|messages 模式| YIELD_TEXT[提取文本内容]
    YIELD_TEXT --> STREAM
    LOG_TOOL --> STREAM
    STREAM --> PUSH_MSG[push_message_stream 推送消息阶段]
    PUSH_MSG --> RETURN_ANSWER[返回 final_answer]
```

## 两种 Agent 的对比

| 维度 | AigcAgent | ReactAgent |
|------|-----------|------------|
| **图编排** | 无，直接调用 LangChain Agent | LangGraph StateGraph |
| **模型** | Deepseek-Chat | Deepseek-V3.1 |
| **工具** | 天气查询（静态） | 客户信息 + MCP 搜索（动态） |
| **阶段** | 单阶段（直接流式输出） | 双阶段（规划 → 执行） |
| **execute_stream** | 自行重写 | 使用基类默认实现 |
| **消息推送** | 手动构建 StreamEvent | 使用 `push_*_stream` 便捷方法 |
| **应用 ID** | 9990002 | 9990001 |
| **适用场景** | 简单问答、快速原型 | 复杂推理、多工具协作 |

## 继承体系

```mermaid
classDiagram
    class BaseAgent {
        +_app_enum: ApplicationEnum
        +checkpointer_backend: CheckpointerBackend
        +application_id: int
        +app_name: str
        +build_graph() StateGraph
        +build_state(request) dict
        +extend_state(request) dict
        +execute_stream(request) AsyncGenerator
        +get_or_create_session() tuple
    }

    class BaseAgentState {
        +ucid: str
        +session_id: str
        +question: str
        +intent: str or None
    }

    class AigcAgent {
        +_app_enum = AIGC_AGENT
        +execute_stream(request) AsyncGenerator
    }

    class ReactAgent {
        +_app_enum = REACT_AGENT
        +build_graph() StateGraph
        +extend_state(request) dict
        +_plan_node(state) dict
        +_execute_node(state) dict
    }

    class ReactAgentState {
        +step: int
        +plan_result: str or None
        +tool_results: list
        +final_answer: str or None
    }

    BaseAgent <|-- AigcAgent
    BaseAgent <|-- ReactAgent
    BaseAgentState <|-- ReactAgentState
    ReactAgent --> ReactAgentState : 使用
```

## 依赖关系

```mermaid
graph LR
    subgraph DemoAgent
        AigcAgent
        ReactAgent
    end

    subgraph ApplicationBase
        BaseAgent
        BaseAgentState
        ApplicationEnum
    end

    subgraph LLMManager
        get_llm
        AIModelName
    end

    subgraph ChatMessage
        StreamEvent
        MessageStage
        MessageStatus
        ProtocolWrapper
    end

    subgraph MessageRuntime
        MessagePersistence
        StageValueMessageHandler
    end

    subgraph WeatherTool
        query_weather_tool
    end

    subgraph ConfigLoader
        create_checkpointer
    end

    AigcAgent --> BaseAgent
    AigcAgent --> LLMManager
    AigcAgent --> ChatMessage
    AigcAgent --> MessageRuntime
    AigcAgent --> WeatherTool
    AigcAgent --> ConfigLoader

    ReactAgent --> BaseAgent
    ReactAgent --> BaseAgentState
    ReactAgent --> LLMManager
    ReactAgent --> MessageRuntime
```

### 外部依赖模块说明

| 依赖模块 | 用途 | 文档链接 |
|---------|------|---------|
| [ApplicationBase](ApplicationBase.md) | 提供 `BaseAgent`、`BaseAgentState`、`ApplicationEnum` 基础框架 | ApplicationBase.md |
| [LLMManager](LLMManager.md) | 提供 `get_llm()` 获取 LLM 模型实例、`AIModelName` 模型名称枚举 | LLMManager.md |
| [ChatMessage](ChatMessage.md) | 提供 `StreamEvent`、`MessageStage`、`MessageStatus` 等消息协议类型 | ChatMessage.md |
| [MessageRuntime](MessageRuntime.md) | 提供 `MessagePersistence` 消息持久化和 `StageValueMessageHandler` 消息聚合 | MessageRuntime.md |
| [WeatherTool](WeatherTool.md) | 提供 `query_weather_tool` 天气查询工具 | WeatherTool.md |

## 数据流

### AigcAgent 数据流

```mermaid
sequenceDiagram
    participant Client as 客户端
    participant Aigc as AigcAgent
    participant MP as MessagePersistence
    participant Agent as LangChain Agent
    participant Handler as StageValueMessageHandler

    Client->>Aigc: ChatRequest
    Aigc->>MP: save_user_message
    Aigc->>Handler: 初始化
    Aigc->>Agent: astream(input, config)
    loop 流式输出
        Agent-->>Aigc: chunk (BaseMessage)
        Aigc->>Aigc: parseChunk 提取文本
        Aigc-->>Client: StreamEvent(UPDATING)
        Aigc->>Handler: merge_event
    end
    Aigc-->>Client: StreamEvent(DONE)
    Aigc->>Handler: flush 获取完整消息
    Aigc->>MP: save_agent_message
```

### ReactAgent 数据流

```mermaid
sequenceDiagram
    participant Client as 客户端
    participant Base as BaseAgent.execute_stream
    participant Graph as StateGraph
    participant Plan as plan_node
    participant Exec as execute_node
    participant LLM as LLM
    participant Agent as LangGraph Agent

    Client->>Base: ChatRequest
    Base->>Base: build_state 构建初始状态
    Base->>Graph: astream(input, config)

    Graph->>Plan: 执行规划节点
    Plan->>LLM: call_llm_simple_stream
    LLM-->>Plan: 流式思考内容
    Plan-->>Client: push_reasoning_stream (REASON阶段)
    Plan->>Graph: 返回 plan_result

    Graph->>Exec: 执行节点
    Exec->>Agent: 创建动态Agent(MCP工具)
    Agent->>Agent: astream 执行工具调用
    Agent-->>Exec: 流式回答
    Exec-->>Client: push_message_stream (MESSAGE阶段)
    Exec->>Graph: 返回 final_answer

    Base->>Base: MessagePersistence 保存消息
```

## 关键设计模式

### 1. 模板方法模式

`BaseAgent` 定义了 Agent 执行的骨架流程（`execute_stream`），子类通过覆盖 `build_graph()`、`extend_state()` 等钩子方法定制具体行为。AigcAgent 则更进一步，完全重写 `execute_stream` 以适配非图编排的场景。

### 2. 状态扩展模式

通过 `extend_state()` 钩子，基类负责通用字段（`ucid`、`session_id`、`question`），子类只需返回自定义字段，两者自动合并。ReactAgent 利用此模式添加 `step`、`plan_result`、`tool_results` 等 React 模式专属状态。

### 3. 便捷消息推送

ReactAgent 使用 `push_reasoning_stream` 和 `push_message_stream` 两个便捷方法，将 StreamEvent 的构建、发送和聚合封装为一行调用，显著简化了节点代码。而 AigcAgent 由于重写了 `execute_stream`，需要手动构建 `StreamEvent` 对象。

### 4. 动态工具加载

ReactAgent 的 `create_dynamic_agent()` 在执行阶段动态获取 MCP 搜索工具并注入 Agent，支持运行时工具集变化。AigcAgent 则使用静态工具列表。
