# escrow_scripting 模块文档

## 概述

`escrow_scripting` 模块是合同管理系统中的核心业务模块，专注于资金存管合同（Fund Escrow Contract）的业务逻辑处理。该模块负责处理与资金存管合同相关的合同生成、脚本动态字段构建等业务场景，为前端提供标准化的合同数据处理和脚本生成能力。

## 核心功能

### 1. 资金存管合同生成
- **ContractEscrowService**：处理资金存管合同的生成逻辑，支持系统自动生成和用户触发两种模式
- 实现幂等性控制，避免重复生成合同
- 处理合同状态流转逻辑（草稿、待签署、待盖章等状态）

### 2. 合同脚本动态字段构建
- **ContractScriptBuildService**：提供各类合同脚本动态字段的数据获取服务
- 包括工期、保修期、收款计划等关键业务字段的计算和格式化

### 3. 批量动态字段获取
- **ContractScriptCreateService**：提供高效的并行字段获取能力
- 通过反射机制动态调用字段获取方法，提升系统扩展性

## 架构与组件关系

### 模块内部架构

```mermaid
classDiagram
    class ContractEscrowService {
        -ContractSubmitService contractSubmitService
        -EscrowRpc escrowRpc
        -ContractService contractService
        -CipherService cipherService
        -ContractBusinessService contractBusinessService
        +generateEscrowContract() ContractSubmitBaseResDTO
        -buildEscrowContractSubmitReq() ContractReqDTO
    }
    
    class ContractScriptBuildService {
        -ContractFieldService contractFieldService
        -ContractService contractService
        -ContractPdfBuildService contractPdfBuildService
        -CommonContractService commonContractService
        -ContractUnifyService contractUnifyService
        +obtainPlanStartTime() Map
        +obtainPlanDay() Map
        +obtainWaterElectricGuaranteeYear() Map
        +obtainWaterProofGuaranteeYear() Map
        +obtainOtherGuaranteeYear() Map
        +obtainCollectionPlanStr() Map
    }
    
    class ContractScriptCreateService {
        -ContractScriptBuildService contractScriptBuildService
        -Executor scriptDynamicFieldExecutor
        +getScriptDynamicFieldBs() Map
    }
    
    ContractEscrowService --> ContractScriptBuildService : 使用
    ContractScriptCreateService --> ContractScriptBuildService : 反射调用
```

### 与系统其他模块的交互

```mermaid
graph TD
    A[escrow_scripting 模块] --> B[contract_core_services 模块]
    A --> C[personal_binding 模块]
    A --> D[utility_and_check 模块]
    
    B --> B1[ContractButtonConfigService]
    B --> B2[ContractDetailService]
    B --> B3[ContractFieldCheckService]
    
    A -->|生成合同| E[ContractSubmitService<br/>contract_core_services]
    A -->|查询账户| F[EscrowRpc<br/>RPC服务]
    A -->|解密数据| G[CipherService<br/>基础服务]
    
    subgraph "contract_core_services"
        H[ContractDetailService]
        I[ContractButtonConfigService]
        J[ContractFieldCheckService]
    end
    
    A -->|获取配置| H
    A -->|字段验证| J
    
    subgraph "utility_and_check"
        K[WorkerTypeCheckService]
    end
```

## 数据流与处理流程

### 资金存管合同生成流程

```mermaid
flowchart TD
    A[开始生成资金存管合同] --> B{检查系统/用户触发?}
    B -->|系统生成| C[设置系统操作上下文]
    B -->|用户触发| D[获取用户上下文]
    C --> E[查询现有合同状态]
    D --> E
    
    E --> F{合同是否存在且非草稿?}
    F -->|是| G[根据状态返回对应响应]
    F -->|否| H[查询存管账户信息]
    
    H --> I[组装合同参数]
    I --> J[调用ContractSubmitService生成合同]
    J --> K[返回合同编号]
    
    G -->|待签署| L[返回待签署响应]
    G -->|已签署| M[抛出已签署异常]
    G -->|待盖章| N[抛出待盖章异常]
    G -->|其他状态| O[抛出状态异常]
    
    P[查询存管账户] --> Q[检查账户信息完整性]
    Q -->|信息不全| R[抛出账户信息不全异常]
    Q -->|信息完整| S[解密敏感数据]
    S --> T[返回解密后数据]
```

### 脚本动态字段获取流程

```mermaid
flowchart TD
    A[开始获取脚本动态字段] --> B[参数校验]
    B -->|参数无效| C[返回空结果并记录日志]
    B -->|参数有效| D[初始化线程安全结果Map]
    
    D --> E[遍历方法名集合]
    E --> F{方法名是否为空?}
    F -->|是| G[跳过并记录警告]
    F -->|否| H[提交并行任务到线程池]
    
    H --> I[通过反射调用对应方法]
    I --> J{调用是否成功?}
    J -->|成功| K[合并结果到Map]
    J -->|失败| L[记录错误日志]
    
    K --> M[等待所有任务完成]
    M --> N[返回合并后的结果]
    
    G --> E
    L --> E
```

## 关键服务说明

### 1. ContractEscrowService（资金存管合同服务）

**职责**：处理资金存管合同的完整生命周期管理

**核心方法**：
- `generateEscrowContract()`：生成资金存管合同，支持系统自动生成和用户触发
- `buildEscrowContractSubmitReq()`：组装合同生成所需的业务参数

**业务规则**：
1. **幂等性控制**：同一项目订单的合同只能生成一次
2. **状态流转管理**：根据合同当前状态返回不同的处理结果
3. **数据完整性校验**：确保存管账户信息完整且解密成功

### 2. ContractScriptBuildService（合同脚本构建服务）

**职责**：提供合同脚本所需的各类动态字段数据

**提供的字段获取方法**：
| 方法名 | 功能 | 数据来源 |
|--------|------|----------|
| `obtainPlanStartTime()` | 获取计划开工日期 | ContractField |
| `obtainPlanDay()` | 获取工期 | ContractField |
| `obtainWaterElectricGuaranteeYear()` | 获取水电保修期 | ContractBusinessConfig |
| `obtainWaterProofGuaranteeYear()` | 获取防水保修期 | ContractBusinessConfig |
| `obtainOtherGuaranteeYear()` | 获取其他保修期 | ContractBusinessConfig |
| `obtainCollectionPlanStr()` | 获取收款计划 | CommonContractService |

### 3. ContractScriptCreateService（脚本创建服务）

**职责**：提供高效的批量字段获取能力

**核心特性**：
- **并行处理**：使用自定义线程池并行调用多个字段获取方法
- **反射机制**：通过反射动态调用方法，支持灵活的字段扩展
- **错误隔离**：单个字段获取失败不影响其他字段的获取

## 依赖关系分析

### 直接依赖模块
1. **contract_core_services**：依赖合同核心服务进行合同操作
2. **personal_binding**：依赖个人绑定服务处理用户签名相关逻辑
3. **utility_and_check**：依赖工具检查服务进行业务规则验证

### 核心依赖组件
| 组件 | 所属模块 | 用途 |
|------|----------|------|
| ContractSubmitService | contract_core_services | 合同提交和生成 |
| ContractService | DAO层 | 合同数据访问 |
| EscrowRpc | RPC层 | 存管账户信息查询 |
| CipherService | 基础服务层 | 敏感数据解密 |
| ContractBusinessService | contract_core_services | 合同业务配置 |

## 配置与扩展点

### 线程池配置
```java
@Resource(name = "scriptDynamicFieldExecutor")
private Executor scriptDynamicFieldExecutor;
```
- 可配置线程池大小、队列类型等参数以优化并行处理性能

### 业务配置扩展
- 保修期等业务参数通过 `ContractBusinessConfig` 配置，支持按业务类型和渠道进行差异化配置
- 字段获取方法可通过反射机制动态扩展，无需修改核心代码

## 最佳实践与注意事项

### 1. 合同生成场景
- 系统自动生成时需确保操作上下文正确设置
- 处理并发生成请求时注意幂等性控制
- 及时处理异常状态的合同数据

### 2. 脚本字段获取场景
- 合理设置线程池参数，避免资源耗尽
- 对反射调用的方法名进行白名单校验
- 监控并行任务执行性能，及时优化

### 3. 错误处理
- 区分业务异常和系统异常，使用适当的日志级别
- 关键操作需要记录完整的业务上下文
- 敏感信息处理要符合安全规范

## 相关文档

- [contract_core_services 模块文档](contract_core_services.md) - 合同核心服务
- [personal_binding 模块文档](personal_binding.md) - 个人绑定与签名服务
- [utility_and_check 模块文档](utility_and_check.md) - 工具类与检查服务
- [terminal_pdf_and_material 模块文档](terminal_pdf_and_material.md) - PDF生成与物料处理

## 版本历史

| 版本 | 日期 | 变更说明 |
|------|------|----------|
| v1.0 | 初始版本 | 基础功能实现，包括合同生成和脚本字段获取 |
| v1.1 | 性能优化 | 引入并行处理机制，优化字段获取性能 |
| v1.2 | 架构优化 | 完善错误处理机制，增强系统稳定性 |