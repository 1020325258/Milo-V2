# RpcClient

## 模块概述

RpcClient 模块是 Agent 系统的**远程服务通信层**，负责封装对外部 RPC 服务的 HTTP 调用。该模块包含两个独立的客户端实现，分别对接不同的后端服务：

- **SessionRpcClient**：与 Session 服务交互，提供用户身份令牌（Token）验证能力。
- **ToolboxRpcClient**：与 Toolbox 服务交互，提供 Prompt 模板的远程获取能力。

两个客户端均继承自 [HttpClient](HttpClient.md) 模块的 `BaseAsyncHttpClient`，复用统一的异步 HTTP 请求基础设施、错误处理和日志记录机制。

## 架构总览

```mermaid
graph TD
    subgraph ApplicationLayer[应用层]
        AuthMiddleware[AuthMiddleware<br/>身份认证中间件]
        AgentBase[BaseAgent<br/>Agent 基类]
    end

    subgraph RpcClientModule[RpcClient 模块]
        SessionRpcClient[SessionRpcClient<br/>会话服务客户端]
        ToolboxRpcClient[ToolboxRpcClient<br/>工具箱服务客户端]
        PromptItemA[PromptItem<br/>Prompt 数据模型]
        PromptItemB[PromptItem<br/>Prompt 数据模型]
    end

    subgraph InfrastructureLayer[基础设施层]
        BaseAsyncHttpClient[BaseAsyncHttpClient<br/>异步 HTTP 客户端基类]
        CacheManager[CacheManager<br/>缓存管理器]
        ConfigLoader[ConfigLoader<br/>配置加载器]
    end

    subgraph ExternalServices[外部服务]
        SessionService[Session 服务<br/>Token 验证]
        ToolboxService[Toolbox 服务<br/>Prompt 管理]
    end

    AuthMiddleware -->|验证 Token| SessionRpcClient
    AgentBase -->|获取 Prompt| ToolboxRpcClient

    SessionRpcClient -->|继承| BaseAsyncHttpClient
    ToolboxRpcClient -->|继承| BaseAsyncHttpClient
    SessionRpcClient -->|使用| PromptItemA
    ToolboxRpcClient -->|使用| PromptItemB

    ToolboxRpcClient -->|缓存 Prompt 结果| CacheManager
    SessionRpcClient -->|读取服务地址和凭证| ConfigLoader
    ToolboxRpcClient -->|读取服务地址和超时| ConfigLoader

    BaseAsyncHttpClient -->|httpx| SessionService
    BaseAsyncHttpClient -->|httpx| ToolboxService
```

## 核心组件详解

### PromptItem

两个客户端文件中各定义了一个同名的 `PromptItem` 数据模型，均使用 Pydantic `BaseModel`，结构完全一致：

| 字段 | 类型 | 说明 |
|------|------|------|
| `role` | `str` | 消息角色（如 `system`、`user`、`assistant`） |
| `content` | `str` | Prompt 内容文本 |

> **注意**：两个文件中的 `PromptItem` 是独立定义的重复类，功能等价。消费方按需从各自模块导入即可。

### SessionRpcClient

`SessionRpcClient` 是与 **Session 服务**通信的异步 HTTP 客户端，核心职责为**用户 Token 验证**。

#### 类继承关系

```mermaid
classDiagram
    class BaseAsyncHttpClient {
        +base_url: str
        +default_timeout: float
        +get(endpoint, headers, params, timeout) dict
        +post(endpoint, json_data, data, headers, timeout) dict
        +put(endpoint, json_data, headers, timeout) dict
        +delete(endpoint, headers, params, timeout) dict
        +patch(endpoint, json_data, headers, timeout) dict
    }

    class SessionRpcClient {
        +TOKEN_VERIFY_ENDPOINT: str
        +verify_token(token: str) dict
    }

    class ToolboxRpcClient {
        +PROMPT_MANAGE_ENDPOINT: str
        +get_prompt(prompt_key, version, space_name) PromptItem
    }

    BaseAsyncHttpClient <|-- SessionRpcClient
    BaseAsyncHttpClient <|-- ToolboxRpcClient
```

#### 初始化

```python
def __init__(self):
    base_url = config.rpc.session.base_url
    super().__init__(base_url=base_url)
```

- 从 [ConfigLoader](ConfigLoader.md) 加载的全局配置中读取 `config.rpc.session.base_url` 作为服务端点
- 使用基类默认超时（30 秒）

#### 核心方法：`verify_token(token: str) -> dict | None`

验证用户身份令牌的有效性，返回用户标识（`ucid`）或 `None`。

**请求构造流程：**

1. 从配置中读取 `source` 和 `signature` 作为认证凭证
2. 构建表单数据：`{ source, signature, token }`
3. 以 `application/x-www-form-urlencoded` 格式发送 POST 请求至 `/token/verify`

**响应处理：**

- `error_code == 0`：验证成功，通过 `dot_get(data, "data.token_info.ucid")` 提取用户唯一标识
- `error_code != 0`：验证失败，记录错误日志，返回 `None`

**数据流图：**

```mermaid
graph LR
    A[调用方传入 token] --> B[读取配置中的 source 和 signature]
    B --> C[构建 form-data]
    C --> D[POST /token/verify]
    D --> E{error_code == 0?}
    E -->|是| F[提取并返回 ucid]
    E -->|否| G[记录错误日志]
    G --> H[返回 None]
```

### ToolboxRpcClient

`ToolboxRpcClient` 是与 **Toolbox 服务**通信的异步 HTTP 客户端，核心职责为**远程获取 Prompt 模板数据**。

#### 初始化

```python
def __init__(self):
    base_url = config.rpc.toolbox.base_url
    timeout = config.rpc.toolbox.timeout
    super().__init__(base_url=base_url, default_timeout=timeout)
```

- 从配置中读取 `config.rpc.toolbox.base_url`（服务地址）和 `config.rpc.toolbox.timeout`（自定义超时）
- 将自定义超时传递给基类，覆盖默认的 30 秒超时

#### 核心方法：`get_prompt(prompt_key, version?, space_name?) -> PromptItem | None`

获取远程 Prompt 管理平台中的 Prompt 模板数据。

**参数说明：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `prompt_key` | `str` | 是 | Prompt 模板的唯一标识键 |
| `version` | `str \| None` | 否 | 指定版本号，不传则获取最新版本 |
| `space_name` | `str \| None` | 否 | 命名空间，不传则使用配置默认值 |

**缓存策略：**

方法使用 `@cache` 装饰器，自动缓存请求结果：

```python
@cache(ttl=900, prefix="toolbox:prompt")
async def get_prompt(self, prompt_key, version, space_name):
```

- **TTL**：900 秒（15 分钟），避免频繁调用远程服务
- **缓存前缀**：`toolbox:prompt`
- **缓存键构成**：前缀 + 方法参数（`prompt_key` + `version` + `space_name`）
- **缓存后端**：由 [CacheInfrastructure](CacheInfrastructure.md) 模块统一管理，支持内存缓存和 Redis 两种策略

**请求与响应处理流程：**

```mermaid
graph TD
    A[调用 get_prompt] --> B{prompt_key 为空?}
    B -->|是| C[抛出 ValueError]
    B -->|否| D{base_url 为空?}
    D -->|是| E[抛出 ValueError]
    D -->|否| F[检查缓存是否命中]
    F -->|命中| G[返回缓存的 PromptItem]
    F -->|未命中| H[构建请求参数]
    H --> I[GET /prompt/manage/get]
    I --> J{code == 2000?}
    J -->|否| K[记录业务错误日志]
    K --> L[返回 None]
    J -->|是| M{data 为空?}
    M -->|是| N[记录警告日志]
    N --> O[返回 None]
    M -->|否| P[提取 data 第一个元素]
    P --> Q[封装为 PromptItem]
    Q --> R[写入缓存并返回]
```

**错误处理策略：**

| 场景 | 处理方式 |
|------|----------|
| `prompt_key` 为空 | 抛出 `ValueError`（快速失败） |
| `base_url` 未配置 | 抛出 `ValueError`（快速失败） |
| 业务响应码非 2000 | 记录错误日志，返回 `None` |
| 响应 `data` 为空数组 | 记录警告日志，返回 `None` |
| 网络/解析异常 | 捕获 `Exception`，记录错误日志，返回 `None` |

## 依赖关系

```mermaid
graph TD
    subgraph RpcClient[RpcClient 模块]
        SRC[SessionRpcClient]
        TRC[ToolboxRpcClient]
    end

    subgraph Dependencies[依赖模块]
        HTTP[HttpClient<br/>BaseAsyncHttpClient]
        CFG[ConfigLoader<br/>全局配置]
        CACHE[CacheInfrastructure<br/>CacheManager]
        UTILS[TimeUtils<br/>dot_get 工具函数]
    end

    subgraph External[外部库]
        PYDANTIC[Pydantic<br/>数据验证]
        HTTPX[httpx<br/>HTTP 客户端]
    end

    SRC --> HTTP
    SRC --> CFG
    SRC --> UTILS
    TRC --> HTTP
    TRC --> CFG
    TRC --> CACHE
    HTTP --> HTTPX
    SRC -.-> PYDANTIC
    TRC -.-> PYDANTIC
```

**依赖模块说明：**

| 依赖模块 | 引用关系 | 说明 |
|----------|----------|------|
| [HttpClient](HttpClient.md) | 继承 `BaseAsyncHttpClient` | 复用异步 HTTP 请求能力，包括请求/响应日志、错误处理、连接池管理 |
| [ConfigLoader](ConfigLoader.md) | 读取 `config.rpc.*` | 从 YAML 配置文件加载服务地址、超时时间、认证凭证等 |
| [CacheInfrastructure](CacheInfrastructure.md) | `@cache` 装饰器 | ToolboxRpcClient 的 `get_prompt` 方法利用缓存减少远程调用频次 |
| [TimeUtils](TimeUtils.md) | `dot_get` 函数 | SessionRpcClient 使用嵌套字典安全取值工具提取深层响应字段 |

## 组件交互时序

### Token 验证流程

```mermaid
sequenceDiagram
    participant Caller as 调用方（AuthMiddleware）
    participant SRC as SessionRpcClient
    participant CFG as ConfigLoader
    participant HTTP as BaseAsyncHttpClient
    participant Svc as Session 服务

    Caller->>SRC: verify_token(token)
    SRC->>CFG: 读取 config.rpc.session
    CFG-->>SRC: source, signature, base_url
    SRC->>HTTP: POST /token/verify (form-data)
    HTTP->>Svc: HTTP POST 请求
    Svc-->>HTTP: JSON 响应
    HTTP-->>SRC: 解析后的 dict
    alt error_code == 0
        SRC-->>Caller: 返回 ucid（用户标识）
    else error_code != 0
        SRC->>SRC: 记录错误日志
        SRC-->>Caller: 返回 None
    end
```

### Prompt 获取流程

```mermaid
sequenceDiagram
    participant Caller as 调用方（Agent）
    participant TRC as ToolboxRpcClient
    participant Cache as CacheManager
    participant CFG as ConfigLoader
    participant HTTP as BaseAsyncHttpClient
    participant Svc as Toolbox 服务

    Caller->>TRC: get_prompt(prompt_key, version?, space_name?)
    TRC->>Cache: 查询缓存（toolbox:prompt:...）
    alt 缓存命中
        Cache-->>TRC: 缓存的 PromptItem
        TRC-->>Caller: 返回 PromptItem
    else 缓存未命中
        Cache-->>TRC: None
        TRC->>CFG: 读取 config.rpc.toolbox
        CFG-->>TRC: base_url, timeout
        TRC->>HTTP: GET /prompt/manage/get
        HTTP->>Svc: HTTP GET 请求
        Svc-->>HTTP: JSON 响应
        HTTP-->>TRC: 解析后的 dict
        alt code == 2000 且 data 非空
            TRC->>TRC: 封装为 PromptItem
            TRC->>Cache: 写入缓存（ttl=900s）
            TRC-->>Caller: 返回 PromptItem
        else 业务失败或数据为空
            TRC-->>Caller: 返回 None
        end
    end
```

## 系统集成

RpcClient 模块在系统中位于**基础设施层**与**应用层**之间的桥梁位置，向上为业务逻辑提供语义化的远程调用接口，向下依赖统一的 HTTP 通信和配置管理基础设施。

```mermaid
graph TD
    subgraph AppLayer[应用层]
        Auth[AuthMiddleware<br/>身份认证]
        Agents[Agent 应用<br/>Prompt 驱动]
    end

    subgraph RpcClient[RpcClient 模块]
        SRC[SessionRpcClient]
        TRC[ToolboxRpcClient]
    end

    subgraph Infra[基础设施层]
        HTTP[HttpClient]
        CACHE[CacheInfrastructure]
        CFG[ConfigLoader]
    end

    subgraph External[外部服务]
        S1[Session 服务]
        S2[Toolbox 服务]
    end

    Auth -->|verify_token| SRC
    Agents -->|get_prompt| TRC
    SRC --> HTTP
    TRC --> HTTP
    TRC --> CACHE
    SRC --> CFG
    TRC --> CFG
    HTTP --> S1
    HTTP --> S2
```

## 设计模式与最佳实践

### 1. 模块级单例实例化

两个客户端在模块末尾各创建了一个全局单例实例：

```python
session_client = SessionRpcClient()   # session_client.py
toolbox_client = ToolboxRpcClient()   # toolbox_client.py
```

Python 模块本身就是单例，因此模块级实例天然具备单例语义——整个应用进程中只存在一个客户端实例，共享底层的 HTTP 连接池（由 `AsyncHttpClientManager` 管理），避免连接资源浪费。

### 2. 继承复用

两个客户端均继承 `BaseAsyncHttpClient`，获得：
- 统一的 GET/POST/PUT/DELETE/PATCH 方法
- 自动化的请求/响应日志记录
- 标准化的异常处理和 `raise_for_status`
- 共享 httpx 异步连接池

### 3. 配置驱动

所有可变参数（服务地址、超时时间、认证凭证）均从 YAML 配置文件中读取，通过 [ConfigLoader](ConfigLoader.md) 单例统一管理。客户端代码中不存在硬编码的 URL 或密钥，支持通过环境变量（`ENVTYPE`）切换不同环境配置。

### 4. 缓存加速

`ToolboxRpcClient.get_prompt` 通过 `@cache` 装饰器实现透明缓存，调用方无需感知缓存逻辑。TTL 设为 15 分钟，在 Prompt 模板变更不频繁的场景下，有效减少远程服务调用次数，降低延迟。

### 5. 优雅降级

两个客户端在异常场景下采用"记录日志 + 返回 None"的降级策略，而非抛出异常向上冒泡。这使得调用方可以在 RPC 失败时执行备选逻辑（如使用默认 Prompt），保证系统整体可用性。
