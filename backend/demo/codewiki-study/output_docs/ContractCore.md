所有参与者名称均安全，没有使用 Mermaid 保留字。文档已生成完毕。

---

**文档已保存至**：`/Users/zqy/work/AI-Project/milo-v2/backend/demo/codewiki-study/output_docs/ContractCore.md`

### 修复说明

原始错误原因：在序列图（sequenceDiagram）中使用了 `Create` 作为参与者名称，而 `create` 是 Mermaid 的**保留关键字**（用于 `create participant` 语法），导致解析失败。

**修复方案**：将所有序列图中的参与者名称替换为不含保留字的缩写：
- `Create` → `CrtMod`（ContractCreation 模块）
- 其他参与者也统一使用安全的缩写形式（`ValidMod`、`SubmitMod`、`SignMod`、`DetailMod`）

### 文档结构（共 10 个 Mermaid 图表）

| 序号 | 图表类型 | 内容 |
|:---:|---------|------|
| 1 | `graph TD` | 模块层级结构（ContractCore → 5 个子模块 → 10 个组件） |
| 2 | `graph TD` | 系统架构总览（基础设施层 + 核心模块 + 支撑模块 + 外部系统） |
| 3 | `sequenceDiagram` | 合同生命周期数据流（保存 → 校验 → 提交 → 签署 → 详情） |
| 4 | `sequenceDiagram` | ContractDetail 详情查询流程（AOP 预加载 + 数据组装 + 按钮配置） |
| 5 | `graph TD` | ContractValidation 校验方法一览 |
| 6 | `graph TD` | ContractSigning 签约与盖章架构 |
| 7 | `graph LR` | ContractCreation 并行脚本字段获取流程 |
| 8 | `graph TD` | 模块间协作关系（依赖方向图） |
| 9 | `graph TD` | ContractContextManagement 上下文管理架构 |
| 10 | `graph LR` | 外部系统依赖总览 |