# ApiMiddleware 模块文档

## 模块概述

ApiMiddleware 是基于 Starlette ASGI 框架构建的 HTTP 请求处理中间件层，位于 API 路由处理器之前，为所有进入系统的 HTTP 请求提供统一的横切关注点处理。该模块包含三个中间件组件，分别负责 **请求认证**、**请求日志记录** 和 **链路追踪 ID 生成**，三者协同构成完整的请求预处理管线。

模块的核心设计目标：
- **安全性**：通过 Token 验证确保只有合法用户可访问受保护的 API
- **可观测性**：通过日志记录和 TraceId 实现请求全链路追踪
- **流式兼容**：日志和 TraceId 中间件采用纯 ASGI 实现，避免 `BaseHTTPMiddleware` 与 SSE（Server-Sent Events）流式响应的兼容性问题

## 架构总览

```mermaid
graph TD
    Client[客户端] --> MW1[TraceIdMiddleware]
    MW1 --> MW2[AuthMiddleware]
    MW2 --> MW3[RequestLoggingMiddleware]
    MW3 --> Router[FastAPI Router]
    Router --> Handler[API Handler]

    subgraph APIMiddleware[ApiMiddleware 模块]
        MW1
        MW2
        MW3
    end

    MW2 -->|验证 Token| SessionClient[SessionRpcClient]
    MW2 -->|读取跳过路径| Config[ConfigLoader]
    MW1 -->|设置 trace_id| LogConfig[LogConfig]
```

中间件按以下顺序执行（从外到内）：

1. **TraceIdMiddleware** — 最先执行，生成或提取 TraceId 并注入日志上下文
2. **AuthMiddleware** — 校验用户身份，将 `ucid` 注入请求头
3. **RequestLoggingMiddleware** — 记录完整的请求/响应日志

## 核心组件详解

### TraceIdMiddleware

**文件路径**：`api/middlewares/trace_id.py`

**实现方式**：纯 ASGI 中间件（直接实现 `__call__` 协议）

**职责**：为每个 HTTP 请求生成全局唯一的追踪标识符，贯穿请求处理全生命周期。

#### 处理流程

```mermaid
flowchart TD
    A[接收 HTTP 请求] --> B{请求头中是否携带 X-Nrs-Agent-Trace-Id}
    B -->|是| C[提取客户端传入的 trace_id]
    B -->|否| D[生成 UUID 作为 trace_id]
    C --> E[存入 scope state]
    D --> E
    E --> F[调用 set_trace_id 写入日志上下文变量]
    F --> G[包装 send 函数]
    G --> H[执行下游中间件]
    H --> I[响应头中附加 X-Nrs-Agent-Trace-Id]
```

#### 关键设计

| 特性 | 说明 |
|------|------|
| TraceId 传递 | 优先使用客户端传入的 `X-Nrs-Agent-Trace-Id` 头，否则自动生成 UUID |
| 日志上下文集成 | 通过 `contextvars` 实现的 `set_trace_id()` 将 TraceId 绑定到当前协程，确保同一线程/协程内所有日志自动携带该 ID |
| 响应回写 | 包装 `send` 函数，在 `http.response.start` 阶段将 TraceId 追加到响应头，便于客户端关联请求 |
| SSE 兼容 | 仅操作 scope 和 send 包装，不缓存响应体，对流式响应零影响 |

### AuthMiddleware

**文件路径**：`api/middlewares/auth.py`

**实现方式**：继承 `BaseHTTPMiddleware`（Starlette 提供的高层抽象）

**职责**：验证请求身份的合法性，将用户标识（`ucid`）注入请求头供下游使用。

#### 处理流程

```mermaid
flowchart TD
    A[接收请求] --> B{HTTP 方法是否为 GET/POST}
    B -->|否| C[直接放行]
    B -->|是| D{路径是否在 skip_paths 中}
    D -->|是| C
    D -->|否| E{请求头中是否有 Lianjia-Access-Token}
    E -->|有| F[调用 session_client.verify_token]
    E -->|无| G{环境是否为 test/dev}
    G -->|是| H{是否有 X-Nrs-User-Id 头}
    H -->|有| C
    H -->|无| I[返回 401]
    G -->|否| I
    F --> J{ucid 是否有效}
    J -->|是| K[将 ucid 注入 X-Nrs-User-Id 请求头]
    K --> C
    J -->|否| I
```

#### 关键设计

| 特性 | 说明 |
|------|------|
| Token 来源 | 从 `Lianjia-Access-Token` 请求头提取 |
| 认证绕过 | 通过 `config.auth.skip_paths` 配置无需认证的路径前缀（如健康检查端点） |
| 开发便利性 | test/dev 环境下支持直接通过 `X-Nrs-User-Id` 头传入用户 ID，跳过 Token 验证 |
| 身份注入 | 验证成功后通过修改 `request._headers`（Starlette 私有属性）将 ucid 注入请求头，下游路由可通过 `X-Nrs-User-Id` 获取当前用户 |
| Token 验证 | 调用 [RpcClient](RpcClient.md) 模块的 `SessionRpcClient.verify_token()` 远程验证 Token 有效性 |

#### 环境差异行为

| 环境 | 无 Token 时的行为 |
|------|------------------|
| test / dev | 允许通过 `X-Nrs-User-Id` 头直接指定用户 |
| 其他环境（preview/prod） | 必须提供有效 Token，否则返回 401 |

### RequestLoggingMiddleware

**文件路径**：`api/middlewares/logging.py`

**实现方式**：纯 ASGI 中间件

**职责**：记录完整的请求和响应信息，用于调试和审计。

#### 处理流程

```mermaid
flowchart TD
    A[接收 HTTP 请求] --> B{是否为 SSE 流式请求}
    B -->|是| C[仅记录请求信息]
    C --> D[直接透传响应 不缓存]
    B -->|否| E[记录请求信息]
    E --> F[包装 receive 读取请求体]
    F --> G[包装 send 缓存响应体]
    G --> H[执行下游中间件]
    H --> I[计算耗时]
    I --> J[记录响应信息]
```

#### 请求日志内容

| 字段 | 来源 | 说明 |
|------|------|------|
| method | `scope["method"]` | HTTP 方法 |
| path | `scope["path"]` | 请求路径 |
| query_string | `scope["query_string"]` | 查询参数 |
| headers | `scope["headers"]` | 请求头（已过滤 authorization、cookie） |
| body | `receive` 包装 | POST/PUT/PATCH 的 JSON 请求体 |

#### 响应日志内容

| 字段 | 来源 | 说明 |
|------|------|------|
| status_code | `http.response.start` | HTTP 状态码 |
| duration_ms | 计算值 | 请求处理耗时（毫秒） |
| body | `http.response.body` 缓存 | JSON 响应体 |

#### SSE 兼容性设计

对于流式请求（路径以 `/stream` 结尾或 Accept 为 `text/event-stream`），中间件采用**单向透传**策略：
- **请求阶段**：记录请求信息（方法、路径、头、体）
- **响应阶段**：直接透传，不缓存响应体，避免内存溢出和流式延迟

## 依赖关系

```mermaid
graph LR
    AuthMiddleware -->|远程调用| SessionClient[SessionRpcClient]
    AuthMiddleware -->|读取配置| ConfigLoader
    TraceIdMiddleware -->|设置上下文| LogConfig
    SessionClient -->|继承| HttpClient[BaseAsyncHttpClient]
    ConfigLoader -->|加载 YAML| ConfigFiles[config/*.yaml]

    subgraph APIMiddleware[ApiMiddleware]
        AuthMiddleware
        TraceIdMiddleware
        RequestLoggingMiddleware
    end

    subgraph ExternalDeps[外部依赖]
        SessionClient
        ConfigLoader
        LogConfig
    end
```

| 中间件 | 依赖模块 | 依赖方式 | 用途 |
|--------|---------|---------|------|
| AuthMiddleware | [RpcClient](RpcClient.md) | `session_client.verify_token()` | Token 远程验证 |
| AuthMiddleware | [ConfigLoader](ConfigLoader.md) | `config.auth.skip_paths` | 读取免认证路径 |
| TraceIdMiddleware | [LogConfig](LogConfig.md) | `set_trace_id()` | 将 TraceId 写入日志上下文 |
| RequestLoggingMiddleware | loguru | `logger.info()` | 输出结构化日志 |

## 请求处理时序

```mermaid
sequenceDiagram
    participant C as Client
    participant T as TraceIdMiddleware
    participant A as AuthMiddleware
    participant L as RequestLoggingMiddleware
    participant R as Router
    participant S as SessionRpcClient

    C->>T: HTTP Request
    Note over T: 生成/提取 trace_id
    T->>T: set_trace_id 写入上下文
    T->>A: 转发请求

    alt 路径在 skip_paths 中
        A->>L: 直接转发
    else 需要认证
        A->>S: verify_token(access_token)
        S-->>A: 返回 ucid
        A->>A: 注入 X-Nrs-User-Id 请求头
        A->>L: 转发请求
    end

    alt SSE 流式请求
        L->>L: 记录请求信息
        L->>R: 转发请求
        R-->>L: 流式响应 直接透传
        L-->>C: 流式响应
    else 普通请求
        L->>L: 记录请求信息 + 缓存请求体
        L->>R: 转发请求
        R-->>L: 返回响应
        L->>L: 记录响应信息 + 耗时
        L-->>C: 返回响应
    end

    Note over C: 响应头包含 X-Nrs-Agent-Trace-Id
```

## 设计模式与关键决策

### 两种 ASGI 实现模式并存

模块中存在两种中间件实现方式，各有其适用场景：

| 实现方式 | 使用者 | 优点 | 缺点 |
|---------|--------|------|------|
| `BaseHTTPMiddleware` | AuthMiddleware | 开发简单，可直接访问 `Request`/`Response` 对象 | 会缓存整个响应体，与 SSE 不兼容 |
| 纯 ASGI 协议 | TraceIdMiddleware、RequestLoggingMiddleware | 完全控制请求/响应生命周期，SSE 友好 | 实现复杂，需手动处理 scope/receive/send |

**决策原因**：AuthMiddleware 仅操作请求头（不涉及响应体缓存），使用 `BaseHTTPMiddleware` 不会导致 SSE 问题；而日志和 TraceId 需要处理响应，必须使用纯 ASGI 以避免阻塞流式传输。

### 认证身份传递机制

```mermaid
graph TD
    subgraph 认证流程
        A[Token 验证] --> B[获取 ucid]
        B --> C[修改 request._headers]
        C --> D[同步 request.scope.headers]
    end

    subgraph 下游消费
        D --> E[API Handler 读取 X-Nrs-User-Id]
        E --> F[业务逻辑使用 ucid]
    end
```

AuthMiddleware 通过修改 Starlette 的私有属性 `_headers` 实现请求头注入。这是一种必要的 hack——Starlette 的 `Headers` 对象设计为不可变，标准中间件 API 无法直接修改传入请求的头部。修改 `_headers` 后还需同步更新 `scope["headers"]` 的字节编码格式，确保 ASGI 应用层能正确读取。

### 环境感知的安全策略

AuthMiddleware 通过 `ENVTYPE` 环境变量实现多环境安全策略差异化：
- **生产环境**：严格 Token 验证，无降级路径
- **开发/测试环境**：支持通过 Header 直接传入用户 ID，简化调试流程

该策略的实现位于中间件的 Token 提取阶段，在 Token 缺失时根据环境类型选择不同的降级逻辑。

## 与系统其他模块的关系

```mermaid
graph TD
    subgraph 基础设施层
        ConfigLoader
        LogConfig
        HttpClient
        RpcClient
    end

    subgraph 中间件层
        AuthMiddleware
        TraceIdMiddleware
        RequestLoggingMiddleware
    end

    subgraph API 层
        ChatAPI[Chat API]
        ConversationAPI[Conversation API]
        StoryAPI[Story API]
    end

    subgraph Schema 层
        ApiSchema
    end

    AuthMiddleware --> RpcClient
    AuthMiddleware --> ConfigLoader
    TraceIdMiddleware --> LogConfig
    RpcClient --> HttpClient

    ChatAPI --> ApiSchema
    ConversationAPI --> ApiSchema
    StoryAPI --> ApiSchema

    AuthMiddleware -.->|注入 ucid| ChatAPI
    AuthMiddleware -.->|注入 ucid| ConversationAPI
    AuthMiddleware -.->|注入 ucid| StoryAPI
```

中间件作为请求处理管线的前置环节，不直接参与业务逻辑，但通过以下方式影响下游：
- **AuthMiddleware**：通过 `X-Nrs-User-Id` 请求头向 [ApiSchema](ApiSchema.md) 层和业务路由传递用户身份
- **TraceIdMiddleware**：通过日志上下文变量关联同一请求的所有日志记录
- **RequestLoggingMiddleware**：提供请求级的审计日志，辅助问题排查

## 配置项

| 配置路径 | 所属模块 | 说明 |
|---------|---------|------|
| `config.auth.skip_paths` | ConfigLoader | 免认证路径列表（如健康检查、文档端点） |
| `config.rpc.session.base_url` | ConfigLoader | Session 服务地址，用于 Token 验证 |
| `config.rpc.session.source` | ConfigLoader | Token 验证请求来源标识 |
| `config.rpc.session.signature` | ConfigLoader | Token 验证请求签名 |
| `ENVTYPE` 环境变量 | 系统 | 当前环境类型（test/preview/prod），影响认证降级策略 |
