# ContractSigning 模块文档

## 模块概述

ContractSigning 是合同系统（ContractCore）的签约执行子模块，负责合同签约阶段的核心业务操作。该模块包含两个核心服务：

- **ContractCompanySignService**：对公签约服务，处理企业对公线上签约场景下的授权协议书生成、授权列表查询、签约信息获取等业务逻辑。
- **ContractSelfSealService**：自主盖章服务，支持内部运营人员上传 PDF 或图片文件，通过 Freeform 平台生成合同 PDF 并加盖电子印章。

该模块位于合同生命周期的中后段，承接 [ContractSubmission](ContractSubmission.md) 模块提交的合同数据，在合同进入待签署状态后，由签约服务驱动授权协议生成和电子签章流程。

---

## 系统架构

```mermaid
graph TD
    subgraph ContractCore[ContractCore 合同核心]
        ContractDetail[ContractDetail 合同详情]
        ContractValidation[ContractValidation 合同校验]
        ContractSubmission[ContractSubmission 合同提交]
        ContractSigning[ContractSigning 合同签约]
        ContractCreation[ContractCreation 合同创建]
    end

    subgraph ContractSigningMod[ContractSigning 模块]
        CompanySign[ContractCompanySignService<br/>对公签约服务]
        SelfSeal[ContractSelfSealService<br/>自主盖章服务]
    end

    subgraph AspectLayer[ContractAspect 切面层]
        ContextAspect[ContractContextAspect<br/>上下文初始化切面]
        ContextHandler[ContractContextHandler<br/>ThreadLocal 上下文持有]
    end

    subgraph PersonalBind[PersonalBinding 个性化绑定]
        SignSource[ContractSigningSource<br/>签约数据源策略接口]
        BillStrategy[BillSigningSourceStrategy]
        ChangeStrategy[ChangeOrderSigningSourceStrategy]
        SubStrategy[SubOrderSigningSourceStrategy]
    end

    subgraph ExternalDeps[外部依赖服务]
        FreeformService[FreeformService<br/>Freeform 电子签章平台]
        S3Service[S3Service<br/>文件存储]
        PdfToImage[PdfToImageService<br/>PDF转图片]
        PayServiceRpc[PayServiceRpc<br/>支付服务]
        UserFeign[UserFeignService<br/>用户服务]
    end

    ContractSubmission --> ContractSigning
    ContractSigning --> ContractDetail
    ContractCreation --> ContractSigning
    ContractValidation -.-> ContractSigning
    ContextAspect -.-> ContractSigning
    SignSource --> BillStrategy
    SignSource --> ChangeStrategy
    SignSource --> SubStrategy
    CompanySign --> UserFeign
    CompanySign --> PayServiceRpc
    SelfSeal --> FreeformService
    SelfSeal --> S3Service
    SelfSeal --> PdfToImage
```

---

## 核心组件详解

### ContractCompanySignService — 对公签约服务

对公签约服务处理企业客户的线上签约场景，核心职责包括**授权协议书生命周期管理**和**C 端授权列表查询**。

#### 职责划分

| 方法 | 职责 | 状态 |
|------|------|------|
| `generateAccreditContract` | 生成/复用授权协议书并关联合同 | @Deprecated |
| `getContractAuthList` | B 端授权协议列表查询 | @Deprecated |
| `getAccreditContractList` | C 端授权协议列表查询（当前主力接口） | 活跃 |
| `getContractAuthInfo` | 获取单个授权协议详情及签约链接 | 活跃 |
| `getBusinessSnapshotDTO` | 构建提醒业务快照 | 活跃 |

#### 授权协议书生成流程

```mermaid
flowchart TD
    Start[主合同进入待签署状态] --> Check{needGenerateAccreditContract?}
    Check -->|不需要| Return[直接返回]
    Check -->|需要| QueryExist[查询项目下已有授权协议]

    QueryExist --> MatchCheck{getExistCanRelatedAcreditContract?}
    MatchCheck -->|找到可复用的| Reuse[复用已有授权协议]
    MatchCheck -->|未找到| Create[buildContractSubmitReq<br/>构造请求参数]

    Create --> Submit[contractSubmitService.submit<br/>调用提交服务生成授权协议]
    Submit --> UpdateCompany[更新授权协议乙方主体]
    UpdateCompany --> Reuse

    Reuse --> StatusCheck{主合同是否仍在待签署?}
    StatusCheck -->|已撤回草稿| Skip[跳过关联]
    StatusCheck -->|正常| Relate[关联主合同与授权协议]

    Relate --> RelatedCheck{是否存在关联合同?}
    RelatedCheck -->|是| BatchRelate[批量关联所有关联合同]
    RelatedCheck -->|否| End[完成]

    BatchRelate --> End
```

#### 授权协议复用判断逻辑

`getExistCanRelatedAcreditContract` 方法通过四重匹配判断是否可复用已有授权协议：

```mermaid
flowchart TD
    Input[遍历项目下所有有效授权协议] --> C1{乙方分公司相同?}
    C1 -->|不同| Skip1[跳过，继续下一个]
    C1 -->|相同| C2{甲方分公司统一社会信用代码相同?}
    C2 -->|不同| Skip2[跳过]
    C2 -->|相同| C3{法人证件号相同?}
    C3 -->|不同| Skip3[跳过]
    C3 -->|相同| C4{代理人情况}
    C4 -->|双方都无代理人| Reuse[可复用]
    C4 -->|双方都有代理人且证件号相同| Reuse[可复用]
    C4 -->|其他| Skip4[跳过]
```

**匹配维度**：

| 维度 | 比较字段 | 说明 |
|------|---------|------|
| 乙方分公司 | `contract.companyCode` | 主合同与授权协议的销售公司编码 |
| 甲方分公司 | `companyCreditCode` 字段值 | 统一社会信用代码，去除空白后比较 |
| 法人 | `ContractUser.certificateNo`（RoleType=LEGAL） | 法人证件号 |
| 代理人 | `ContractUser.certificateNo`（RoleType=COMPANY_AGENT） | 代理人证件号，双方均无代理人也视为匹配 |

#### 生成条件判断

`needGenerateAccreditContract` 方法定义了生成授权协议的前置条件：

```mermaid
flowchart TD
    Start[输入 Contract] --> N1{contract != null?}
    N1 -->|否| False[返回 false]
    N1 -->|是| N2{签约渠道为线上?}
    N2 -->|否| False
    N2 -->|是| N3{合同类型需要授权协议?}
    N3 -->|否| False
    N3 -->|是| N4{非协同发起的 C 合同?}
    N4 -->|否| False
    N4 -->|是| N5{签约主体为企业?}
    N5 -->|否| False
    N5 -->|是| N6{非无协议变更?}
    N6 -->|否| False
    N6 -->|是| True[返回 true]
```

**需要生成授权协议的合同类型**：正签合同、个性化合同、首期款合同、变更合同、设计合同、设计变更合同（由 `ContractTypeEnum.needRelateAccreditContractTypes()` 定义）。

#### C 端授权列表查询

`getAccreditContractList` 方法为 C 端用户提供授权协议列表，查询路径：

```mermaid
sequenceDiagram
    participant Client as C 端客户端
    participant Service as ContractCompanySignService
    participant ProjectInfo as ProjectInfoReadService
    participant ContractSvc as ContractService
    participant UserSvc as ContractUserService
    participant Feign as UserFeignService
    participant Cipher as CipherService
    participant BtnConfig as ContractButtonConfigService

    Client->>Service: getAccreditContractList(projectOrderId, ucId)
    Service->>ProjectInfo: getByProjectOrderIdWithoutCache
    ProjectInfo-->>Service: ProjectInfoDTO
    Service->>ContractSvc: getContractList(type=ACCREDIT)
    ContractSvc-->>Service: accreditContractList
    Service->>Feign: getUserInfo(ucId)
    Feign-->>Service: CUserDTO
    Service->>Cipher: encrypt(phone)
    Cipher-->>Service: loginPhone
    Service->>UserSvc: getContractListBySignerPhone(loginPhone)
    UserSvc-->>Service: signUserList
    Note over Service: 过滤：accreditContract ∩ signUserList
    loop 每个可见授权协议
        Service->>ContractSvc: getCompanyCode
        Service->>Service: getAccreditFieldList(认证状态/授权状态)
        Service->>BtnConfig: getAccreditCustomerListButtonList
    end
    Service-->>Client: ContractAuthListResDTO
```

**权限过滤**：仅返回登录用户作为签署人的授权协议，确保数据隔离。

#### 授权信息详情

`getContractAuthInfo` 方法提供单个授权协议的完整信息，包含越权校验：

```mermaid
flowchart TD
    Input[contractCode] --> Validate{是否为授权协议?}
    Validate -->|否| Error1[抛出异常: 合同不存在]
    Validate -->|是| LoadProject[查询项目地址]
    LoadProject --> LoadMainContract[查询关联主合同]
    LoadMainContract --> LoadSigner[查询主合同签约人]
    LoadSigner --> AuthCheck{当前用户是否为<br/>授权协议签署人?}
    AuthCheck -->|否| Error2[抛出越权异常<br/>提示正确手机号]
    AuthCheck -->|是| Build[构建返回结果]
    Build --> Output[ContractAuthResDTO<br/>含 contractUrl/signUrl/isSignatory]
```

---

### ContractSelfSealService — 自主盖章服务

自主盖章服务为内部运营人员提供自定义文件（PDF/图片）的电子签章能力，支持批量盖章任务的异步处理。

#### 核心流程

```mermaid
flowchart TD
    Start[运营人员提交盖章请求] --> Validate[checkSubmitInfo<br/>校验提交信息]
    Validate --> Build[buildSelfSealTask<br/>构建盖章任务记录]

    Build --> FileType{文件类型?}
    FileType -->|PDF| PdfRecord[每个 PDF 文件<br/>创建一条 SelfSealRecord]
    FileType -->|IMAGE| ImgRecord[多张图片合并<br/>创建一条 SelfSealRecord]

    PdfRecord --> BatchInsert[insertBatch 批量入库]
    ImgRecord --> BatchInsert

    BatchInsert --> Async[异步处理盖章任务]
    Async --> SealLoop[dealSealTask 遍历任务]

    SealLoop --> Single[dealSingleSealTask]
    Single --> Convert{文件类型?}
    Convert -->|PDF| ToImage[pdf2ImagePublicParallel<br/>PDF 转图片]
    Convert -->|IMAGE| Direct[直接使用图片 URL]

    ToImage --> BuildForm[buildFromData<br/>构建 Freeform 表单数据]
    Direct --> BuildForm

    BuildForm --> GenPdf[generatePdf<br/>调用 Freeform 生成 PDF]
    GenPdf --> Seal[contractSeal<br/>调用 Freeform 盖章]
    Seal --> Upload[上传至 S3 存储]
    Upload --> Update[更新状态为 SEAL_SUCCESS]
```

#### 盖章任务构建逻辑

根据文件类型采用不同的记录构建策略：

| 文件类型 | 记录策略 | 文件命名 | 说明 |
|---------|---------|---------|------|
| PDF（`FileTypeEnum.PDF`） | 每个文件一条记录 | 原文件名 | 各 PDF 独立处理 |
| 图片（`FileTypeEnum.IMAGE`） | 多图合并为一条记录 | `yyyyMMdd_random.pdf` | 图片 URL 以逗号拼接存储 |

#### Freeform 集成流程

```mermaid
sequenceDiagram
    participant SelfSeal as ContractSelfSealService
    participant Apollo as ContractApolloConfig
    participant Freeform as FreeformService
    participant S3 as S3Service

    SelfSeal->>Apollo: getSelfSealFormInfo
    Apollo-->>SelfSeal: formKey + formId

    SelfSeal->>Freeform: createInstance(formKey, userId)
    Freeform-->>SelfSeal: instanceId

    SelfSeal->>Freeform: submit(instanceId, recordId, userId, formData)
    Note over Freeform: formData 包含图片 URL 列表<br/>最后一页标记 sign=true

    SelfSeal->>Freeform: createPdf(instanceId, userId, formId, formData)
    Freeform-->>SelfSeal: AttachmentInfo (pdfUrl)

    SelfSeal->>Freeform: companySeal(instanceId, sealCode, userId)
    Note over Freeform: sealCode 从 Apollo 配置<br/>按分公司匹配
    Freeform-->>SelfSeal: signedPdfUrl

    SelfSeal->>S3: upload(signedPdfUrl)
    S3-->>SelfSeal: fileKey
    Note over SelfSeal: 更新 SelfSealRecord<br/>previewKey = fileKey<br/>sealStatus = SEAL_SUCCESS
```

#### 盖章主体与权限

```mermaid
flowchart LR
    UserId[当前登录人 userId] --> SystemCode[ucIdToSystemCode<br/>转换为系统号]
    SystemCode --> Filter[从 Apollo 配置中<br/>过滤支持的分公司列表]
    Filter --> CompanyList[SelfSealCompanyInfoDTO 列表]

    CompanyList --> SubmitCheck[提交时校验:<br/>companyCode 在支持列表内]
    CompanyList --> ListFilter[列表查询时:<br/>按支持分公司过滤数据]
```

#### 错误处理与重试

- 每个盖章任务独立异步执行（`CompletableFuture.runAsync` + SkyWalking `RunnableWrapper`）
- 单个任务失败不影响其他任务，失败任务状态更新为 `SEAL_FAIL`
- `reSeal(Long id)` 方法支持对失败任务重新发起盖章

---

## 模块间依赖关系

```mermaid
graph LR
    subgraph ContractSigning
        CompanySign[ContractCompanySignService]
        SelfSeal[ContractSelfSealService]
    end

    subgraph CoreServices[核心依赖服务]
        ContractSvc[ContractService<br/>合同 CRUD]
        ContractUserSvc[ContractUserService<br/>签约人管理]
        ContractFieldSvc[ContractFieldService<br/>合同字段管理]
        ContractRelationSvc[ContractRelationService<br/>合同关联管理]
        ContractNodeSvc[ContractNodeService<br/>审批节点管理]
        ContractCompanyInfoSvc[ContractCompanyInfoService<br/>公司信息管理]
        ContractSubmitSvc[ContractSubmitService<br/>合同提交]
        ButtonConfigSvc[ContractButtonConfigService<br/>按钮配置]
    end

    subgraph CommonServices[公共服务]
        HomeAndPc[HomeAndPcCommonService<br/>Home/PC 公共逻辑]
        CityCompanyConfig[ContractCityCompanyConfigService<br/>城市公司配置]
        CipherSvc[CipherService<br/>加解密服务]
        ApolloConfigSvc[ApolloConfigService<br/>配置中心]
        CommonBiz[CommonBusinessService<br/>通用业务]
    end

    subgraph RPCServices[RPC 服务]
        UserFeign[UserFeignService<br/>用户 Feign]
        PayRpc[PayServiceRpc<br/>支付 RPC]
    end

    subgraph PdfServices[PDF/盖章服务]
        Freeform[FreeformService<br/>Freeform 平台]
        Pdf2Img[PdfToImageService<br/>PDF 转图片]
        S3[S3Service<br/>文件存储]
    end

    CompanySign --> ContractSvc
    CompanySign --> ContractUserSvc
    CompanySign --> ContractFieldSvc
    CompanySign --> ContractRelationSvc
    CompanySign --> ContractNodeSvc
    CompanySign --> ContractCompanyInfoSvc
    CompanySign --> ContractSubmitSvc
    CompanySign --> ButtonConfigSvc
    CompanySign --> HomeAndPc
    CompanySign --> CityCompanyConfig
    CompanySign --> CipherSvc
    CompanySign --> ApolloConfigSvc
    CompanySign --> CommonBiz
    CompanySign --> UserFeign
    CompanySign --> PayRpc

    SelfSeal --> Freeform
    SelfSeal --> Pdf2Img
    SelfSeal --> S3
```

**依赖特征对比**：

| 维度 | ContractCompanySignService | ContractSelfSealService |
|------|---------------------------|------------------------|
| 依赖服务数量 | 17 个 | 4 个 |
| 耦合程度 | 高，涉及合同全流程数据 | 低，专注文件处理 |
| 外部 RPC | UserFeignService, PayServiceRpc | 无 |
| 数据库交互 | Contract, ContractUser, ContractField, ContractRelation, ContractNode, ContractCompanyInfo | SelfSealRecord |
| 与合同状态流转关系 | 紧密耦合（读写合同状态） | 独立于合同生命周期 |

---

## 数据流

### 对公签约主流程数据流

```mermaid
flowchart TD
    subgraph Input[输入]
        MainContract[主合同<br/>Contract + ContractUser + ContractField]
        ProjectOrder[项目订单号]
        LoginUser[登录用户 ucId]
    end

    subgraph CompanySignProcess[对公签约处理]
        GenAccredit[生成授权协议书]
        AuthList[查询授权列表]
        AuthInfo[查询授权详情]
    end

    subgraph Output[输出]
        AccreditContract[授权协议书<br/>Contract type=ACCREDIT]
        AuthListDTO[ContractAuthListResDTO<br/>授权列表 + 按钮配置 + 字段信息]
        AuthInfoDTO[ContractAuthResDTO<br/>签约链接 + 认证状态]
        SnapshotDTO[BusinessSnapshotDTO<br/>提醒快照]
    end

    MainContract --> GenAccredit
    GenAccredit --> AccreditContract
    MainContract --> AuthList
    ProjectOrder --> AuthList
    LoginUser --> AuthList
    AuthList --> AuthListDTO

    ProjectOrder --> AuthInfo
    AuthInfo --> AuthInfoDTO
    MainContract --> SnapshotDTO
```

### 自主盖章数据流

```mermaid
flowchart TD
    subgraph Input[输入]
        SubmitDTO[SelfSealSubmitDTO<br/>分公司编码 + 文件列表 + 文件类型]
        UserId[登录用户 userId]
    end

    subgraph Processing[处理流程]
        Validate[权限校验<br/>按 systemCode 过滤分公司]
        BuildTask[构建 SelfSealRecord]
        PdfConvert[PDF 转图片<br/>或直接使用图片 URL]
        FormBuild[构建 Freeform 表单]
        CreatePdf[Freeform 生成 PDF]
        AddSeal[Freeform 盖章]
        UploadS3[上传 S3]
    end

    subgraph Storage[存储]
        DB[(SelfSealRecord 表)]
        S3File[(S3 文件)]
    end

    subgraph Output[输出]
        TaskList[盖章任务列表<br/>含预览 URL]
        SealResult[盖章结果<br/>SEAL_SUCCESS / SEAL_FAIL]
    end

    SubmitDTO --> Validate
    UserId --> Validate
    Validate --> BuildTask
    BuildTask --> DB
    BuildTask --> PdfConvert
    PdfConvert --> FormBuild
    FormBuild --> CreatePdf
    CreatePdf --> AddSeal
    AddSeal --> UploadS3
    UploadS3 --> S3File
    UploadS3 --> SealResult

    DB --> TaskList
    S3File --> TaskList
```

---

## 关键设计模式

### 1. 策略模式 — 授权协议复用判断

`getExistCanRelatedAcreditContract` 方法采用**链式匹配策略**，按优先级依次检查四个匹配维度，任一维度不匹配即跳过当前授权协议。这种设计将匹配规则解耦为独立的判断步骤，便于新增匹配维度。

### 2. 模板方法模式 — 单任务盖章处理

`dealSingleSealTask` 定义了盖章处理的固定流程骨架：

```
文件转换 → 表单构建 → PDF 生成 → 印章加盖 → 状态更新
```

各步骤通过私有方法实现，子类（如有）可覆写特定步骤。当前设计中未使用继承，而是通过方法内联实现。

### 3. 异步任务编排

ContractSelfSealService 使用 `CompletableFuture.runAsync` + SkyWalking `RunnableWrapper` 实现：
- **异步执行**：盖章任务不阻塞主请求
- **链路追踪**：RunnableWrapper 保证 SkyWalking Trace Context 传播
- **容错隔离**：单个任务失败通过 try-catch 更新状态为 `SEAL_FAIL`，不影响其他任务
- **手动重试**：`reSeal` 方法支持对失败任务重新执行

### 4. ThreadLocal 上下文模式

ContractCompanySignService 依赖 [ContractAspect](ContractContextManagement.md) 模块的 ThreadLocal 上下文机制：
- `HeaderContext.getUserId()` 获取当前登录人
- `HeaderContext.getContext().setOperatorUcId()` 设置操作人
- 通过 AOP 切面自动初始化和清理上下文，防止内存泄漏

### 5. 配置驱动的权限模型

自主盖章的分公司权限通过 Apollo 配置中心管理：
- `SelfSealCompanyInfoDTO` 包含 `systemCodes` 字段（逗号分隔的系统号列表）
- 运营人员的系统号通过 `CommonUtil.ucIdToSystemCode` 转换
- 权限判断：当前系统号是否在目标分公司的 `systemCodes` 中

---

## 与其他模块的关系

| 相关模块 | 关系 | 说明 |
|---------|------|------|
| [ContractDetail](ContractDetail.md) | 下游 | 签约完成后，合同详情页面展示签约状态和授权信息 |
| [ContractSubmission](ContractSubmission.md) | 上游 | 合同提交（草稿保存/托管提交）后进入签约流程 |
| [ContractValidation](ContractValidation.md) | 前置 | 签约前的字段校验和工种校验确保数据完整性 |
| [ContractContextManagement](ContractContextManagement.md) | 基础设施 | AOP 切面为对公签约提供上下文初始化和参数预处理 |
| [ButtonConfig](ButtonConfig.md) | 协作 | 授权列表的按钮配置由 ContractButtonConfigService 驱动 |
| [ContractSigningSource](ContractSigningSource.md) | 关联 | 个性化合同签约数据源策略，影响签约前的数据准备 |
| [ContractCreation](ContractCreation.md) | 上游 | 合同创建后进入签约流程，授权协议通过 ContractSubmitService 创建 |

---

## 枚举依赖速查

| 枚举 | 在本模块中的用途 |
|------|----------------|
| `ContractTypeEnum` | 授权协议类型（`ACCREDIT`）、需要授权协议的主合同类型判断、合同名称生成 |
| `ContractStatusEnum` | 合同状态判断（草稿撤回检测、有效状态过滤、完成状态判断） |
| `SignChannelTypeEnum` | 线上/线下签约渠道判断（仅线上签约需要授权协议） |
| `ContractObjectTypeEnum` | 签约主体类型（`COMPANY` 对公、`PERSON` 对私） |
| `RoleTypeEnum` | 签约角色（`LEGAL` 法人、`COMPANY_AGENT` 代理人） |
| `ContractButtonEnum` | 授权列表按钮类型（`VIEW` 查看等） |
| `ContractAuthStatusEnum` | 授权状态（企业实名认证状态、签约人授权状态） |
| `SelfSealStatusEnum` | 盖章任务状态（`SEAL_ING`、`SEAL_SUCCESS`、`SEAL_FAIL`） |
| `FileTypeEnum` | 自主盖章文件类型（`PDF`、`IMAGE`） |