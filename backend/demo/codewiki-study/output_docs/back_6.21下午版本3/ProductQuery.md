# ProductQuery 模块文档

## 1. 模块概述

`ProductQuery` 模块是合同签署流程中的**产品信息查询层**，负责根据主订单号和报价单号/变更单号，从订单标准化查询服务中获取个性化报价商品（SKU）信息。该模块为 [ContractSigningSource](ContractSigningSource.md) 策略族提供商品数据支撑，是合同签署"商品信息构建"环节的核心数据来源。

模块仅包含一个服务类 `ProductQueryService`，对外暴露两个查询方法：

| 方法 | 入参 | 出参 | 场景 |
|------|------|------|------|
| `getQuotationProductDTOS` | projectOrderId + billCodeList | `List<QuotationProductDTO>` | 报价单签署时查询商品 |
| `getChangeQuotationProductDTOS` | projectOrderId + changeOrderId | `List<ChangeQuotationProductDTO>` | 变更单签署时查询商品 |

## 2. 架构位置

ProductQuery 在个性化合同签署体系中处于**数据查询层**，位于调用链的中间位置：

```mermaid
graph TD
    Router[ContractSigningSourceRouter 路由]
    BillStrategy[BillSigningSourceStrategy 报价单策略]
    ChangeStrategy[ChangeOrderSigningSourceStrategy 变更单策略]
    SubOrderStrategy[SubOrderSigningSourceStrategy 子订单策略]
    PQS[ProductQueryService 商品查询服务]
    RPC[OrderStandardQueryRpc RPC远程调用]
    Remote[远程订单服务 HomeProject]

    Router --> BillStrategy
    Router --> ChangeStrategy
    Router --> SubOrderStrategy
    BillStrategy --> PQS
    ChangeStrategy --> PQS
    PQS --> RPC
    RPC --> Remote

    style PQS fill:#4A90D9,color:#fff
    style RPC fill:#7B68EE,color:#fff
```

## 3. 核心组件详解

### 3.1 ProductQueryService

Spring `@Service`，通过 `OrderStandardQueryRpc` 远程调用获取商品数据，内部统一采用 `Optional` 链式取值 + Stream 聚合的模式处理数据。

#### 3.1.1 getQuotationProductDTOS（报价单商品查询）

```mermaid
flowchart TD
    Start[入参: projectOrderId + billCodeList] --> Empty{billCodeList为空?}
    Empty -->|是| ReturnEmpty[返回空列表]
    Empty -->|否| Loop[遍历 billCodeList]
    Loop --> RPC1[调用 orderStandardQueryRpc.queryHomeProjectAndQuotationSkuList]
    RPC1 --> Extract[Optional链式取值: HomeProject -> MainOrder -> CostControl -> QuotationModule -> PersonalQuotation]
    Extract --> Fail{取值失败?}
    Fail -->|是| Throw1[抛出 NrsBusinessException]
    Fail -->|否| Merge[合并套餐商品 + 单品列表]
    Merge --> Add[添加到结果集]
    Add --> Loop
    Loop -->|遍历完成| Return[返回全部 QuotationProductDTO]

    style Start fill:#52C41A,color:#fff
    style Return fill:#52C41A,color:#fff
    style Throw1 fill:#FF4D4F,color:#fff
```

**数据取值链路：**

```
HomeProject
  └── MainOrder
        └── CostControl
              └── QuotationModule
                    └── PersonalQuotation (ComboQuotationListDTO)
                          ├── comboList -> 每个套餐的 quotationProductList (套餐内商品)
                          └── quotationList (单品列表)
```

**商品合并逻辑：** 将套餐内商品（`combo.quotationProductList`）与单品（`quotationList`）通过 `Stream.concat` 合并，并过滤 `null`。

#### 3.1.2 getChangeQuotationProductDTOS（变更单商品查询）

```mermaid
flowchart TD
    Start[入参: projectOrderId + changeOrderId] --> RPC1[调用 orderStandardQueryRpc.queryHomeProjectAndChangeQuotationSkuList]
    RPC1 --> Extract[Optional链式取值: HomeProject -> MainOrder -> CostControl -> ChangeQuotationModule -> PersonalQuotation]
    Extract --> Fail{取值失败?}
    Fail -->|是| Throw1[抛出 NrsBusinessException]
    Fail -->|否| Merge[合并变更套餐商品 + 变更单品列表]
    Merge --> Return[返回全部 ChangeQuotationProductDTO]

    style Start fill:#52C41A,color:#fff
    style Return fill:#52C41A,color:#fff
    style Throw1 fill:#FF4D4F,color:#fff
```

**数据取值链路：**

```
HomeProject
  └── MainOrder
        └── CostControl
              └── ChangeQuotationModule
                    └── PersonalQuotation (ChangeComboQuotationListDTO)
                          ├── comboList -> 每个变更套餐的 quotationProductList
                          └── quotationList (变更单品列表)
```

## 4. 依赖关系

### 4.1 上游依赖

| 依赖组件 | 依赖方式 | 说明 |
|----------|----------|------|
| `OrderStandardQueryRpc` | `@Resource` 注入 | 远程过程调用，查询 HomeProject 及其关联的报价/变更 SKU 列表 |

### 4.2 下游调用方

| 调用方 | 调用方法 | 使用场景 |
|--------|----------|----------|
| `BillSigningSourceStrategy` | `getQuotationProductDTOS` | 通过报价单号获取 SKU 商品，用于构建 goodsInfo 和商品类目信息 |
| `ChangeOrderSigningSourceStrategy` | `getChangeQuotationProductDTOS` | 通过变更单号获取 SKU 商品，用于构建变更单的 goodsInfo |

```mermaid
graph LR
    subgraph 调用方
        BillStrategy[BillSigningSourceStrategy]
        ChangeStrategy[ChangeOrderSigningSourceStrategy]
    end

    subgraph ProductQuery模块
        PQS[ProductQueryService]
    end

    subgraph 外部依赖
        RPC[OrderStandardQueryRpc]
    end

    BillStrategy -->|getQuotationProductDTOS| PQS
    ChangeStrategy -->|getChangeQuotationProductDTOS| PQS
    PQS --> RPC

    style PQS fill:#4A90D9,color:#fff
```

## 5. 数据流

### 5.1 报价单签署的商品查询数据流

```mermaid
sequenceDiagram
    participant BS as BillSigningSourceStrategy
    participant PQS as ProductQueryService
    participant RPC as OrderStandardQueryRpc
    participant Remote as 远程订单服务

    BS->>PQS: getQuotationProductDTOS(projectOrderId, billCodeList)
    loop 遍历每个 billCode
        PQS->>RPC: queryHomeProjectAndQuotationSkuList(projectOrderId, billCode)
        RPC->>Remote: RPC 调用
        Remote-->>RPC: HomeProject
        RPC-->>PQS: HomeProject
        PQS->>PQS: Optional链取值 -> PersonalQuotation
        PQS->>PQS: 合并 comboList商品 + quotationList单品
    end
    PQS-->>BS: List of QuotationProductDTO
    BS->>BS: 提取 SkuProduct, 构建 goodsInfo
```

### 5.2 变更单签署的商品查询数据流

```mermaid
sequenceDiagram
    participant CS as ChangeOrderSigningSourceStrategy
    participant PQS as ProductQueryService
    participant RPC as OrderStandardQueryRpc
    participant Remote as 远程订单服务

    CS->>PQS: getChangeQuotationProductDTOS(projectOrderId, changeOrderId)
    PQS->>RPC: queryHomeProjectAndChangeQuotationSkuList(projectOrderId, changeOrderId)
    RPC->>Remote: RPC 调用
    Remote-->>RPC: HomeProject
    RPC-->>PQS: HomeProject
    PQS->>PQS: Optional链取值 -> ChangePersonalQuotation
    PQS->>PQS: 合并 comboList商品 + quotationList单品
    PQS-->>CS: List of ChangeQuotationProductDTO
    CS->>CS: 提取 SkuProduct, 构建变更单 goodsInfo
```

## 6. 关键设计模式

### 6.1 Optional 防空链式取值

两个方法均采用 `Optional.ofNullable().map().map()...orElseThrow()` 模式逐层取值，避免深层对象的空指针异常。当任一中间节点为 `null` 时，统一抛出 `NrsBusinessException("通过主订单查询商品信息失败")`。

### 6.2 套餐 + 单品合并模式

```
最终商品列表 = Stream.concat(套餐内商品流, 单品流).filter(nonNull)
```

报价数据采用"套餐 + 单品"的二元结构：
- **套餐（Combo）**：嵌套结构，需 `flatMap` 展开内部 `quotationProductList`
- **单品（Quotation）**：扁平结构，直接作为 Stream 元素

两个方法的数据合并模式完全一致，差异仅在 DTO 类型（`QuotationProductDTO` vs `ChangeQuotationProductDTO`）和数据路径（`QuotationModule` vs `ChangeQuotationModule`）。

### 6.3 逐单循环查询 vs 单次查询

- `getQuotationProductDTOS`：对 `billCodeList` 逐个循环查询，因为 RPC 接口按单个报价单号查询
- `getChangeQuotationProductDTOS`：单次查询，因为变更单通过唯一 `changeOrderId` 标识

## 7. 模块在整体系统中的角色

```mermaid
graph TD
    subgraph 合同签署流程
        Router[ContractSigningSourceRouter] --> Strategy[ContractSigningSource策略族]
    end

    subgraph 数据准备阶段
        Strategy --> QuoteQuery[queryPersonalQuoteInfo 查询个性化报价]
        Strategy --> GoodsBuild[buildGoodsInfo 构建商品信息]
        Strategy --> DrawBuild[buildPersonalDrawing 构建图纸]
    end

    subgraph 商品查询层
        PQS[ProductQueryService]
    end

    GoodsBuild --> PQS
    PQS --> RPC[OrderStandardQueryRpc]

    style PQS fill:#4A90D9,color:#fff
    style Strategy fill:#FAAD14,color:#fff
```

ProductQuery 模块在合同签署流程中的职责边界清晰：

- **职责**：根据订单标识查询商品 SKU 列表
- **不负责**：商品数据的转换、类目合并、图纸构建等业务逻辑（这些由策略类完成）
- **依赖方向**：策略类依赖 ProductQueryService，ProductQueryService 依赖 OrderStandardQueryRpc，单向无循环

该模块是 [ContractSigningSource](ContractSigningSource.md) 策略族构建商品信息（`buildGoodsInfo`）的唯一数据来源，被 `BillSigningSourceStrategy` 和 `ChangeOrderSigningSourceStrategy` 两个策略实现使用。
