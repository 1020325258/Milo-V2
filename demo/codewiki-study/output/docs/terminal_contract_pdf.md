# Terminal Contract PDF 模块 — 解约协议 PDF 生成服务

## 模块概述

`terminal_contract_pdf` 模块负责**解约协议 PDF 的数据填充与生成**。当客户发起家装项目退单（解约）时，系统需要生成一份正式的解约协议 PDF 文档，包含乙方公司信息、房屋地址、关联已签署合同、款项明细、保密违约金等关键条款内容。

该模块的核心类 `TerminalContractPdfBuildService` 是一个 Spring `@Component`，它不直接负责 PDF 的渲染（如 iText/pdfbox），而是作为 **PDF 数据供给层**，将各项业务字段以 `Map<String, Object>` 形式输出，供上游 PDF 模板引擎（如 FreeMarker）填充到解约协议模板中。

## 架构总览

```mermaid
graph TD
    A[ContractContextAspect 合同数据准备切面] -->|初始化 ThreadLocal 上下文| B[ContractContextHandler]
    B -->|提供上下文数据| C[TerminalContractPdfBuildService]

    C -->|查询乙方公司信息| D[ContractCompanyInfoService]
    C -->|查询正向合同| E[ContractBusinessService]
    C -->|查询合同字段| F[ContractFieldService]
    C -->|查询合同列表| G[ContractService]
    C -->|获取业务类型| H[CommonBusinessService]
    C -->|查询退单记录| I[CancelOrderService]
    C -->|构建合并发起退单DTO| J[CommonContractService]
    C -->|金额加密解密| K[CipherService]

    C -->|输出 PDF 数据 Map| L[PDF 模板引擎]

    subgraph 上游触发层
        M[合同提交接口] -->|ContractDataPrepare注解| A
    end

    subgraph 数据供给层
        C
    end

    subgraph 数据访问层
        D
        E
        F
        G
        H
        I
        J
        K
    end
```

## 核心组件详解

### TerminalContractPdfBuildService

**职责**：解约协议 PDF 各项数据段的构建与格式化，是本模块唯一的核心组件。

**依赖注入的服务列表**：

| 依赖服务 | 来源模块 | 用途 |
|---------|---------|------|
| `ContractCompanyInfoService` | [contract_context](contract_context.md) | 查询乙方（装修公司）公司信息 |
| `ContractBusinessService` | [contract_context](contract_context.md) | 获取解约协议关联的正向合同信息 |
| `ContractFieldService` | [contract_context](contract_context.md) | 查询合同自定义字段（地址、区域等） |
| `ContractService` | [contract_context](contract_context.md) | 获取已签署合同列表 |
| `CommonBusinessService` | [contract_context](contract_context.md) | 获取业务类型、小程序类型等公共业务逻辑 |
| `CancelOrderService` | [contract_context](contract_context.md) | 查询最新退单记录（含资金明细） |
| `CommonContractService` | [contract_context](contract_context.md) | 获取公司信息、构建合并发起退单 DTO |
| `CipherService` | [contract_context](contract_context.md) | 银行卡号等敏感信息解密 |

**上下文依赖**：本服务大量依赖 `ContractContextHandler` 提供的 `ThreadLocal` 上下文，详见 [contract_context](contract_context.md) 模块文档。

## 公开方法清单

本服务对外暴露以下数据构建方法，每个方法返回 `Map<String, Object>`，键为 PDF 模板中的变量名：

```mermaid
graph LR
    S[TerminalContractPdfBuildService]

    S --> M1[getTerminalSecondPartyCompanyInfo]
    S --> M2[getTerminalProjectContractAddress]
    S --> M3[getTerminalSignContractInfo]
    S --> M4[getTerminalDetailFundInfo]
    S --> M5[getTerminalTotalFundInfo]
    S --> M6[getTerminalRetrieveMaterialDays]
    S --> M7[getBreachPenaltyAmount]
    S --> M8[getTerminalRelationHouseFormalInfo]

    M1 -->|输出| R1[companyName]
    M2 -->|输出| R2[projectContractAddress]
    M3 -->|输出| R3[terminalSignContractInfo]
    M4 -->|输出| R4[terminalDetailFundInfo]
    M5 -->|输出| R5[terminalTotalFundInfo]
    M6 -->|输出| R6[terminalRetrieveMaterialDays]
    M7 -->|输出| R7[breachPenaltyAmount]
    M8 -->|输出| R8[houseFormalCompanyName, houseFormalContractName]
```

## 数据流与处理逻辑

### 1. 乙方公司信息 (`getTerminalSecondPartyCompanyInfo`)

```mermaid
sequenceDiagram
    participant S as TerminalContractPdfBuildService
    participant Ctx as ContractContextHandler
    participant Biz as ContractBusinessService
    participant CI as ContractCompanyInfoService

    S->>Ctx: getContractReq().getProjectOrderId()
    S->>Biz: getTerminalUseContractInfo(projectOrderId, false)
    Biz-->>S: Contract 正向合同
    S->>CI: getByCompanyCode(contract.companyCode)
    CI-->>S: ContractCompanyInfo
    S-->>S: {companyName: 公司名称}
```

通过项目订单号找到对应的正向签约合同，再根据公司编码查询公司全称。

### 2. 房屋地址 (`getTerminalProjectContractAddress`)

从正向合同的自定义字段中拼接完整地址：`城市-区域-小区-楼栋-单元-楼层-门牌号`。地址各层级通过 `ContractField` 的 `fieldKey` 提取，城市名称通过 `CityEnum` 枚举转换。

### 3. 已签署合同信息 (`getTerminalSignContractInfo`)

```mermaid
flowchart TD
    A[获取项目所有已签署合同] --> B{按合同类型分组}
    B --> C[设计合同 + 设计变更合同]
    B --> D[正签/首期款/正签变更合同]

    C --> E{设计合同编号非空?}
    E -->|是| F[拼接设计服务协议文本]
    E -->|否| G[跳过]

    D --> H{业务类型判断}
    H -->|团装| I[家庭居室团体装饰装修合同]
    H -->|整装 被窝| J[室内装饰装修工程施工合同]
    H -->|整装 圣都 整装| K[家庭居室装饰装修施工合同]
    H -->|整装 圣都 局装| L[住宅局部改造装修施工合同]
    H -->|翻新全案| M[住宅局部翻新装修施工合同]
    H -->|仅首期款| N[施工首期工程款合同]

    F --> O[拼接最终合同信息文本]
    I --> O
    J --> O
    K --> O
    L --> O
    M --> O
    N --> O
```

合同名称根据**业务类型**和**小程序渠道**（被窝 vs 圣都）动态选择，这是解约协议中引用原始协议的关键段落。

### 4. 款项明细 (`getTerminalDetailFundInfo`)

根据**退单资金数据**生成已支付金额、违约金、实际已发生费用的明细文本。

```mermaid
flowchart TD
    A[buildCancelOrderBaseInfo] --> B{合并发起模式?}
    B -->|否| C[cancelOrderService.getLastRecordByProjectOrderId]
    B -->|是| D[commonContractService.buildMergeLaunchCancelOrderDTO]

    C --> E[CancelOrderBaseInfoDTO]
    D --> E

    E --> F[fundAmountList 资金明细列表]
    F --> G{业务类型?}
    G -->|团装 GROUP_DECORATE| H[团装模板: 仅工程款 + 违约金 + 施工费]
    G -->|整装/局装/翻新| I[通用模板: 设计费 + 工程款 + 违约金 + 施工费 + 设计服务费]

    H --> J[格式化金额 + 大写金额]
    I --> J
    J --> K[输出 terminalDetailFundInfo]
```

关键差异：
- **团装**：只涉及工程款，不区分设计费
- **整装/局装/翻新**：分别列出设计服务费和工程款

资金类型通过 `FundTypeEnum` 枚举区分：`DESIGN_CHARGE`（设计费）、`PROJECT_CHARGE`（工程款）、`LIQUIDATED_DAMAGES`（违约金）。

### 5. 总款项信息 (`getTerminalTotalFundInfo`)

```mermaid
flowchart TD
    A[获取退单总金额] --> B[扣除定金金额]
    B --> C{cancelOrderAmount > 0?}

    C -->|甲方需付款| D[付款模板: 10个工作日内支付]
    C -->|乙方需退款| E[获取退款信息]

    E --> F[解析 refundInfo JSON]
    F --> G[获取银行卡信息]
    F --> H{退款渠道?}

    H -->|BACKTRACK 原路退回| I[方式1: 退回原支付账户]
    H -->|BANK 银行转账| J[方式2: 退至指定账户]
    H -->|REFUND_TO_WALLET 退至余额| K[方式3: 退至客户端余额]

    D --> L[输出 terminalTotalFundInfo]
    I --> L
    J --> L
    K --> L
```

退款渠道通过 `RefundChannelEnum` 枚举区分，退款模板包含三种方式：
1. **原路退回**：微信/支付宝/理房通原支付账户
2. **指定银行账户**：需提供开户行、户名、账号
3. **客户端余额**：可消费或提现

银行账号通过 `CipherService.decrypt()` 解密后展示。

### 6. 其他条款字段

| 方法 | 输出字段 | 数据来源 | 说明 |
|------|---------|---------|------|
| `getTerminalRetrieveMaterialDays` | `terminalRetrieveMaterialDays` | `ContractProjectInfoReq` | 已开工时乙方可取回剩余施工材料的天数，默认"/" |
| `getBreachPenaltyAmount` | `breachPenaltyAmount` | `ContractProjectInfoReq` | 保密义务违约金金额，默认"/" |
| `getTerminalRelationHouseFormalInfo` | `houseFormalCompanyName`, `houseFormalContractName` | 合并发起的合同列表 | 仅合并发起模式下填充家装正签合同信息 |

## 模块间依赖关系

```mermaid
graph TD
    subgraph terminal_contract_pdf
        TCS[TerminalContractPdfBuildService]
    end

    subgraph contract_context
        CCH[ContractContextHandler]
        CCA[ContractContextAspect]
        CBI[ContractBusinessService]
        CCI[ContractCompanyInfoService]
        CFS[ContractFieldService]
        CS[ContractService]
        CBS[CommonBusinessService]
        CCS[CommonContractService]
    end

    subgraph change_contract_strategy
        CCSF[ChangeContractStrategyFactory]
    end

    subgraph contract_signing_source
        CSS[ContractSigningSource]
    end

    subgraph contract_validation
        CFC[ContractFieldCheckService]
    end

    CCA -->|Before切面初始化上下文| CCH
    CCH -->|ThreadLocal 数据| TCS
    TCS --> CBI
    TCS --> CCI
    TCS --> CFS
    TCS --> CS
    TCS --> CBS
    TCS --> CCS

    CCA -.->|数据准备完成后再调用| TCS
```

> **注**：`TerminalContractPdfBuildService` 不直接依赖 `change_contract_strategy`、`contract_signing_source`、`contract_validation` 等模块。这些模块在合同提交、变更等流程中使用，而解约协议 PDF 生成是独立的数据填充步骤。

## 关键设计模式

### 1. ThreadLocal 上下文模式

`TerminalContractPdfBuildService` 的所有方法都通过 `ContractContextHandler.getContractReq()` 获取上下文数据，而非通过方法参数传入。这种设计：

- **优势**：方法签名简洁，多个 PDF 字段构建方法共享同一上下文，无需层层传参
- **前提**：调用前必须由 `ContractContextAspect`（AOP 切面）初始化上下文，方法执行完毕后切面自动清理

```mermaid
sequenceDiagram
    participant Controller as 合同 Controller
    participant Aspect as ContractContextAspect
    participant Ctx as ContractContextHandler ThreadLocal
    participant Svc as TerminalContractPdfBuildService
    participant Engine as PDF 模板引擎

    Controller->>Aspect: @ContractDataPrepare 方法执行
    Aspect->>Ctx: initContext + 并行加载数据
    Aspect->>Controller: 执行目标方法
    Controller->>Svc: getTerminalSecondPartyCompanyInfo
    Svc->>Ctx: getContractReq()
    Ctx-->>Svc: ContractReqDTO
    Svc-->>Controller: Map 结果
    Controller->>Svc: getTerminalDetailFundInfo
    Svc->>Ctx: getProjectInfo()
    Ctx-->>Svc: ProjectInfoDTO
    Svc-->>Controller: Map 结果
    Controller->>Engine: 填充所有 Map 到模板
    Engine-->>Controller: PDF 文件
    Aspect->>Ctx: clearContext
```

### 2. 合并发起 vs 普通发起的分支处理

解约协议的退单数据来源有两种路径：

```mermaid
flowchart LR
    A[buildCancelOrderBaseInfo] --> B{isMergeLaunch?}
    B -->|普通发起| C[从退单记录获取<br/>cancelOrderService.getLastRecordByProjectOrderId]
    B -->|合并发起| C[从基金信息构建<br/>commonContractService.buildMergeLaunchCancelOrderDTO]
    C --> D[CancelOrderBaseInfoDTO]
```

- **普通发起**：用户先有退单操作，解约协议关联已有的退单记录
- **合并发起**：解约协议与正向合同同时发起，退单数据需要从基金信息中临时构建

### 3. 金额格式化的防御式编程

所有金额展示统一使用 `formatAmount` / `formatAmountText` 通用方法，对 `null` 值、零值统一返回"/"，避免 PDF 中出现 `null` 或空白。人民币大写通过 `MoneyConvertUtil` 工具类转换。

## 装修业务类型对合同名称的影响

解约协议中引用的原始合同名称取决于业务类型，这是理解本模块的关键业务知识：

| 业务类型 (BusinessTypeEnum) | 合同名称 | 适用场景 |
|---------------------------|---------|---------|
| `GROUP_DECORATE` | 家庭居室团体装饰装修合同 | 团装项目 |
| `HOUSE_CERTIFICATE`（圣都） | 家庭居室装饰装修施工合同 | 整装项目 |
| `PART_DECORATE`（圣都） | 住宅局部改造装修施工合同 | 局装项目 |
| `REFORM_ALL`（圣都） | 住宅局部翻新装修施工合同 | 翻新全案 |
| 被窝小程序 | 室内装饰装修工程施工合同 | 被窝渠道所有类型 |
| 仅有首期款（非翻新） | 施工首期工程款合同 | 未签正签合同 |
| 仅有首期款（翻新） | 硬装首期款合同 | 翻新项目未签正签合同 |

## 异常处理

模块在以下场景抛出 `NrsBusinessException`（`SHOW_TO_CLIENT` 级别，前端可展示）：

| 场景 | 触发方法 | 错误信息 |
|------|---------|---------|
| 正向合同信息为空 | `getTerminalSecondPartyCompanyInfo` | 解约协议对应正向签约乙方公司信息失败 |
| 房屋地址获取失败 | `getTerminalProjectContractAddress` | 获取解约协议的房屋地址信息失败 |
| 正签和首期款合同都为空 | `getTerminalSignContractInfo` | 生成解约协议，构建合同pdf失败，正签和首期款合同信息都为空 |
| 合并发起缺少正签合同 | `getTerminalRelationHouseFormalInfo` | 合并发起模式生成解约协议，构建合同pdf失败，正签合同信息为空 |
