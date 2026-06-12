# Milo-V2

基于 AgentScope 的 AI Agent 对话平台，前后端分离架构。

## ⚠️ 强制要求：如果用户指定 UI 验证标准，则必须使用 `playwright-cli` 进行浏览器端到端测试

---

## 启动方式

### 前置条件

确保已安装：
- Docker（用于 Redis）
- Python 3.11+
- Node.js 18+

### 启动步骤

```bash
# 1. 启动 Redis
docker-compose up -d

# 2. 启动后端 (端口 8001)
cd backend
source venv/bin/activate  # 激活虚拟环境（必须）
python main.py

# 3. 启动前端 (端口 5175)
cd frontend && npm run dev
```

### 访问地址

- 前端界面: http://localhost:5175
- 后端 API: http://localhost:8001

### 关于 `source venv/bin/activate`

激活 Python 虚拟环境，确保：
- 使用项目专属的 Python 解释器（venv/bin/python3）
- 只能访问 venv 中安装的包（如 agentscope）
- 隔离系统 Python 环境，避免依赖冲突

验证是否激活成功：
```bash
which python3
# 应显示: /Users/zqy/work/AI-Project/milo-v2/backend/venv/bin/python3
```

退出虚拟环境：`deactivate`

### 首次配置

```bash
# 创建后端虚拟环境并安装依赖
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### PyCharm 配置

如果使用 PyCharm，需要配置 Python 解释器：

1. 打开 PyCharm → `Preferences` → `Project: milo-v2` → `Python Interpreter`
2. 点击右上角齿轮图标 → `Add Interpreter` → `Existing`
3. 输入路径：`/Users/zqy/work/AI-Project/milo-v2/backend/venv/bin/python3`
4. 点击 `OK`

> **注意**：不要使用系统 Python（如 `/usr/local/bin/python3`），否则 IDE 跳转会指向本地源码而非 venv 中的依赖包。

## 技术栈

- **后端**: Python 3.11+ / FastAPI / AgentScope / Redis
- **前端**: React 19 / TypeScript / Vite / Tailwind CSS 4 / shadcn / react-router-dom
- **前端 API 代理**: Vite dev server 将 `/api`, `/chat`, `/agent` 等路径代理到 `localhost:8001`

## 开发规范

### 1. 代码复用优先

- **禁止复制粘贴代码**。当两处逻辑相似度超过 70% 时，必须抽取为公共函数/Hook/组件。
- 前端：跨页面复用的逻辑抽到 `hooks/`，跨组件复用的 UI 片段抽到 `components/` 对应域。
- 后端：跨路由复用的逻辑抽到 service 层或工具函数。
- **结构性重复也算重复**：如果多个组件有相同的 props 传递模式、相同的条件渲染结构、相同的错误处理骨架，应抽取为高阶组件、Render Props 或自定义 Hook。

### 2. 分层架构与抽象隔离

代码组织按职责分层，每一层对上层暴露**抽象接口**，隐藏**实现细节**。依赖方向严格单向，上层不得直接访问下层的内部实现。

```
pages/          # 页面层：路由入口，组合组件，编排数据流
  ↓             #   只调用组件 + Hooks，不知道数据怎么来的
components/     # 组件层：UI 渲染，纯展示 + 回调
  ↓             #   只通过 Props 接收数据，不知道状态怎么管理的
hooks/          # 状态层：业务状态编排，组合多个 API 调用
  ↓             #   只调用 api/ 的导出函数，不知道 HTTP 细节
api/            # 接口层：HTTP 请求封装，类型定义
  ↓             #   只依赖 types.ts 的类型契约，不知道业务逻辑
utils/ lib/     # 基础层：纯函数，工具方法，零业务依赖
```

#### 层间抽象规则

**页面层（pages/）**
- 只做组件组合和路由编排，**禁止**包含业务计算、数据转换逻辑
- 通过 Hooks 获取数据，通过组件 Props 传递，**不得**直接调用 API
- 页面不知道数据来自 REST、WebSocket 还是本地缓存——这是 Hooks 层的事

**组件层（components/）**
- 纯展示层：接收 Props，渲染 UI，通过回调上报事件
- **禁止**在组件内调用 API、管理服务端状态、直接操作 localStorage
- 组件不关心数据的来源和存储方式，只关心"给我什么数据，我怎么展示"
- 业务组件与基础 UI 组件（`ui/`）解耦：业务组件组合基础组件，不修改基础组件内部

**状态层（hooks/）**
- 封装业务状态管理和副作用，是组件与 API 之间的**唯一桥梁**
- 对组件暴露简洁的接口：返回 `{ data, loading, error, actions }` 模式
- **隐藏**数据获取策略（轮询、WebSocket、缓存失效等），组件不感知
- 多个相关 Hook 可组合，但单个 Hook 内部逻辑不超过一个业务领域

**接口层（api/）**
- 只负责 HTTP 请求的发送和响应的解析，**禁止**包含状态管理或 UI 逻辑
- 对上层暴露语义化函数（`fetchSessions`, `sendMessage`），**隐藏** URL 拼接、请求头处理、序列化细节
- 请求/响应类型定义在 `types.ts`，这是层间的**类型契约**——上层只依赖类型，不依赖实现
- 如需替换 HTTP 客户端（fetch → axios），只需改 api/ 内部，上层无感

**基础层（utils/ lib/）**
- 纯函数，零副作用，零业务依赖
- 可独立测试，可在任何层使用
- 不引用 `hooks/`、`api/`、`components/` 中的任何内容

#### 依赖反转原则

当上层需要抽象而非具体实现时，使用依赖反转：
- 组件通过 **Props 接口**（而非具体 Hook）接收数据——方便测试时注入 mock 数据
- Hook 通过 **api 层的导出函数**（而非直接 import axios）发请求——方便测试时 mock API
- 页面通过 **组件组合**（而非硬编码具体组件）构建 UI——方便替换实现

#### 扩展性要求

- **新增数据源**（如从 REST 切换到 WebSocket）：只改 `hooks/` 内部实现，`components/` 和 `pages/` 零改动
- **新增 UI 主题/适配**：只改 `components/ui/` 或添加新组件，`hooks/` 和 `api/` 零改动
- **新增 API 端点**：在 `api/` 添加函数 + `types.ts` 添加类型，`hooks/` 按需调用，`components/` 零改动
- **替换第三方库**（如状态管理、HTTP 客户端）：影响范围控制在单层内，不波及其他层

#### 层间违规检查（Code Review 必查项）

以下行为属于**层级违规**，PR 中不得出现：

| 违规行为 | 违反规则 | 正确做法 |
|---------|---------|---------|
| 组件内 `import { api }` | 组件直接调用 API | 通过 Hook 获取数据 |
| 组件内 `useState` + `fetch` | 组件管理服务端状态 | 抽到自定义 Hook |
| 页面内写 `if/else` 数据转换 | 页面包含业务逻辑 | 逻辑下沉到 Hook |
| Hook 内 return JSX | Hook 包含 UI 逻辑 | Hook 只返回数据和操作 |
| `utils/` 引用 `hooks/` 或 `api/` | 基础层依赖上层 | 工具函数应无业务依赖 |
| `api/` 内 `useState` / `useEffect` | 接口层管理状态 | api/ 只导出纯异步函数 |
| 直接在组件中操作 localStorage | 组件直接访问存储 | 封装到 Hook 或 utils |

### 3. 设计规范（避免代码坏味道）

#### 函数/组件设计
- **单一职责**：一个函数只做一件事。超过 50 行的函数必须拆分。
- **参数对象化**：超过 3 个参数时，使用 options 对象。
- **早返回**：使用 guard clause 减少嵌套，嵌套不超过 3 层。

#### 命名规范
- 组件用 **PascalCase**（`ChatContent.tsx`）
- 工具函数/Hook 用 **camelCase**（`useChat.ts`, `formatDate.ts`）
- 常量用 **UPPER_SNAKE_CASE**
- CSS 类名用 Tailwind，不自造 class 名
- 布尔变量用 `is/has/can/should` 前缀

#### 文件规范
- 单个文件不超过 **300 行**，超过则拆分
- 一个文件只导出一个主要产物（组件/Hook/函数）
- 相关的类型定义就近放置（`types.ts` 或文件内 `interface`）

### 4. 测试覆盖

- **新功能必须有测试**，不允许提交无测试覆盖的功能代码。
- 测试文件与源文件同目录，命名为 `*.test.ts(x)` 或 `*.spec.ts(x)`。
- 测试金字塔：单元测试为主 > 集成测试为辅 > E2E 测试可选。
- 测试应覆盖：正常路径、边界条件、错误处理。
- Mock 外部依赖（API 调用、浏览器 API），不 mock 被测模块内部逻辑。

#### 分层测试策略

分层架构天然支持**逐层独立测试**，利用抽象隔离降低测试复杂度：

| 测试层级 | 测试内容 | Mock 策略 |
|---------|---------|----------|
| **utils/lib** | 纯函数输入输出 | 无需 Mock |
| **api/** | 请求构造、响应解析、错误处理 | Mock fetch/axios |
| **hooks/** | 状态流转、副作用触发、缓存行为 | Mock api/ 层的导出函数 |
| **components/** | 渲染输出、交互回调、条件展示 | Mock Hook 返回值 + Props |
| **pages/** | 页面组合、路由跳转、数据流串联 | Mock Hooks + 子组件 |

关键原则：**每一层的测试只 Mock 它的直接下层**，不跨层 Mock。这样当下层实现变更时，只需更新该层的测试，上层测试不受影响。

```bash
# 前端测试
cd frontend && npm test

# 后端测试
cd backend && python -m pytest

# 前端 lint
cd frontend && npm run lint
```

**严禁跳过测试直接提交。** 如果测试失败，必须修复后再提交。

