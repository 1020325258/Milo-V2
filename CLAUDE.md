# Milo-V2

基于 AgentScope 的 AI Agent 对话平台，前后端分离架构。

## 项目结构

```
milo-v2/
├── backend/                # Python 后端 (FastAPI + AgentScope)
│   ├── main.py             # 应用入口
│   ├── requirements.txt    # Python 依赖
│   └── workspaces/         # Agent 工作空间（运行时生成，已 gitignore）
├── frontend/               # React 前端 (Vite + TypeScript + Tailwind)
│   ├── src/
│   │   ├── api/            # API 调用层（按资源拆分）
│   │   ├── components/     # UI 组件（按功能域分组）
│   │   │   ├── badge/      # 徽章组件
│   │   │   ├── chat/       # 聊天相关组件
│   │   │   │   └── tool-renderers/  # 工具调用渲染器
│   │   │   ├── dialog/     # 弹窗组件
│   │   │   ├── drawer/     # 抽屉组件
│   │   │   ├── form/       # 表单组件
│   │   │   ├── layout/     # 布局组件
│   │   │   ├── select/     # 选择器组件
│   │   │   ├── tour/       # 新手引导
│   │   │   └── ui/         # 基础 UI 原子组件（shadcn 风格）
│   │   ├── hooks/          # 自定义 Hooks（按资源拆分）
│   │   ├── i18n/           # 国际化
│   │   ├── lib/            # 工具库
│   │   ├── pages/          # 页面组件（按路由拆分）
│   │   └── utils/          # 通用工具函数
│   └── package.json
└── docker-compose.yml      # Redis 等基础设施
```

## 启动方式

```bash
# 启动 Redis
docker-compose up -d

# 启动后端 (端口 8001)
cd backend && python main.py

# 启动前端 (端口 5175)
cd frontend && npm run dev
```

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

### 2. 分层架构（DDD 思想）

代码组织按职责分层，依赖方向单向：**页面 → 组件 → Hooks/API → 工具函数**。

```
pages/          # 页面层：路由入口，组合组件，编排数据流
  ↓
components/     # 组件层：UI 渲染，接收 props，触发回调
  ↓
hooks/          # 状态层：业务状态管理，调用 API，缓存逻辑
  ↓
api/            # 接口层：HTTP 请求封装，类型定义
  ↓
utils/ lib/     # 基础层：纯函数，工具方法，无业务依赖
```

- **页面组件**只做组合，不包含业务计算逻辑
- **Hooks** 封装状态和副作用，不包含 JSX
- **API 层**只负责请求/响应，不管理状态
- **组件**通过 props 接收数据，通过回调上报事件，不直接调用 API

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

#### TypeScript 规范
- 禁止 `any`，必须使用具体类型或 `unknown`
- API 响应必须定义完整的 TypeScript 类型（在 `api/types.ts`）
- 组件 Props 必须显式定义 interface

#### React 规范
- 优先使用函数组件 + Hooks
- 避免在渲染函数中创建新对象/数组（会导致不必要的 re-render）
- `useEffect` 依赖数组必须完整，不遗漏依赖
- 自定义 Hook 以 `use` 开头，只封装可复用的状态逻辑

### 4. 测试覆盖

- **新功能必须有测试**，不允许提交无测试覆盖的功能代码。
- 测试文件与源文件同目录，命名为 `*.test.ts(x)` 或 `*.spec.ts(x)`。
- 测试金字塔：单元测试为主 > 集成测试为辅 > E2E 测试可选。
- 测试应覆盖：正常路径、边界条件、错误处理。
- Mock 外部依赖（API 调用、浏览器 API），不 mock 被测模块内部逻辑。

### 5. 开发流程

每次功能开发必须遵循以下流程：

1. **编写/更新测试** — 先写测试或同步写测试（TDD 或 TAD）
2. **实现功能代码** — 满足测试用例
3. **运行相关测试** — 确保所有相关测试通过
4. **运行 lint** — `cd frontend && npm run lint`
5. **确认无误后提交**

```bash
# 前端测试
cd frontend && npm test

# 后端测试
cd backend && python -m pytest

# 前端 lint
cd frontend && npm run lint
```

**严禁跳过测试直接提交。** 如果测试失败，必须修复后再提交。

## 常见任务

### 添加新页面
1. 在 `pages/` 下创建页面目录和组件
2. 在 `App.tsx` 中添加路由
3. 在 `i18n/locales/` 下添加对应翻译

### 添加新 API
1. 在 `api/types.ts` 定义请求/响应类型
2. 在 `api/` 对应资源文件中添加请求函数
3. 在 `hooks/` 中封装为 Hook（如需要）

### 添加新组件
1. 确定组件归属的功能域（chat/dialog/form 等）
2. 基础 UI 组件放 `components/ui/`，业务组件放对应域目录
3. 组件 Props 定义 interface，放在组件文件顶部或同目录 `types.ts`
