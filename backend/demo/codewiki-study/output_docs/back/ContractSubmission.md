文档已生成并保存到 `/Users/zqy/work/AI-Project/milo-v2/backend/demo/codewiki-study/output_docs/ContractSubmission.md`。

文档涵盖以下内容：

- **模块概述** — 两个核心服务的职责对照表
- **系统定位** — 展示 ContractSubmission 在合同生命周期（校验→提交→签署）中的位置
- **架构图** — 包含外部依赖和基础设施依赖的完整依赖关系
- **核心组件详解** — 两个 Service 的所有公开方法、个性化报价拆分流程图、存管合同幂等状态机、参数组装流程
- **数据流** — 草稿保存和存管合同生成的完整时序图
- **依赖关系** — 内部（兄弟模块）、跨模块、基础服务三个层次
- **关键设计模式** — AOP 上下文预加载、自调用事务代理（`AopContext.currentProxy()`）、幂等性设计、系统自动触发、按主体拆分、合并发起机制
- **兄弟模块关系** — 与其他 ContractCore 子模块的交互图
- **线程安全与事务边界** — ThreadLocal 隔离和 `@Transactional` 边界分析