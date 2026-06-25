# MaterialPdfDiff 模块文档

## 模块概述

`MaterialPdfDiff` 模块位于合同服务（Contract Service）的材料清单子系统中，路径为 `combo/material/pdf/`。该模块承担两项核心职责：

1. **数据差异检查**（`MaterialPdfDiffService`）：将远程 SCM 实时查询的套餐 SKU 数据与数据库中已持久化的材料 PDF 快照数据进行比对，判断数据是否一致，从而决定是否需要重新生成材料配送清单 PDF。
2. **PDF 生成工具**（`MaterialPdfUtil`）：封装 HTML 模板渲染、PDF 转换、S3 上传的完整流程，为上层调用方提供一站式 PDF 生成能力。

该模块是合同材料清单 PDF 生成管线中的关键环节，上游由 `MaterialPdfGenerator` 编排调用，下游依赖多个基础设施服务完成文件处理。

---

## 架构总览

```mermaid
graph TD
    subgraph 上游调用方
        CIMG[ComboInfoMaterialGenerator]
        MPDFG[MaterialPdfGenerator]
    end

    subgraph MaterialPdfDiff 模块
        MPDS[MaterialPdfDiffService]
        MPU[MaterialPdfUtil]
    end

    subgraph 数据模型
        CSVG[ComboSkuGroupDTO]
        CPMD[ContractMaterialPdfData]
        CSVO[ComboSkuVO]
        MIVO[MaterialPdfItemVO]
    end

    subgraph 基础设施
        HRU[HtmlRenderUtil]
        PU[PdfUtils]
        S3S[S3Service]
        CPFS[ContractPdfFileHandleService]
        AFP[AtomForPdfRpc]
    end

    CIMG -->|生成材料清单| MPDFG
    MPDFG -->|差异检查| MPDS
    MPDFG -->|PDF生成| MPU
    CSVG -->|远程数据| MPDS
    CPMD -->|数据库快照| MPDS
    MPDS -->|中间模型| CSVO
    CSVO -->|聚合结果| MIVO
    MPU --> HRU
    MPU --> PU
    MPU --> S3S
    MPU --> CPFS
    MPU -.->|已注入 未直接调用| AFP
```

---

## 核心组件详解

### MaterialPdfDiffService

`MaterialPdfDiffService` 是一个**无状态纯服务**（`@Service`），不依赖任何外部资源注入。其设计遵循"**先转换、再聚合、后比较**"的三段式差异比对策略。

```mermaid
graph TD
    START[isConsistent 入口] --> STEP1[步骤1: 远程数据转换]
    START --> STEP2[步骤2: 数据库数据转换]
    STEP1 -->|convertFromSkuGroup| CSVO1[ComboSkuVO 列表]
    STEP2 -->|convertFromDbData| CSVO2[ComboSkuVO 列表]
    CSVO1 --> AGG1[aggregateMaterialData 聚合]
    CSVO2 --> AGG2[aggregateMaterialData 聚合]
    AGG1 --> MIVO1[MaterialPdfItemVO 列表]
    AGG2 --> MIVO2[MaterialPdfItemVO 列表]
    MIVO1 --> SIZE{数量相同?}
    MIVO2 --> SIZE
    SIZE -->|否| FALSE[返回 false]
    SIZE -->|是| KEY[构建比较键集合]
    KEY --> EQUAL{Set 相等?}
    EQUAL -->|否| FALSE2[返回 false]
    EQUAL -->|是| TRUE[返回 true 一致]
```

#### 方法清单

| 方法 | 可见性 | 职责 |
|------|--------|------|
| `isConsistent` | public | 入口方法，接收远程数据和数据库数据，返回一致性布尔值 |
| `convertFromSkuGroup` | public | 将 `ComboSkuGroupDTO` 转换为 `List<ComboSkuVO>`，按 `(categoryLevel3Code + brandCode)` 去重 |
| `convertFromDbData` | public | 将 `List<ContractMaterialPdfData>` 转换为 `List<ComboSkuVO>` |
| `compareMaterialData` | private | 执行聚合后的集合比较 |
| `aggregateMaterialData` | private | 按三级类目分组、过滤"其他"品牌、拼接品牌名、排序并编号 |
| `buildMaterialItemCompareKey` | private | 构建 `categoryLevel3Name\|brandNames` 格式的唯一比较键 |

#### 数据聚合规则

`aggregateMaterialData` 方法执行的聚合逻辑是整个差异比对的核心，规则如下：

| 步骤 | 规则 | 说明 |
|------|------|------|
| 1 | 按 `categoryLevel3Code` 分组 | 同一三级类目下的 SKU 归为一组 |
| 2 | 过滤 `brandName == "其他"` | 排除非特定品牌项 |
| 3 | 品牌名去重后按字母序排序，以 `/` 连接 | 例如 `"TOTO/科勒/箭牌"` |
| 4 | 过滤品牌为空的组 | 品牌全被过滤的三级类目不参与比较 |
| 5 | 按 `categoryLevel3Name` 正序排序并编号 | 生成带序号的最终列表 |

#### 比较键生成

最终比较键格式为 `categoryLevel3Name|brandNames`，例如：`"马桶|TOTO/科勒"`。两侧数据各自生成 `Set<String>`，通过 `Set.equals()` 实现无序比较，确保品牌顺序差异不影响结果。

---

### MaterialPdfUtil

`MaterialPdfUtil` 是一个 `@Component`，封装了 PDF 生成的完整基础设施调用链。

```mermaid
sequenceDiagram
    participant Caller as MaterialPdfGenerator
    participant MPU as MaterialPdfUtil
    participant HRU as HtmlRenderUtil
    participant PU as PdfUtils
    participant CPFS as ContractPdfFileHandleService
    participant S3 as S3Service

    Caller->>MPU: doGeneral(templateFile, key, data)
    MPU->>HRU: render(templateFile, data)
    HRU-->>MPU: HTML 字符串
    MPU->>PU: getPdfS3Url(html, null, null)
    PU-->>MPU: PDF S3 URL
    MPU->>MPU: hostReplacement(外网 → 内网)
    MPU->>CPFS: downloadFileFromUrl(url, tempPath)
    CPFS-->>MPU: 临时 PDF 文件
    MPU->>S3: uploadPublic(bytes, key)
    S3-->>MPU: 最终 PDF 公网 URL
    MPU->>CPFS: cleanUp(tempPath)
    MPU-->>Caller: 材料清单 PDF URL
```

#### 内外网地址替换

`MaterialPdfUtil` 包含一个特殊的 host 替换逻辑，将外网 CDN 地址替换为内网地址以提高文件下载速度：

| 配置 | 值 | 用途 |
|------|-----|------|
| `REPLACE_HOST` | `https://file.ljcdn.com` | 外网 CDN 地址 |
| `TARGE_HOST` | `http://file.media.lianjia.com` | 内网文件服务地址 |

当 `PdfUtils` 返回的 S3 URL 以 `REPLACE_HOST` 开头时，自动替换为 `TARGE_HOST`，确保后续 `downloadFileFromUrl` 走内网下载。

---

## 数据模型

```mermaid
classDiagram
    class ComboSkuGroupDTO {
        +Long comboId
        +List~ComboSkuDTO~ skuList
    }

    class ComboSkuDTO {
        +String categoryLevel3Code
        +String categoryLevel3Name
        +String brandCode
        +String brandName
    }

    class ContractMaterialPdfData {
        +String comboCode
        +String categoryLevel3Code
        +String categoryLevel3Name
        +String brandCode
        +String brandName
        +String createUserId
        +String updateUserId
        +Date ctime
        +Date mtime
        +Integer delStatus
    }

    class ComboSkuVO {
        +String categoryLevel3Code
        +String categoryLevel3Name
        +String brandCode
        +String brandName
    }

    class MaterialPdfItemVO {
        +String categoryLevel3Name
        +String brandNames
        +String sequenceNumber
    }

    ComboSkuGroupDTO --> ComboSkuDTO : 包含
    ComboSkuDTO ..> ComboSkuVO : 转换
    ContractMaterialPdfData ..> ComboSkuVO : 转换
    ComboSkuVO ..> MaterialPdfItemVO : 聚合
```

模型层次说明：

| 模型 | 来源 | 角色 |
|------|------|------|
| `ComboSkuGroupDTO` / `ComboSkuDTO` | SCM 远程接口 | 外部输入，远程实时数据 |
| `ContractMaterialPdfData` | 数据库（`ContractMaterialPdfDataRepository`） | 内部存储，上一次 PDF 生成时的快照 |
| `ComboSkuVO` | 模块内部 | 统一中间表示，消除远程 DTO 与 DB 模型的结构差异 |
| `MaterialPdfItemVO` | 模块内部 | 聚合后的最终比对单元和 PDF 渲染数据源 |

---

## 在合同模块中的定位

```mermaid
graph LR
    subgraph ContractCore
        CDS[ContractDetailService]
        CSBS[ContractSaveDraftService]
    end

    subgraph ContractPdfSelfCreate
        DCP[DrawingContractPdfBySelfStrategy]
        GFC[GroupFormalContractPdfBySelfStrategy]
        RFR[ReformAllFormalContractPdfBySelfStrategy]
    end

    subgraph MaterialPdfDiff
        MPDS[MaterialPdfDiffService]
        MPU[MaterialPdfUtil]
    end

    subgraph 上游编排
        CIMG[ComboInfoMaterialGenerator]
        MPDFG[MaterialPdfGenerator]
    end

    CIMG --> MPDFG
    MPDFG --> MPDS
    MPDFG --> MPU
    GFC -->|getMaterialPdf| MPDFG
    RFR -->|getMaterialPdf| MPDFG
    DCP -->|getMaterialPdf| MPDFG
    CDS -.->|合同详情中的材料信息| CIMG
```

`MaterialPdfDiff` 模块在合同体系中属于**合同 PDF 自生成**（[ContractPdfSelfCreate](ContractPdfSelfCreate.md)）的下游支撑模块。各种 PDF 生成策略（`DrawingContractPdfBySelfStrategy`、`GroupFormalContractPdfBySelfStrategy` 等）在生成正式合同时，需要附带材料配送清单 PDF，此时通过 `MaterialPdfGenerator` → `MaterialPdfDiffService` / `MaterialPdfUtil` 链路完成差异检查与 PDF 生成。

---

## 数据流

### 完整的差异检查与 PDF 生成流程

```mermaid
graph TD
    A[ComboInfoMaterialGenerator 调用入口] --> B[MaterialPdfGenerator.generateMaterialPdf]
    B --> C{需要生成 PDF?}
    C -->|调用 noNeedGenerateMaterialPdf| D[MaterialPdfDiffService.isConsistent]

    D --> E[convertFromSkuGroup 远程数据标准化]
    D --> F[convertFromDbData 数据库数据标准化]
    E --> G[aggregateMaterialData 远程数据聚合]
    F --> H[aggregateMaterialData 数据库数据聚合]
    G --> I[构建比较键集合]
    H --> I
    I --> J{Set 比较结果}

    J -->|一致| K[跳过生成 返回已有 PDF URL]
    J -->|不一致| L[MaterialPdfGenerator.generateMaterialPdfByComboSkus]
    L --> M[MaterialPdfUtil.doGeneral]
    M --> N[HTML 模板渲染]
    N --> O[HTML 转 PDF]
    O --> P[外网地址替换为内网]
    P --> Q[下载临时 PDF 文件]
    Q --> R[上传 S3]
    R --> S[清理临时文件]
    S --> T[持久化 ContractMaterialPdfData 快照]
    T --> U[返回新 PDF URL]

    C -->|是| L
```

### 转换与聚合的详细数据流转

```mermaid
graph LR
    subgraph 远程数据路径
        A1[ComboSkuGroupDTO] -->|遍历 skuList| A2[按 categoryLevel3Code + brandCode 去重]
        A2 --> A3[ComboSkuVO 列表]
        A3 -->|按 categoryLevel3Code 分组| A4[过滤品牌=其他]
        A4 -->|品牌去重排序拼接| A5[MaterialPdfItemVO 列表]
    end

    subgraph 数据库数据路径
        B1[ContractMaterialPdfData 列表] -->|字段映射| B2[ComboSkuVO 列表]
        B2 -->|按 categoryLevel3Code 分组| B3[过滤品牌=其他]
        B3 -->|品牌去重排序拼接| B4[MaterialPdfItemVO 列表]
    end

    A5 --> C[比较键集合 Set]
    B4 --> C
    C --> D[一致性判定]
```

---

## 依赖关系

### 内部依赖

| 依赖方向 | 源组件 | 目标组件 | 接口/方法 |
|----------|--------|----------|-----------|
| 上游调用 | `MaterialPdfGenerator` | `MaterialPdfDiffService` | `isConsistent()`, `convertFromSkuGroup()` |
| 上游调用 | `MaterialPdfGenerator` | `MaterialPdfUtil` | `doGeneral()` |
| 更上游 | `ComboInfoMaterialGenerator` | `MaterialPdfGenerator` | `generateMaterialPdf()`, `noNeedGenerateMaterialPdf()` |
| PDF 上下文 | [ContractPdfSelfCreate](ContractPdfSelfCreate.md) 策略 | `MaterialPdfGenerator` | `getMaterialPdf()` |

### 外部依赖

| 依赖服务 | 注入位置 | 用途 |
|----------|----------|------|
| `HtmlRenderUtil` | `MaterialPdfUtil` | FreeMarker/Thymeleaf 模板渲染为 HTML |
| `PdfUtils` | `MaterialPdfUtil` | HTML 转 PDF 文件并上传临时 S3 |
| `S3Service` | `MaterialPdfUtil` | 最终 PDF 公网 S3 上传 |
| `ContractPdfFileHandleService` | `MaterialPdfUtil` | 临时文件下载与清理 |
| `AtomForPdfRpc` | `MaterialPdfUtil` | 远程 PDF 服务 RPC（已注入，当前 `doGeneral` 未直接调用） |

### 数据依赖

| 数据源 | 模型 | 提供方 |
|--------|------|--------|
| SCM 材料选品服务 | `ComboSkuGroupDTO` / `ComboSkuDTO` | 远程 RPC |
| 合同材料 PDF 数据表 | `ContractMaterialPdfData` | `ContractMaterialPdfDataRepository` |

---

## 关键设计模式

### 1. 统一中间模型（Canonical Intermediate Model）

`ComboSkuVO` 作为统一的中间表示，消除了远程 DTO（`ComboSkuDTO`）和数据库实体（`ContractMaterialPdfData`）之间的结构差异。两条数据路径各自独立转换为 `ComboSkuVO` 后，下游比较逻辑无需感知数据来源。

```
ComboSkuGroupDTO ──→ ComboSkuVO ←── ContractMaterialPdfData
```

### 2. 聚合-比较两阶段处理

差异比对不是简单的字段级比较，而是经历了**聚合**（分组、过滤、拼接、排序）后才进行比较。这确保了比对结果反映的是"最终 PDF 内容"层面的一致性，而非原始 SKU 数据层面的一致性。

### 3. Set 比较替代 List 比较

通过 `Set<String>.equals()` 实现无序比较，避免了因数据返回顺序不同导致的误判。比较键格式 `categoryLevel3Name|brandNames` 确保了足够的区分度。

### 4. 幂等 PDF 生成

通过 `isConsistent()` 的差异检查，`MaterialPdfGenerator` 可以避免不必要的重复 PDF 生成，节省计算资源和 S3 存储成本。只有当远程数据与快照不一致时才触发重新生成。

### 5. 内外网地址自适应

`MaterialPdfUtil.hostReplacement()` 确保在服务端环境（内网）中始终使用内网地址下载 PDF 中间文件，避免外网带宽瓶颈。

---

## 注意事项与扩展建议

| 项目 | 说明 |
|------|------|
| **临时工具类定位** | `MaterialPdfUtil` 源码注释标注为"临时先放这里，后续统一管理维护到合理的地方"，后续应迁移至统一的 PDF 工具层 |
| **AtomForPdfRpc 未使用** | `AtomForPdfRpc` 已注入但当前 `doGeneral` 方法未直接调用，可能是历史遗留或预留扩展 |
| **宿主替换硬编码** | 内外网地址以 `static final` 常量硬编码，建议迁移至配置中心或 Nacos 配置 |
| **去重逻辑仅基于远程数据** | `convertFromSkuGroup` 对远程数据执行 `(categoryLevel3Code + brandCode)` 去重，而 `convertFromDbData` 不去重——依赖数据库侧保证无重复 |
| **"其他"品牌过滤** | 硬编码过滤 `brandName == "其他"`，如业务规则变化需修改代码 |