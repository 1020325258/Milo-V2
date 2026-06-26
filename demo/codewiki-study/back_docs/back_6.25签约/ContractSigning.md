# ContractSigning 模块文档

## 1. 模块概述

ContractSigning 是合同系统中负责**合同签署流程**的核心模块，涵盖从签署前的视频观看与人脸认证、对公签约授权协议生成、PDF 盖章，到个性化合同关联关系管理、多主体报价签约源路由等完整签署链路。该模块作为 ContractSubmission（合同提交）的下游，在合同提交成功后通过事件驱动机制被触发，负责执行实际的签署操作。

### 核心职责

| 职责 | 关键服务 | 说明 |
|------|---------|------|
| 签署视频管理 | `ContractVideoService` | 签约前视频观看状态判定、视频跳转链接获取、观看记录提交 |
| 人脸身份认证 | `FaceAuthService` | 签署前活体人脸认证，校验签署人身份真实性 |
| 协议平台集成 | `FreeformService` | 对接第三方 Freeform 协议平台，统一处理实例创建、表单提交、PDF 生成、盖章、签署 |
| 对公签约授权 | `ContractCompanySignService` | 对公线上签约场景下自动生成授权协议书，管理法人授权流程 |
| 自主盖章 | `ContractSelfSealService` | 支持业务人员自主上传文件并盖电子章，异步处理盖章任务 |
| 正签合同重签 | `FormalReSignService` | 处理 2.0→2.5 订单模式迁移场景下正签合同的重签逻辑 |
| 多主体报价管理 | `FormalMultipleCompanyService` | 正签发起时管理多分公司 C 报价与协同报价的选择 |
| 个性化合同关联 | `PersonalRelationHandler` | 处理个性化合同与报价单/S 单的绑定关系撤回与解绑 |
| 签约源路由 | `ContractSigningSourceRouter` | 策略路由，按绑定类型（报价单/子订单/变更单）分发签约数据构建逻辑 |

---

## 2. 模块架构

### 2.1 整体架构图

```mermaid
graph TD
    subgraph Controllers[接口层]
        MPC[MpContractController]
        HCC[HomeContractController]
        CSC[ContractSelfSealController]
        CTC[ContractToolController]
    end

    subgraph ContractSigning[ContractSigning 模块]
        CVS[ContractVideoService]
        FAS[FaceAuthService]
        FFS[FreeformService]
        CCS[ContractCompanySignService]
        CSS[ContractSelfSealService]
        FRS[FormalReSignService]
        FMCS[FormalMultipleCompanyService]
        PRH[PersonalRelationHandlerImpl]
        CSRR[ContractSigningSourceRouter]
    end

    subgraph ExternalSystems[外部系统]
        FREEFORM[Freeform 协议平台]
        AUTH[统一认证平台]
        KAFKA[Kafka 事件总线]
        REDIS[Redis]
        S3[S3 存储]
    end

    MPC --> CVS
    MPC --> CCS
    MPC --> FFS
    HCC --> FMCS
    HCC --> CSRR
    CSC --> CSS
    CTC --> FRS

    CVS --> REDIS
    FAS --> AUTH
    FAS --> REDIS
    FFS --> FREEFORM
    CCS --> KAFKA
    CSS --> FFS
    CSS --> S3
    PRH --> KAFKA
    CSRR --> FMCS
```

### 2.2 模块间依赖关系

```mermaid
graph LR
    subgraph ContractSigning[ContractSigning]
        CVS[ContractVideoService]
        FAS[FaceAuthService]
        FFS[FreeformService]
        CCS[ContractCompanySignService]
        CSS[ContractSelfSealService]
        FRS[FormalReSignService]
        FMCS[FormalMultipleCompanyService]
        PRH[PersonalRelationHandlerImpl]
    end

    subgraph ContractCore[ContractCore]
        CUS[ContractUnifyService]
        CBS[ContractBusinessService]
        CCS2[CommonContractService]
    end

    subgraph ContractSubmission[ContractSubmission]
        CSBS[ContractSubmitService]
    end

    subgraph ContractPresentation[ContractPresentation]
        HCS[HomeContractService]
        PCS[PcContractService]
    end

    subgraph ContractEvents[ContractEvents]
        CSL[ContractSubmitListener]
        SAAF[SendMessageAfterAccreditFinish]
        CPCSL[CancelPersonalContractListener]
        CBSTSL[ChangeBillSubmitListener]
    end

    subgraph ContractConfig[ContractConfig]
        CAC[ContractApolloConfig]
    end

    CBS --> FAS
    CBS --> FFS
    CSBS --> FRS
    CUS --> FRS
    CUS --> FMCS
    CUS --> CCS
    HCS --> FRS
    HCS --> FMCS
    PCS --> FRS
    CSL --> CCS
    SAAF --> CCS
    CPCSL --> PRH
    CBSTSL --> PRH
    CVS --> CAC
    FAS --> CAC
    CCS --> CAC
    FRS --> CUS
```

---

## 3. 核心组件详解

### 3.1 FreeformService — 协议平台集成层

`FreeformService` 是整个 ContractSigning 模块中被引用最广泛的服务（13+ 个服务依赖），作为系统与第三方 Freeform 协议平台之间的统一集成层，封装了所有平台交互操作。

#### 功能矩阵

| 功能分类 | 方法 | 说明 |
|---------|------|------|
| **实例管理** | `createInstance` | 创建协议平台表单实例 |
| | `submit` | 提交表单数据至协议平台 |
| | `uploadPdfForInstance` | 按实例 ID 上传 PDF |
| **PDF 生成** | `createPdf` | 根据实例和表单生成合同 PDF，支持水印 |
| **盖章操作** | `companySeal` / `multiCompanySeal` | 同步盖公司章（单主体/多主体） |
| | `companySealAsync` / `multiCompanySealAsync` | 异步盖公司章 |
| | `queryContractSealResult` | 查询异步盖章结果 |
| **签署操作** | `getSignUrl` | 获取用户手签 URL |
| | `getContractSignResult` / `getBatchContractSignResult` | 查询个人手签结果（单个/批量） |
| | `getCompanyContractSignResult` | 查询公对公手签结果 |
| | `getBathSignUrl` | 批量获取手签链接（通过合同目录） |
| **授权操作** | `getCompanySignUrl` | 获取公司授权链接 |
| | `getCompanyAccreditResult` | 查询公司授权结果 |
| | `checkCompanyRegister` | 校验分公司是否注册 |
| **目录管理** | `createContractCatalog` / `addContractToCatalog` | 创建和管理合同目录 |
| **元数据查询** | `queryCustomForm` | 查询协议版式信息 |
| | `queryNewSealConfigs` | 查询签章规则 |
| | `getFormKeyByInstanceId` / `getFormIdByInstanceId` | 通过实例查询板式信息 |
| **企业实名** | `getCompanyRealNameInfo` / `getCompanyRealNameInfoWithCache` | 获取企业实名认证信息 |
| | `getCompanyAuthenticationRes` | 获取企业实名认证结果 |

#### 签章类型

```mermaid
graph TD
    subgraph SealTypes[签章类型]
        COMPANY[公司章 - COMPANY]
        PERSON[个人章 - PERSON]
        FINANCE[财务章 - FINANCE]
    end

    subgraph Operations[操作方式]
        SYNC[同步盖章 - contractSealV2]
        ASYNC[异步盖章 - contractSealV3Async]
    end

    COMPANY --> SYNC
    COMPANY --> ASYNC
    PERSON --> SYNC
    FINANCE --> SYNC
```

---

### 3.2 ContractVideoService — 签约视频管理

负责管理合同签署前的视频观看流程，确保用户在签署前完成必要的视频观看环节。

#### 视频观看判定逻辑

```mermaid
flowchart TD
    Start[开始判定] --> CheckNeed{需要观看视频?}
    CheckNeed -->|整装 + 正签/首期款| NeedWatch[需要观看]
    CheckNeed -->|团装 2.5 + 正签/销售| NeedWatch
    CheckNeed -->|其他类型| NoNeed[不需要观看]

    NeedWatch --> CheckSkip{是否可跳过?}
    CheckSkip -->|团装 2.5| GroupSkip[按合同类型+城市配置]
    CheckSkip -->|整装| HouseSkip[默认可跳过, 不跳过城市列表除外]

    GroupSkip --> WatchStatus{检查观看状态}
    HouseSkip --> WatchStatus

    WatchStatus --> CheckLog{查询合同日志}
    CheckLog -->|存在相同视频URL的观看记录| Finished[已观看]
    CheckLog -->|无匹配记录| NotFinished[未观看]
```

#### 核心方法说明

| 方法 | 功能 |
|------|------|
| `getContractVideo` | 获取视频初始化信息，包含视频链接、观看状态、是否可跳过、签约跳转 Schema |
| `needWatchVideo` | 根据业务类型+合同类型判定是否需要观看视频 |
| `getWatchStatusNew` | 按视频链接维度（而非项目维度）判定观看状态，支持不同合同类型不同视频 |
| `getCanSkipWatch` | 按城市和合同类型配置判定是否允许跳过视频 |
| `submitVideo` | 提交视频观看完成记录到 ContractLog 表 |
| `getVideoSkipUrlNew` | 多级配置获取视频跳转地址：城市维度 > 通用维度 |

#### 观看状态判定改进（V2）

V1 版本按**项目维度**判定观看状态——同一项目下任一合同看过视频即视为完成。V2（`getWatchStatusNew`）改为按**视频链接维度**判定——不同合同类型可能配置不同视频 URL，只有当前合同对应的视频 URL 有观看记录才视为完成。

---

### 3.3 FaceAuthService — 人脸身份认证

在签署前为用户提供人脸活体认证，增强签署安全性。仅被 `ContractBusinessService` 调用。

#### 认证流程

```mermaid
sequenceDiagram
    participant User as 用户端
    participant CBS as ContractBusinessService
    participant FAS as FaceAuthService
    participant AUTH as 统一认证平台
    participant REDIS as Redis

    User->>CBS: 请求签署
    CBS->>FAS: canUseFaceAuth(contractCodeList, signer)
    FAS-->>CBS: true/false

    alt 需要人脸认证
        CBS->>FAS: getFaceAuthUrl(contractCode, name, certNo, phone, returnUrl)
        FAS->>FAS: 解密证件号和手机号
        FAS->>FAS: 三密加密(AuthDESTools)
        FAS->>AUTH: authPrepare(FaceAuthPrepareParam)
        AUTH-->>FAS: bizFlowNo + unifiedAuth URL
        FAS->>REDIS: saveFaceAuthBizFlowNo(contractCode, bizFlowNo)
        FAS-->>CBS: 人脸认证URL
        CBS-->>User: 返回认证URL
        User->>AUTH: 完成人脸认证

        User->>CBS: 查询认证结果
        CBS->>FAS: getAuthResult(contractCode)
        FAS->>REDIS: getFaceAuthBizFlowNo(contractCode)
        FAS->>AUTH: authQuery(bizCode, bizFlowNo)
        AUTH-->>FAS: status=30(成功) / 其他
        FAS-->>CBS: true/false
    end
```

#### 适用条件

人脸认证需同时满足以下所有条件：

| 条件 | 说明 |
|------|------|
| 非白名单项目 | `projectOrderId` 不在 `faceAuthWhiteLists` 中 |
| 整装业务 | `businessType` 为 HOUSE_CERTIFICATE |
| 2.5 流程 | `processV25` 为 true |
| 身份证 | `certificateType` 为 ID_CARD |
| 正式签署 | `userSignType` 为 SIGN |
| 开城城市 | `gbCode` 在 `faceAuthOpenCity` 列表中 |
| 支持合同类型 | `contractType` 在 `faceAuthContractTypes` 列表中 |

---

### 3.4 ContractCompanySignService — 对公签约授权

处理对公线上签约场景下的授权协议书自动生成和管理。核心逻辑是在主合同提交后，为对公（公司）签约场景自动生成授权协议书供法人签署。

#### 授权协议书生成流程

```mermaid
flowchart TD
    CSLE[ContractSubmitListener 收到提交事件] --> CheckNeed{需要生成授权协议?}
    CheckNeed -->|非线上签约| Skip[跳过]
    CheckNeed -->|非对公签约| Skip
    CheckNeed -->|协同发起| Skip
    CheckNeed -->|无协议变更| Skip
    CheckNeed -->|需要生成| CheckReuse{能否复用已有授权协议?}

    CheckReuse -->|法人+代理人+分公司均相同| Reuse[复用已有授权协议]
    CheckReuse -->|不满足复用条件| CreateNew[生成新授权协议书]

    Reuse --> LinkContract[主合同关联授权协议]
    CreateNew --> BuildReq[构建授权协议请求参数]
    BuildReq --> Submit[通过 ContractSubmitService 提交]
    Submit --> LinkContract
    LinkContract --> SendSMS[发送短信通知法人]
```

#### 授权协议复用条件

`getExistCanRelatedAcreditContract` 方法判定是否可复用已有授权协议，需同时满足：

1. 主合同与授权协议的**乙方分公司**（companyCode）相同
2. 主合同与授权协议的**甲方分公司**（companyCreditCode）相同
3. **法人证件号**相同
4. **代理人证件号**相同（或均无代理人）

---

### 3.5 ContractSelfSealService — 自主盖章服务

支持业务人员在 PC 端自主上传文件（PDF 或图片），由系统自动盖电子章后返回盖章文件。

#### 盖章流程

```mermaid
sequenceDiagram
    participant User as 业务人员
    participant Controller as ContractSelfSealController
    participant Service as ContractSelfSealService
    participant FFS as FreeformService
    participant PDF as PdfToImageService
    participant S3 as S3存储

    User->>Controller: POST /api/contract/selfSeal/submit
    Controller->>Service: submitSelfSeal(SelfSealSubmitDTO)
    Service->>Service: checkSubmitInfo 校验

    loop 每个盖章任务
        Service->>Service: buildSelfSealTask 构建任务
        Service->>Service: insertBatch 批量入库

        par 异步处理每个任务
            alt PDF文件
                Service->>PDF: pdf2ImagePublicParallel 转图片
            else 图片文件
                Service->>Service: 直接使用图片URL
            end
            Service->>Service: buildFromData 构建合同参数
            Service->>FFS: createInstance 创建协议实例
            Service->>FFS: submit 提交表单
            Service->>FFS: createPdf 生成PDF
            Service->>FFS: companySeal 盖公司章
            Service->>S3: upload 上传盖章文件
            Service->>Service: 更新状态为盖章成功
        end
    end
```

---

### 3.6 FormalReSignService — 正签合同重签

处理 2.0→2.5 订单模式迁移场景下正签合同的重签信息获取与判断。

#### 场景说明

当项目从 2.0 订单模式刷数为 2.5 模式后，原有的 2.0 正签合同需要特殊处理：

```mermaid
flowchart TD
    Start[查询项目正签合同] --> HasHistorical{存在已完结的 2.0 正签合同?}

    HasHistorical -->|否| Normal[正常流程]
    HasHistorical -->|是| Cancelled{2.0 合同已作废?}

    Cancelled -->|是| NewLaunch{2.5 合同已发起?}
    NewLaunch -->|否| ShowCreate[展示创建新合同入口]
    NewLaunch -->|是| ShowCurrent[展示当前 2.5 合同]

    Cancelled -->|否| HaveFinish[有已完成的 2.0 合同]
    HaveFinish --> ShowOld[展示旧合同链接 + 创建新合同入口]
    ShowOld --> CanCreate[允许创建 2.5 正签合同]
```

#### 核心判断方法

| 方法 | 功能 |
|------|------|
| `haveHistoricalContract` | 判断是否存在刷数前发起的 2.0 正签合同（通过比较刷数时间和合同发起节点时间） |
| `isCancelHistoricalContract` | 判断历史正签合同是否已被作废 |
| `newContractLaunch` | 判断 2.5 模式下新合同是否已发起（发起时间在刷数之后） |
| `formalContractUnique` | 正签合同唯一性校验，防止重复创建 |
| `historicalContractLink` | 获取历史正签合同的详情链接 |

---

### 3.7 FormalMultipleCompanyService — 多主体报价管理

正签发起时，管理多分公司 C 报价与协同报价的选择逻辑。

#### 报价数据来源

```mermaid
graph TD
    subgraph DataSources[报价数据来源]
        FORMAL[正签 C 报价]
        COOPER[协同报价单]
        SUBORDER[S 单据]
    end

    subgraph Processing[处理逻辑]
        ROUTER[ContractSigningSourceRouter]
        BILL[BillSigningSourceStrategy]
        SUB[SubOrderSigningSourceStrategy]
        CHANGE[ChangeOrderSigningSourceStrategy]
    end

    FORMAL --> ROUTER
    COOPER --> ROUTER
    SUBORDER --> ROUTER

    ROUTER -->|BINDTYPE_BILL_CODE| BILL
    ROUTER -->|BINDTYPE_SUB_ORDER| SUB
    ROUTER -->|BINDTYPE_CHANGE_ORDER| CHANGE

    BILL --> GROUP[SignableOrderInfoGroup.buildGroup]
    SUB --> GROUP
    CHANGE --> GROUP
```

#### V2 签约源路由（`ContractSigningSourceRouter`）

采用策略模式，按绑定类型路由到不同的签约源策略：

| 策略 | 绑定类型 | 数据来源 |
|------|---------|---------|
| `BillSigningSourceStrategy` | 报价单号 (BILL_CODE) | 从报价系统获取可签约的 C 报价单 |
| `SubOrderSigningSourceStrategy` | 子订单号 (SUB_ORDER) | 从订单中心获取可签约的 S 单 |
| `ChangeOrderSigningSourceStrategy` | 变更单号 (CHANGE_ORDER) | 从变更系统获取可签约的变更单 |

每个策略统一实现 `ContractSigningSource` 接口，提供 `buildSignableOrderInfos`、`checkPersonalCanCreate`、`buildGoodsInfo` 等方法。

---

### 3.8 PersonalRelationHandler — 个性化合同关联关系处理

处理个性化合同与报价单/S 单的绑定关系撤回操作，由 Kafka 事件驱动。

#### 撤回流程

```mermaid
flowchart TD
    Event[Kafka 事件: 报价单撤回/变更单提交] --> Lock[获取分布式锁]
    Lock --> CheckDirect{报价单直接关联合同?}

    CheckDirect -->|是| DirectBound[直接绑定处理]
    CheckDirect -->|否| ViaSubOrder[通过 S 单处理]

    DirectBound --> OnlyBound{仅绑定该报价单?}
    OnlyBound -->|是| Cancel[作废合同]
    OnlyBound -->|否| UnbindUndo[解除关联 + 撤回合同]

    ViaSubOrder --> FindSubOrders[查找报价单对应 S 单]
    FindSubOrders --> CheckSubBound{S 单关联合同?}
    CheckSubBound -->|否| Skip[跳过]
    CheckSubBound -->|是| SubBoundCheck{S 单是否为合同唯一绑定?}
    SubBoundCheck -->|是| Cancel
    SubBoundCheck -->|否| UnbindUndo

    Cancel --> CleanDraft[清理正签草稿字段]
    UnbindUndo --> RecordLog[记录解绑日志]
    RecordLog --> UndoContract[回退合同到草稿]
    UndoContract --> CleanDraft
```

#### 操作类型枚举

| 操作 | 说明 |
|------|------|
| `CANCEL_CONTRACT` | 作废合同（合同仅绑定被撤回的单据） |
| `UNBIND_AND_UNDO` | 解除关联并撤回合同（合同还绑定了其他单据） |
| `SKIP` | 跳过处理（合同处于无效/终态） |

---

### 3.9 JiaFangAgentSupportConfig / SupportWatchVideoConfig — 配置 DTO

| 配置类 | 用途 |
|--------|------|
| `JiaFangAgentSupportConfig` | 甲方代理人签章配置：控制支持城市、合同类型、业务类型、白名单项目（始终走旧逻辑使用甲方签章） |
| `SupportWatchVideoConfig` | 签约视频开关配置：按业务类型+城市维度控制视频功能是否开启 |

---

## 4. 事件驱动交互

ContractSigning 模块与 ContractEvents 模块深度集成，通过 Kafka 事件实现异步解耦。

### 4.1 事件交互时序图

```mermaid
sequenceDiagram
    participant User as 用户端
    participant HomeContract as HomeContractController
    participant Submit as ContractSubmitService
    participant Producer as ContractEventProducer
    participant Kafka as Kafka
    participant SubmitListener as ContractSubmitListener
    participant CompanySign as ContractCompanySignService
    participant AccreditListener as SendMessageAfterAccreditFinish
    participant Business as ContractBusinessService
    participant Freeform as FreeformService

    User->>HomeContract: 提交合同
    HomeContract->>Submit: submit(contractReq)
    Submit->>Submit: 构建合同数据 + 保存草稿
    Submit->>Submit: submitLaunch 批量发起
    Submit->>Producer: 发送 CONTRACT_SUBMIT 事件
    Producer->>Kafka: 发送消息

    Kafka->>SubmitListener: 消费 CONTRACT_SUBMIT
    SubmitListener->>CompanySign: generateAccreditContract(contract)
    CompanySign->>CompanySign: 判断是否需要授权协议
    CompanySign->>Submit: 生成授权协议书(递归提交)
    CompanySign->>CompanySign: 关联主合同与授权协议
    CompanySign->>User: 短信通知法人

    Note over User: 法人完成授权协议签署

    Kafka->>AccreditListener: 消费 CONTRACT_FINISH(ACCREDIT)
    AccreditListener->>CompanySign: getBusinessSnapshotDTO
    AccreditListener->>User: 短信通知签约人

    Note over User: 签约人进入签署流程

    User->>Business: 请求签署信息
    Business->>Freeform: 获取签署URL/查询签署结果
    Freeform-->>Business: 返回签署结果
    Business-->>User: 返回签署结果
```

### 4.2 关键事件监听器

| 监听器 | 监听事件 | 行为 |
|--------|---------|------|
| `ContractSubmitListener` | CONTRACT_SUBMIT | 触发授权协议生成（`generateAccreditContract`）、取消历史个性化合同关联 |
| `SendMessageAfterAccreditFinish` | CONTRACT_FINISH (ACCREDIT) | 授权协议签署完成后发送短信通知签约人 |
| `CancelPersonalContractListener` | 合同取消事件 | 调用 `PersonalRelationHandler.revokeCooperQuotation` 解绑关联关系 |
| `ChangeBillSubmitListener` | 变更单提交事件 | 调用 `PersonalRelationHandler.revokeCooperQuotation` 处理变更场景关联 |
| `BillToSubOrderListener` | 报价单换绑事件 | 处理报价单与 S 单的合同关联换绑 |

---

## 5. 数据流

### 5.1 签署前数据准备流

```mermaid
graph LR
    subgraph Input[输入数据]
        PO[ProjectOrderId]
        CC[ContractCode]
        USER[用户信息]
    end

    subgraph SigningPrep[签署前准备]
        VIDEO[视频状态检查]
        FACE[人脸认证检查]
        ACCREDIT[授权协议检查]
    end

    subgraph Output[输出]
        SIGN_URL[签署URL]
        AUTH_URL[认证URL]
        VIDEO_INFO[视频信息]
        AUTH_STATUS[授权状态]
    end

    PO --> VIDEO
    PO --> ACCREDIT
    CC --> FACE
    USER --> FACE

    VIDEO --> VIDEO_INFO
    FACE --> AUTH_URL
    FACE --> AUTH_STATUS
    ACCREDIT --> SIGN_URL
```

### 5.2 PDF 盖章数据流

```mermaid
graph TD
    subgraph FreeformPlatform[Freeform 协议平台操作]
        CREATE[createInstance - 创建实例]
        SUBMIT[submit - 提交表单数据]
        PDF[createPdf - 生成PDF]
        SEAL[companySeal - 盖公司章]
        UPLOAD[uploadPdfForInstance - 上传PDF]
    end

    FORM_DATA[表单字段数据] --> CREATE
    CREATE --> SUBMIT
    CONTRACT_NO[合同编号] --> SUBMIT
    SUBMIT --> PDF
    WATERMARK[水印配置] --> PDF
    PDF --> SEAL
    COMPANY_CODE[公司信用编码] --> SEAL
    SEAL --> RESULT[盖章后PDF链接]

    UPLOAD --> PDF
```

---

## 6. 关键设计模式

### 6.1 策略模式

模块中大量使用策略模式实现可扩展的业务逻辑分发：

```mermaid
classDiagram
    class ContractSigningSource {
        <<interface>>
        +bindType()
        +queryPersonalQuoteInfo()
        +buildSignableOrderInfos()
        +checkPersonalCanCreate()
        +buildGoodsInfo()
    }

    class AbstractContractSigningSource {
        <<abstract>>
        +queryPersonalQuoteInfo()
        +buildPersonalDrawingImgList()
        +filterByCompanyCode()
    }

    class BillSigningSourceStrategy {
        +bindType() BILL_CODE
        +buildSignableOrderInfos()
        +getSkuProductsByBillCode()
    }

    class SubOrderSigningSourceStrategy {
        +bindType() SUB_ORDER
        +buildSignableOrderInfos()
        +getSignableSubOrderNos()
    }

    class ChangeOrderSigningSourceStrategy {
        +bindType() CHANGE_ORDER
        +buildSignableOrderInfos()
        +getSkuProductsByChangeOrderId()
    }

    class ContractSigningSourceRouter {
        +route(bindType) ContractSigningSource
    }

    ContractSigningSource <|.. AbstractContractSigningSource
    AbstractContractSigningSource <|-- BillSigningSourceStrategy
    AbstractContractSigningSource <|-- SubOrderSigningSourceStrategy
    AbstractContractSigningSource <|-- ChangeOrderSigningSourceStrategy
    ContractSigningSourceRouter --> ContractSigningSource
```

### 6.2 事件驱动模式

模块通过 Kafka 事件实现与其他模块的解耦：

- **发布者**：`ContractSubmitService` 在合同提交成功后发布 `CONTRACT_SUBMIT` 事件
- **消费者**：`ContractSubmitListener` 消费事件后调用 `ContractCompanySignService` 生成授权协议
- **效果**：合同提交与授权协议生成异步解耦，提交不阻塞

### 6.3 模板方法模式

`PersonalRelationHandlerImpl` 中的撤回流程采用类似模板方法的结构：

1. **加锁** → 2. **判断绑定类型** → 3. **确定操作类型** → 4. **执行撤回** → 5. **清理字段**

`executeRevocationAction` 根据 `ContractRevocationAction` 枚举分发到不同的具体操作（作废/解绑撤回/跳过）。

### 6.4 配置驱动模式

通过 Apollo 配置中心（`ContractApolloConfig`）实现业务规则的动态配置：

| 配置项 | 影响范围 |
|--------|---------|
| 视频跳转地址 | `ContractVideoService` 按城市+业务类型+合同类型+小程序类型+开渠维度配置 |
| 人脸认证开城 | `FaceAuthService` 按城市和合同类型控制认证功能 |
| 自主盖章分公司 | `ContractSelfSealService` 按系统号和分公司控制权限 |
| 甲方代理人配置 | `JiaFangAgentSupportConfig` 按城市和项目控制签章类型 |

---

## 7. API 端点汇总

### 7.1 小程序端（MpContractController）

| 端点 | 方法 | 说明 |
|------|------|------|
| `/mp/contract/video/query` | GET | 获取合同视频初始化信息 |
| `/mp/contract/video/submit` | GET | 提交视频观看完成 |
| `/mp/contract/contractAuthList/v2` | GET | 获取授权协议列表（C 端） |
| `/mp/contract/getContractAuthInfo` | GET | 获取授权协议详情 |
| `/mp/contract/canSign/V2` | GET | 检查合同是否可签署 |
| `/mp/contract/signLocationReport` | POST | 上报签署位置信息 |

### 7.2 自主盖章端（ContractSelfSealController）

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/contract/selfSeal/companyInfos` | GET | 获取可盖章分公司列表 |
| `/api/contract/selfSeal/submit` | POST | 提交自主盖章请求 |
| `/api/contract/selfSeal/getList` | GET | 查询盖章任务列表（分页） |
| `/api/contract/selfSeal/reSeal` | GET | 重新触发盖章 |

---

## 8. 关联模块文档

| 模块 | 关系 | 说明 |
|------|------|------|
| [ContractCore](ContractCore.md) | 上游 | 提供合同基础数据模型（Contract、ContractUser、ContractField 等）和核心服务（CommonContractService、ContractBusinessService、ContractUnifyService） |
| [ContractSubmission](ContractSubmission.md) | 上游 | 合同提交模块，提交成功后通过 Kafka 事件触发本模块的授权协议生成 |
| [ContractPresentation](ContractPresentation.md) | 调用方 | HomeContractService 和 PcContractService 调用本模块的 FormalReSignService 和 FormalMultipleCompanyService |
| [ContractEvents](ContractEvents.md) | 事件总线 | 提供 Kafka 事件监听器，驱动本模块的异步流程 |
| [ContractConfig](ContractConfig.md) | 配置源 | ContractApolloConfig 提供视频、人脸认证、盖章等配置 |
| [ContractPdf](ContractPdf.md) | PDF 生成 | 与本模块的 FreeformService 协作完成 PDF 生成和盖章 |
