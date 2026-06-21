# ContractFieldValidation 模块文档

## 模块概述

ContractFieldValidation 是合同子系统中的**字段校验模块**，负责在合同提交、保存草稿等关键业务节点对合同数据进行规则校验。该模块采用**反射驱动 + 配置化**的校验架构：校验方法通过配置表动态绑定，运行时由 `ContractUnifyService` 读取字段配置后反射调用对应校验方法，实现校验逻辑与调用方的解耦。

模块包含两个核心服务：
- **ContractFieldCheckService**：合同字段校验主服务，包含品类校验、金额校验、身份信息校验、设计费校验等 9 个校验方法
- **WorkerTypeCheckService**：工种校验服务，通过 RPC 查询人员工种信息，提供通用的工种类型校验能力

---

## 架构总览

```mermaid
graph TD
    subgraph 调用层
        CUS[ContractUnifyService]
        CSUB[ContractSubmitService]
        CSDS[ContractSaveDraftService]
    end

    subgraph ContractFieldValidation 模块
        CFCS[ContractFieldCheckService]
        WTCS[WorkerTypeCheckService]
    end

    subgraph 配置层
        CFC[ContractFieldConfig 配置表]
        CAC[ContractApolloConfig 动态配置]
    end

    subgraph 外部依赖
        CERES[CeresRpc 工种信息查询]
        COMMON[CommonContractService]
        CIPHER[CipherService 加解密]
        CBIZ[ContractBusinessService]
        FUND[FundInfoService 款项信息]
        ADMIN[AdminService 文件服务]
        DFC[DesignFeeCalculator 设计费计算]
        CUNIFY[ContractUnifyService 辅助方法]
        CBBIZ[CommonBusinessService]
    end

    CUS -->|反射调用| CFCS
    CSUB -->|submit流程| CUS
    CSDS -->|saveDraft流程| CUS
    CUS -->|读取配置| CFC
    CFC -->|绑定checkFunction| CFCS

    CFCS --> COMMON
    CFCS --> CIPHER
    CFCS --> CBIZ
    CFCS --> FUND
    CFCS --> ADMIN
    CFCS --> DFC
    CFCS --> CUNIFY
    CFCS --> CBBIZ
    CFCS --> CAC

    WTCS --> CERES
```

---

## 核心组件详解

### ContractFieldCheckService

**职责**：合同字段校验的核心执行器，所有校验方法通过反射机制被动态调用。

> **重要约束**：该类中的校验方法通过反射调用，方法名称不能修改，方法不能删除。新增校验方法时需同步在 `ContractFieldConfig` 配置表中注册对应的 `checkFunction` 名称。

#### 反射调用机制

```mermaid
sequenceDiagram
    participant CUS as ContractUnifyService
    participant CFC as ContractFieldConfig 配置表
    participant CFCS as ContractFieldCheckService
    participant Method as 具体校验方法

    CUS->>CFC: 查询字段配置（按城市/公司/业务类型/合同类型）
    CFC-->>CUS: 返回 List of ContractFieldConfig

    loop 遍历每个配置项
        CUS->>CUS: 过滤有 checkFunction 的配置
        CUS->>CUS: 按 checkFunction 去重
        CUS->>CUS: 评估 conditionCheck 条件

        alt 条件满足
            CUS->>CFCS: checkContractField(contractReq, functionName)
            CFCS->>CFCS: ReflectionUtils.findMethod(this, functionName)
            CFCS->>Method: ReflectionUtils.invokeMethod(method, this, contractReq)
            Method-->>CFCS: true / false
            CFCS-->>CUS: true / false

            alt 校验失败
                CUS->>CUS: 抛出 NrsBusinessException
            end
        end
    end
```

#### 校验方法一览

| 方法名 | 校验内容 | 失败处理 | 依赖服务 |
|--------|---------|---------|---------|
| `checkBrandList` | 品类列表预收金额求和校验、品类编号合法性、预收金额占比校验 | 返回 false 或抛出异常（预收金额不足时） | `ContractApolloConfig`, `ContractContextHandler` |
| `checkBrandTotalAmount` | 品类列表总计金额不小于款项已付金额 | 返回 false | `FundInfoService`, `FundRelateContractMapping` |
| `checkAdvanceAmount` | 首期款金额在预估合同额的 20%~70% 范围内；预估合同额与报价一致性校验 | 抛出 `UtopiaBussinessException` | `ContractUnifyService`, `ContractApolloConfig` |
| `checkAdvanceFileSize` | 首期款报价单文件大小不超过配置上限（默认 10M） | 抛出 `NrsBusinessException` | `AdminService`, `ContractApolloConfig` |
| `checkHouseType` | 正式套餐合同提交时，房屋类型与报价侧一致（仅 V2.5 流程） | 抛出 `NrsBusinessException` | `CommonBusinessService`, `ContractContextHandler` |
| `checkIdCardInfo` | 业主/代理人/公司代理人/法人姓名与身份证号一致性校验 | 抛出 `UtopiaBussinessException` | `CommonContractService`, `CipherService` |
| `checkCompanyInfo` | 企业名称与统一社会信用代码非空及一致性校验 | 抛出 `UtopiaBussinessException` | `ContractBusinessService` |
| `checkDesignAmount` | 设计服务费（优惠后）不大于（优惠前），且大于 0 | 抛出 `UtopiaBussinessException` | `DesignFeeCalculator`, `ContractUnifyService`, `ContractApolloConfig` |

#### 校验方法内部逻辑

**checkBrandList 品类校验流程**：

```mermaid
flowchart TD
    A[开始] --> B{品类列表为空?}
    B -->|是| C[返回 false]
    B -->|否| D[获取公司编码 companyCode]
    D --> E[遍历品类列表]
    E --> F{品类编号在枚举中?}
    F -->|否| G[返回 false]
    F -->|是| H{预收/报价金额非空?}
    H -->|否| G
    H -->|是| I[累加 dueAmount 和 quoteAmount]
    I --> J{预收金额小于报价的配置比例?}
    J -->|是| K[加入 errorBrandSet]
    J -->|否| L{还有下一个品类?}
    K --> L
    L -->|是| E
    L -->|否| M{errorBrandSet 非空?}
    M -->|是| N[抛出异常: 预收金额不足]
    M -->|否| O{dueTotalAmount == 请求的总预收金额?}
    O -->|否| C
    O -->|是| P{quoteTotalAmount == 请求的总报价金额?}
    P -->|否| C
    P -->|是| Q[返回 true]
```

**checkAdvanceAmount 首期款校验流程**：

```mermaid
flowchart TD
    A[开始] --> B[读取预估合同额/首期款金额/业务类型]
    B --> C{是否从报价单获取首期信息?}
    C -->|是| D[从 quotation 模块读取]
    C -->|否| E[从 projectInfo 读取]
    D --> F{预估合同额非空?}
    E --> F
    F -->|否| Q[返回 true 跳过]
    F -->|是| G{预估合同额 > 0?}
    G -->|否| H[抛出异常: 必须大于0]
    G -->|是| I{业务类型校验}
    I -->|整装| J{预估合同额 >= 报价预估合同额?}
    J -->|否| K[抛出异常: 不可小于报价额]
    I -->|翻新全案| L{在配置范围内?}
    L -->|否| M[抛出异常: 超出范围]
    I -->|其他| N[继续]
    J -->|是| N
    L -->|是| N
    N --> O[计算 minAdvanceAmount = 预估合同额 × advanceRate]
    O --> P[计算 maxAdvanceAmount = 预估合同额 × 70%]
    P --> R{minAdvanceAmount <= 首期款 <= maxAdvanceAmount?}
    R -->|否| S[抛出异常: 超出范围]
    R -->|是| Q
```

**checkIdCardInfo 身份校验流程**：

```mermaid
flowchart TD
    A[开始] --> B{签约主体类型?}
    B -->|个人| C{证件类型为身份证?}
    C -->|是| D[解密证件号，校验姓名与身份证一致性]
    D -->|不一致| E[抛出异常: 业主姓名与身份证号不一致]
    C -->|否| F[跳过]
    E --> F
    F --> G{有代理人且证件类型为身份证?}
    G -->|是| H[解密证件号，校验代理人信息]
    H -->|不一致| I[抛出异常: 代理人信息不一致]
    G -->|否| J[继续]
    I --> J
    B -->|公司| K{公司代理人证件类型为身份证?}
    K -->|是| L[校验公司代理人信息]
    L -->|不一致| M[抛出异常: 公司代理人信息不一致]
    K -->|否| N{法人证件类型为身份证?}
    M --> N
    N -->|是| O[校验法人信息]
    O -->|不一致| P[抛出异常: 法人信息不一致]
    N -->|否| Q[返回 true]
    P --> Q
```

#### 直接调用的校验方法

除反射调用外，`ContractUnifyService` 中还存在两个直接调用的校验场景：

1. **`checkCompanyInfo`** — 在 `ContractUnifyService.checkParamLegitimacy()` 中直接调用，校验公司信息合法性
2. **`checkDesignAmount`** — 在 `ContractUnifyService.checkParamLegitimacy()` 中直接调用，校验设计服务费（仅对设计变更/套餐变更合同类型）

---

### WorkerTypeCheckService

**职责**：提供通用的工种校验能力，通过 RPC 查询人员信息，判断手机号对应的人员是否属于指定工种。

#### 核心能力

```mermaid
flowchart LR
    A[输入: mobile + WorkTypeEnum 数组] --> B[hasWorkerType]
    B --> C[CeresRpc.queryWorkerByMobile]
    C --> D{查询到人员信息?}
    D -->|否| E[返回 false]
    D -->|是| F[获取岗位列表 positions]
    F --> G{任一岗位的 workTypeCode 匹配?}
    G -->|是| H[返回 true]
    G -->|否| E

    I[输入: mobile + errorMsg + WorkTypeEnum 数组] --> J[checkWorkerType]
    J --> K[hasWorkerType]
    K -->|true| L[抛出 NrsBusinessException]
    K -->|false| M[校验通过]
```

#### 方法说明

| 方法 | 签名 | 说明 |
|------|------|------|
| `hasWorkerType` | `(String mobile, WorkTypeEnum... workTypes) → boolean` | 判断手机号对应的人员是否包含任一指定工种，支持可变参数传入多种工种 |
| `checkWorkerType` | `(String mobile, String errorMsg, WorkTypeEnum... workTypes) → void` | 校验手机号不能为指定工种，匹配则抛出 `NrsBusinessException` |

#### 外部依赖

- **CeresRpc**：通过 `queryWorkerByMobile(mobile)` 查询人员详情（`PersonHighDetailDTO`），获取岗位列表（`PersonPositionHighDetailDTO`），比对 `workTypeCode` 与传入的 `WorkTypeEnum.code`

---

## 模块间依赖关系

```mermaid
graph LR
    subgraph ContractFieldValidation
        CFCS[ContractFieldCheckService]
        WTCS[WorkerTypeCheckService]
    end

    subgraph 合同核心模块
        CUS[ContractUnifyService]
        COMMON[CommonContractService]
        CBIZ[ContractBusinessService]
        CBBIZ[CommonBusinessService]
        ADMIN[AdminService]
    end

    subgraph 基础设施
        CIPHER[CipherService]
        CAC[ApolloConfig]
        FIS[FundInfoService]
        FBS[FundBaseService]
    end

    subgraph 计算模块
        DFC[DesignFeeCalculator]
    end

    subgraph 外部系统
        CERES[CeresRpc]
    end

    subgraph 上下文
        CTX[ContractContextHandler]
    end

    CFCS --> COMMON
    CFCS --> CBIZ
    CFCS --> CBBIZ
    CFCS --> ADMIN
    CFCS --> CIPHER
    CFCS --> CAC
    CFCS --> FIS
    CFCS --> DFC
    CFCS --> CUS
    CFCS -.->|ThreadLocal| CTX

    WTCS --> CERES

    CUS -->|反射调用| CFCS
```

### 依赖模块说明

| 依赖模块 | 文件 | 用途 |
|---------|------|------|
| [ContractOperations](ContractOperations.md) | ContractUnifyService | 校验入口，读取字段配置后反射调用本模块的校验方法 |
| [ContractContextAop](ContractContextAop.md) | ContractContextHandler | 通过 ThreadLocal 获取当前请求上下文（如城市公司信息、报价 DTO 等） |
| CipherService | - | 身份证号加解密，`checkIdCardInfo` 中解密后校验 |
| CommonContractService | - | 提供 `checkIdName` 方法，校验姓名与身份证号一致性 |
| ContractBusinessService | - | 提供 `checkCompanyInfo` 方法，校验企业信用代码 |
| DesignFeeCalculator | - | 判断是否跳过设计费计算校验 |
| FundInfoService | - | 查询款项信息，用于 `checkBrandTotalAmount` 校验已付金额 |
| AdminService | - | 获取 PDF 文件大小，用于 `checkAdvanceFileSize` |
| ContractApolloConfig | - | 动态配置中心，提供品类名称映射、预收比例、城市编码等配置 |

---

## 数据流

### 合同提交时的校验数据流

```mermaid
sequenceDiagram
    participant Client as 前端
    participant CUS as ContractUnifyService
    participant CFC as ContractFieldConfig
    participant CFCS as ContractFieldCheckService
    participant CTX as ContractContextHandler
    participant Ext as 外部服务

    Client->>CUS: 提交合同 ContractReqDTO
    CUS->>CFC: 查询字段配置（gbCode, companyCode, businessType, contractType）
    CFC-->>CUS: List of ContractFieldConfig

    loop 遍历有 checkFunction 的配置
        CUS->>CUS: conditionCheck 条件评估

        alt 条件满足
            CUS->>CFCS: checkContractField(contractReq, functionName)
            CFCS->>CFCS: 反射查找并调用方法

            alt checkBrandList
                CFCS->>CTX: getContractCityCompanyInfo()
                CTX-->>CFCS: 公司信息
                CFCS->>CFCS: 校验品类编号、金额求和、占比
            else checkIdCardInfo
                CFCS->>Ext: cipherService.decrypt(证件号)
                CFCS->>Ext: commonContractService.checkIdName()
            else checkAdvanceAmount
                CFCS->>Ext: contractUnifyService.getAdvanceFromQuotation()
                CFCS->>CFCS: 校验首期款范围
            else checkDesignAmount
                CFCS->>Ext: designFeeCalculator.shouldSkipCalculateDesignFee()
                CFCS->>Ext: contractUnifyService.designFeeCalculateIsOpen()
                CFCS->>CFCS: 校验设计费优惠前后
            end

            CFCS-->>CUS: true/false
        end
    end

    alt 全部校验通过
        CUS->>CUS: 继续合同提交流程
    else 校验失败
        CUS-->>Client: 抛出业务异常
    end
```

---

## 关键设计模式

### 1. 反射驱动的策略校验

模块最核心的设计是**基于反射的动态校验调度**：

- 校验方法的名称存储在 `ContractFieldConfig.checkFunction` 字段中
- 运行时通过 `ReflectionUtils.findMethod` 查找方法，`ReflectionUtils.invokeMethod` 调用
- 方法签名统一为 `public boolean methodName(ContractReqDTO contractReq)`
- 返回 `true` 表示校验通过，返回 `false` 或抛出异常表示校验失败

**优势**：新增校验规则只需添加方法 + 配置记录，无需修改调用方代码。

**约束**：方法名不能修改、方法不能删除（见类注释中的三重强调）。

### 2. 条件化校验（ConditionCheck）

`ContractUnifyService.contractFieldCheck` 在调用校验方法前会先执行 `conditionCheck` 评估，只有满足条件的校验才会被执行。这使得同一套校验配置可以按城市、业务类型、合同类型等维度差异化生效。

### 3. 配置驱动的校验范围

校验范围由以下维度的配置决定：

```mermaid
graph TD
    A[ContractFieldConfig] --> B[gbCode 城市编码]
    A --> C[companyCode 公司编码]
    A --> D[businessType 业务类型]
    A --> E[contractType 合同类型]
    A --> F[fieldConfigVersion 配置版本]
    A --> G[checkFunction 校验方法名]
    A --> H[conditionCheck 条件表达式]
```

不同城市、公司、业务类型可以配置不同的校验规则组合，实现灵活的差异化校验策略。

### 4. 双通道校验

校验方法分为两种调用通道：

| 通道 | 触发方式 | 适用场景 |
|------|---------|---------|
| 反射调用 | `checkContractField(contractReq, functionName)` | 配置化的通用字段校验（品类、金额、房屋类型等） |
| 直接调用 | `contractFieldCheckService.checkXxx(contractReq)` | 特定场景的硬编码校验（公司信息、设计费） |

### 5. 加密数据的校验处理

`checkIdCardInfo` 中涉及敏感数据（身份证号）的校验时，先通过 `CipherService.decrypt` 解密后再调用 `CommonContractService.checkIdName` 进行一致性比对，确保校验逻辑工作在明文数据上，同时不泄露解密后的数据到日志或前端。

---

## 与相邻模块的关系

| 相关模块 | 关系描述 |
|---------|---------|
| [ContractOperations](ContractOperations.md) | `ContractUnifyService` 是本模块的主要调用方，在合同保存草稿、提交、变更等流程中触发字段校验 |
| [ContractContextAop](ContractContextAop.md) | `ContractContextAspect` 在请求进入时初始化上下文，本模块通过 `ContractContextHandler` 读取上下文中的城市公司信息、报价 DTO 等数据 |
| [ContractPdfGeneration](ContractPdfGeneration.md) | PDF 生成前的数据准备阶段依赖本模块的校验结果，确保字段数据合法 |
| [MaterialPdfUtils](MaterialPdfUtils.md) | `checkBrandList` 中的品类校验与材料清单有关联，确保品类编号在有效范围内 |
