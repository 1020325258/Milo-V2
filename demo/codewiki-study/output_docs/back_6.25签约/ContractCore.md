# ContractCore 合同核心模块

## 1. 模块概述

ContractCore 是装修业务合同管理系统的核心模块，覆盖合同全生命周期管理，包括合同创建、草稿保存、提交发起、PDF生成、盖章签署、审核审批、变更管理、合同完成等完整业务链路。该模块支持多种合同类型（正签合同、个性化销售合同、首期款合同、设计合同、变更合同、解约协议、补充协议、和解协议等），适配家装整装、翻新全案、局装、团装、零售等多种业务场景，同时兼容线上线下签约方式、个人签约与公对公签约等差异化业务流程。

---

## 2. 系统架构

```mermaid
graph TD
    subgraph presentation[Presentation Layer - ContractPresentation]
        HC[HomeContractService]
        PC[PcContractService]
        MP[ContractMpService]
        HPC[HomeAndPcCommonService]
    end

    subgraph core[Core Service Layer - ContractCore]
        CCS[CommonContractService]
        CBS[ContractBusinessService]
        CUS[ContractUnifyService]
        CDS[ContractDetailService]
        CSS[ContractSubmitService]
        CSDS[ContractSaveDraftService]
    end

    subgraph context[Context & AOP Layer]
        CCA[ContractContextAspect]
        CCH[ContractContextHandler]
        CDA[ContractDetailAspect]
        CDH[ContractDetailContextHandler]
    end

    subgraph specialized[Specialized Services]
        CCUS[ChangeContractUnifyService]
        QRCS[QuotationRelationCommonService]
        CMGC[ContractMergeLaunchComputer]
        CFCS[ContractFieldCheckService]
        CDDS[ContractDependentDataService]
        CSSR[ContractSigningSourceRouter]
    end

    subgraph pdf[PDF & Signing]
        CPB[ContractPdfBuildService]
        CPC[ContractPdfCreateService]
        FRS[FreeformService]
        FS[FaceAuthService]
    end

    subgraph events[Event & Async - ContractEvents]
        CEP[ContractEventProducer]
        KL[Kafka Listeners]
        SCH[Schedules]
    end

    subgraph config[Config Layer - ContractConfig]
        CAP[ContractApolloConfig]
        CCC[ContractCityCompanyConfigService]
        CVS[ContractConfigVersionService]
    end

    subgraph privacy[Privacy Layer - ContractPrivacy]
        POS[PrivacyOperateStrategy]
    end

    subgraph dao[Data Access Layer]
        CS[ContractService]
        CFS[ContractFieldService]
        CUS2[ContractUserService]
        CAS[ContractAttachService]
        CNS[ContractNodeService]
        CRLS[ContractRelationService]
        CQRS[ContractQuotationRelationService]
    end

    subgraph external[External Dependencies]
        NFC[NerveCenter RPC]
        ABR[AtomBudget RPC]
        FFA[FreeformApiFacade]
        BPS[BPM Service]
        QFS[QuotationFeignService]
        MDM[MDM RPC]
    end

    HC --> CUS
    PC --> CUS
    MP --> CBS
    HPC --> CCS
    HPC --> CBS

    CUS --> CCS
    CUS --> CBS
    CUS --> CDS
    CUS --> CSS
    CUS --> CSDS
    CUS --> CMGC

    CCA --> CCH
    CCA --> CUS
    CDA --> CDH
    CDA --> CDS

    CCS --> CS
    CCS --> CFS
    CCS --> CUS2
    CCS --> NFC
    CBS --> FFA
    CBS --> BPS
    CSS --> CUS
    CSS --> CCS
    CUS --> CCC
    CUS --> CVS
    CUS --> CAP
    CUS --> QRCS

    CCUS --> CUS
    CCUS --> CCS
    QRCS --> CQRS
    QRCS --> CRLS
    CMGC --> CUS
    CSSR --> CDDS
    CFCS --> CUS

    CEP --> KL
    KL --> CCS
    KL --> CBS
    KL --> CUS
```

---

## 3. 合同类型体系

```mermaid
graph TD
    CT[ContractTypeEnum] --> PKG_F[PACKAGE_FORMAL<br/>正式套餐合同]
    CT --> ADV[ADVANCE<br/>首期款合同]
    CT --> PER[PERSONAL<br/>个性化销售合同]
    CT --> DES[DESIGN<br/>设计合同]
    CT --> PKG_C[PACKAGE_CHANGE<br/>正签变更合同]
    CT --> DES_C[DESIGN_CHANGE<br/>设计变更合同]
    CT --> TER[TERMINAL<br/>解约协议]
    CT --> SUP[SUPPLEMENT<br/>补充协议]
    CT --> SET[SETTLEMENT<br/>和解协议]
    CT --> DRW[DRAWING<br/>施工图纸合同]
    CT --> ACC[ACCREDIT<br/>授权协议书]
    CT --> AUTH[AUTH_AGENT<br/>代理人授权合同]
    CT --> FES[FUND_ESCROW<br/>资金存管合同]
```

### 合同状态机

```mermaid
stateDiagram-v2
    [*] --> DRAFT: 创建草稿
    DRAFT --> PENDING_USER_SIGN: 提交发起
    DRAFT --> PENDING_COMPANY_SIGN: 线下发起
    DRAFT --> AUDITING: 需BPM审核
    DRAFT --> FINISH: 无需审核线下

    PENDING_COMPANY_SIGN --> PENDING_USER_SIGN: 盖章完成
    PENDING_COMPANY_SIGN --> PENDING_USER_CONFIRM: 协议确认类
    PENDING_COMPANY_SIGN --> FINISH: 无需用户签署

    AUDITING --> DRAFT: 审核驳回
    AUDITING --> AUDIT_REJECT: 审核驳回(个性化)
    AUDITING --> PENDING_USER_SIGN: 审核通过(签前)
    AUDITING --> PENDING_USER_CONFIRM: 审核通过(确认类)
    AUDITING --> PENDING_COMPANY_SIGN: 审核通过(签后)

    PENDING_USER_CONFIRM --> USER_CONFIRMED: 用户确认
    PENDING_USER_SIGN --> PENDING_COMPANY_SIGN: 用户签署完成
    PENDING_USER_SIGN --> FINISH: 合并发起直签完成

    USER_CONFIRMED --> FINISH: 盖章完成
    CANCEL --> [*]

    AUDIT_REJECT --> DRAFT: 撤回重发
```

---

## 4. 核心组件详解

### 4.1 CommonContractService - 合同公共服务

**职责**: 提供合同基础查询、格式化、业务通用逻辑，是合同模块的基础服务层。

**核心方法分组**:

| 方法组 | 代表方法 | 说明 |
|--------|----------|------|
| 基础查询 | `getBaseContractInfo`, `queryContractList`, `queryContractListBatch` | 按项目/类型查询合同基础信息 |
| 详情格式化 | `formatContractBaseDTO`, `formatAllContract` | 将DB对象转换为DTO，附带PDF链接、单据号等 |
| 节点信息 | `getBaseContractNodeInfo`, `getUserConfirmSignMixTime` | 获取合同流程节点（提交、确认、签署等时间线） |
| 字段查询 | `queryFieldList`, `queryContractFieldInfo` | 查询合同扩展字段（KV结构存储） |
| 合同完成 | `contractFinishHandler` | 合同签署完成后处理：创建款项、作废历史合同、同步资金模型 |
| 短信提醒 | `sendContractSmsRemind`, `sendOnlineContractSmsRemind` | 线上/线下合同签署后的短信通知 |
| 合同作废 | `cancelHistoryContracts`, `cancelOtherContracts`, `cancelCurrentContract` | 合同状态流转至作废，关联BPM审批取消 |
| 资金同步 | `syncNerveCenter` | 合同完成后将金额同步到资金模型（定金/工程款/设计费） |
| 公对公签约 | `openCompanySignOnline`, `getCompanyInfo` | 判断公对公线上签约是否开放 |
| 合同模式 | `computeFormalContractMode`, `getContractModeByContractCode` | 计算正签合同模式（如全案模式） |
| 合并发起 | `mergeLaunchContract`, `buildMergeTerminalContractReq` | 构建合并发起关联合同参数 |
| 大表推送 | `contractDataPushBigTable` | 正签/变更合同签署后推送到数据大表 |

**关键依赖关系**:

```mermaid
graph LR
    CCS[CommonContractService] --> CS[ContractService<br/>合同CRUD]
    CCS --> CFS[ContractFieldService<br/>合同字段KV]
    CCS --> CUS2[ContractUserService<br/>签约人信息]
    CCS --> CNS[ContractNodeService<br/>流程节点]
    CCS --> CAS[ContractAttachService<br/>合同附件]
    CCS --> CRLS[ContractRelationService<br/>合同关联]
    CCS --> CQRS[ContractQuotationRelationService<br/>报价单关联]
    CCS --> S3[S3Service<br/>文件存储]
    CCS --> NFC[NerveCenterRpc<br/>资金模型同步]
    CCS --> CPVS[ContractConfigVersionService<br/>配置版本]
    CCS --> FFA[FreeformApiFacade<br/>协议平台]
    CCS --> QRCS[QuotationRelationCommonService]
```

---

### 4.2 ContractBusinessService - 合同业务服务

**职责**: 处理合同签署、盖章、BPM审批、PDF生成等核心业务流程，是合同业务操作的中心枢纽。

**核心方法分组**:

| 方法组 | 代表方法 | 说明 |
|--------|----------|------|
| C端列表 | `getContractListGroup`, `getUserContractList`, `getUserContractListPage` | C端用户合同列表（整装+零售分组） |
| 签约URL | `getContractSignUrl`, `commonFetchSignUrl`, `accreditFetchAuthUrl` | 获取协议平台手签URL，区分个人签/公对公签/授权签 |
| 签约结果 | `contractSignResult`, `signSuccess` | 轮询签约结果，签署成功后更新状态 |
| 公司盖章 | `companySealSync`, `companySealAsync`, `updateCompanySealResult` | 同步/异步盖公司章，支持多主体盖章 |
| BPM审批 | `dealContractForBpm`, `applyContractBpm`, `dealContractResultForBpm` | 发起审批、获取审批人、处理审批结果 |
| PDF生成 | `generatePdf`, `generatePdfAddWaterMark` | 通过协议平台生成PDF（带/不带水印） |
| PDF转图片 | `contractPdfToImage`, `contractPdfToImageSchedule` | PDF转图片用于C端展示 |
| 签署校验 | `checkSignInfo`, `isFinishAfterSign`, `isFinishAfterChangeContractSign` | 校验实名认证、判断签署后是否直接完成 |
| 代理人 | `registerSignUser`, `registerUserSeal` | 注册个人签章，提前准备签署环境 |
| 关联合同 | `getRelationContract`, `getRelationContractCodeByContractCode` | 获取合并发起的关联合同列表 |

**合同签署流程**:

```mermaid
sequenceDiagram
    participant User as C端用户
    participant CBS as ContractBusinessService
    participant FFS as FreeformService
    participant Platform as 协议平台
    participant DB as Database

    User->>CBS: getContractSignUrl(contractCode)
    CBS->>CBS: checkSignInfo() 实名校验
    CBS->>DB: 查询签约人信息
    CBS->>CBS: registerUserSeal() 注册个人章
    CBS->>FFS: getSignUrl()
    FFS->>Platform: 创建签署链接
    Platform-->>FFS: 返回签署URL
    FFS-->>CBS: 返回URL
    CBS-->>User: 返回签署链接

    User->>CBS: contractSignResult(contractCode)
    CBS->>FFS: getContractSignResult()
    FFS->>Platform: 查询签署结果
    Platform-->>FFS: 返回签署PDF
    FFS-->>CBS: 返回PDF URL
    CBS->>CBS: signSuccess() 更新状态
    CBS->>DB: 更新合同状态、记录日志、发布事件
```

---

### 4.3 ContractUnifyService - 合同统一服务

**职责**: 合同核心业务的统一入口，涵盖签前校验、草稿保存、提交发起、详情查询、预览、配置管理等全流程操作。是整个合同模块中最大最核心的服务类。

**核心方法分组**:

#### 4.3.1 签前校验链

```mermaid
graph TD
    START[checkCanCreate] --> UC[checkContractUnique<br/>合同唯一性校验]
    START --> CO[checkContractInCancelOrder<br/>退单状态校验]
    START --> PSC[preSignCheck<br/>签前节点校验]

    PSC --> NODE1[人员校验<br/>设计师/经营部经理/预算员]
    PSC --> NODE2[量房打卡/到店服务]
    PSC --> NODE3[报价完成校验]
    PSC --> NODE4[预报价校验]
    PSC --> NODE5[零售配套校验]
    PSC --> NODE6[补充/和解协议前置校验]

    SEC[secondaryCheckCanCreate] --> ADV_CHECK[首期款预报价选择]
    SEC --> PER_CHECK[checkPersonalListV2<br/>销售合同单据校验]
    SEC --> FORMAL_CHECK[checkFormalListV2<br/>正签合同单据校验]
```

#### 4.3.2 合同详情构建

```mermaid
graph TD
    DETAIL[detailV2] --> BASE[baseDetail]
    BASE --> DASPECT[ContractDetailAspect<br/>AOP数据准备]
    DASPECT --> PROJ[项目信息]
    DASPECT --> PLAN[报价信息]
    DASPECT --> COMBO[套餐信息]
    DASPECT --> DRAW[图纸信息]
    DASPECT --> FUND[款项信息]
    DASPECT --> AUDIT[审核信息]
    DASPECT --> ATTACH[备件信息]

    BASE --> CDS[ContractDetailService]
    CDS --> BIZ[BusinessInfoDetail]
    CDS --> BASE_INFO[ContractBaseInfoDetail]
    CDS --> SIGN[ContractSignInfoDetail]
    CDS --> PROJECT[ContractProjectInfoDetail]
    CDS --> PROMISE[PromiseInfoDetail]
    CDS --> QUOTE[QuotationInfo]
    CDS --> PROCESS[ProcessInfo]
    CDS --> ATTACH_INFO[ContractAttachInfoDetail]
    CDS --> PERSONAL[PersonalQuotation]
```

#### 4.3.3 合同保存与提交

```mermaid
graph TD
    SAVE[saveDraftContract] --> BUILD[buildDraftContract<br/>构建合同实体]
    SAVE --> CORE[saveDraftCoreContractDb]
    SAVE --> MERGE[mergeLaunchSaveContract<br/>合并发起合同保存]
    SAVE --> BIND[bindContractRelation<br/>记录关联关系]
    SAVE --> QUOTE_BIND[bindCodeRelationWithClear<br/>记录报价单关联]

    SUBMIT[ContractSubmitService.submit] --> DRAFT[buildAndSaveContractDraft]
    SUBMIT --> LAUNCH[submitLaunch]
    LAUNCH --> PDF[parallelGreatPdf<br/>并行生成PDF]
    LAUNCH --> DATA[submitContractDealData<br/>提交后数据处理]
    DATA --> REWRITE[rewriteCustomer<br/>回写客源]
    DATA --> SMS[sendContractSmsRemind<br/>短信提醒]
    DATA --> AUDIT[dealContractForBpm<br/>发起审核]
```

#### 4.3.4 合同配置系统

配置采用三级降级策略获取：

```mermaid
graph TD
    REQ[配置请求] --> L1[城市+分公司+业务类型]
    L1 -->|未找到| L2[城市+业务类型]
    L2 -->|未找到| L3[业务类型]
    L3 -->|未找到| ERR[抛出异常]

    MOD[getModuleConfigAdapt] --> L1
    FIELD[getFieldConfigAdapt] --> L1
```

---

### 4.4 ContractContextAspect & ContractDetailAspect - AOP上下文管理

**职责**: 通过AOP切面，在合同操作前后自动准备和清理上下文数据（项目信息、报价信息、图纸信息、套餐信息等），避免在业务代码中重复查询。

```mermaid
sequenceDiagram
    participant Controller as Controller
    participant Aspect as ContractContextAspect
    participant Context as ContractContextHandler
    participant Service as ContractUnifyService
    participant RPC as External RPCs

    Controller->>Aspect: @ContractDataPrepare 方法调用
    Aspect->>Context: initContext()
    Aspect->>Aspect: preHandleParam() 参数预处理

    par 并行数据准备
        Aspect->>RPC: 获取项目信息
        Aspect->>RPC: 获取报价信息(PlanAllDTO)
        Aspect->>RPC: 获取套餐信息
        Aspect->>RPC: 获取图纸信息
        Aspect->>RPC: 获取操作人姓名
        Aspect->>RPC: 获取存管账户信息
        Aspect->>RPC: 获取标准设计费
        Aspect->>RPC: 获取合同主体信息
    end

    Aspect->>Aspect: 计算合同模式
    Aspect->>Aspect: 设计费预处理
    Aspect->>Service: 执行业务方法
    Service->>Context: getContext() 获取准备好的数据
    Service-->>Aspect: 返回结果
    Aspect->>Context: clearContext()
```

**ContractContext（ThreadLocal）包含的关键数据**:
- `projectInfoDTO` - 项目信息
- `planAllDTO` - 报价快照
- `contractSourceDataBO` - 报价源数据（含个性化报价）
- `drawingDTO` - 图纸信息
- `contractReq` - 合同请求参数
- `contractCityCompanyInfo` - 城市分公司配置
- `comboDTOList` - 套餐信息
- `designQuoteFeeDTO` - 设计费报价信息
- `mergeLaunch` - 是否合并发起标识

---

### 4.5 ContractMergeLaunchComputer - 合并发起计算器

**职责**: 根据Apollo配置规则，通过反射调用条件方法，计算当前合同需要合并发起的其他合同类型。

```mermaid
graph TD
    INPUT[computeContractType<br/>输入: contractType] --> CONFIG[读取Apollo配置<br/>mergeLaunchConfig]
    CONFIG --> RULES[遍历规则列表]
    RULES --> PARSE[解析rule字符串<br/>split by &]
    PARSE --> REFLECT[反射调用条件方法]
    REFLECT --> RESULT[返回合并发起类型列表]

    subgraph conditions[条件方法示例]
        FULL[fullService - 是否全案]
        V25[process_v2_5 - 是否2.5订单]
        HPQ[havePersonalQuote - 有个性化报价]
        NSP[noSignPersonalContract - 未签C合同]
        HSUP[houseBusinessType - 是否整装]
        TERM[launchTerminal - 是否发起解约]
        AUTH[hasAuthAgent - 是否有授权代理人]
        DRAW[hasUploadFormalDrawing - 是否上传图纸]
        SUP[mergeLaunchSupplement - 是否合并补充协议]
        DES[mergeLaunchDesign - 是否合并设计合同]
    end
```

---

### 4.6 QuotationRelationCommonService - 报价单关联服务

**职责**: 管理合同与报价单/S单/变更单之间的绑定关系，支持绑定、解绑、换绑（协同报价单→S单）。

**绑定关系类型**:

| BindTypeEnum | 说明 | 典型场景 |
|-------------|------|---------|
| BILL_CODE | 报价单 | 基础报价、协同报价 |
| SUB_ORDER | S单（子订单） | 报价单下单后的实际订单 |
| CHANGE_ORDER | 变更单 | 变更场景下的新报价 |

**换绑流程**:

```mermaid
sequenceDiagram
    participant Event as 合同提交事件
    participant QRCS as QuotationRelationCommonService
    participant Budget as AtomBudgetRpc
    participant SubOrder as SubOrderFeignService
    participant DB as ContractQuotationRelation

    Event->>QRCS: convertCooperBillToSubOrderByContract()
    QRCS->>DB: 查询合同关联的报价单
    QRCS->>Budget: 过滤出协同报价单类型
    loop 每个协同报价单
        QRCS->>SubOrder: 查询对应的S单
        QRCS->>DB: 解绑协同报价单
        QRCS->>DB: 绑定S单
        QRCS->>QRCS: 记录换绑日志
    end
```

---

### 4.7 ContractFieldCheckService - 字段校验服务

**职责**: 通过反射机制，根据配置动态调用校验方法，支持条件化校验。

| 校验方法 | 校验内容 |
|---------|---------|
| `checkBrandList` | 品类列表约定预收金额、品类编号合法性 |
| `checkBrandTotalAmount` | 品类总计金额 >= 款项已付金额 |
| `checkAdvanceAmount` | 首期款金额在预估合同额20%~70%范围内 |
| `checkAdvanceFileSize` | 首期款报价单PDF大小 <= 10M |
| `checkHouseType` | 房屋类型与报价侧一致（2.5需要） |
| `checkIdCardInfo` | 身份证号与姓名一致性校验 |
| `checkCompanyInfo` | 公司名称与统一社会信用代码匹配 |
| `checkDesignAmount` | 设计服务费优惠后 <= 优惠前 |

---

### 4.8 ContractDependentDataService - 合同依赖数据服务

**职责**: 获取合同所需的报价相关数据（个性化报价、协同报价、S单报价等），是正签和销售合同数据准备的核心。

```mermaid
graph TD
    BUILD[buildPersonalContractData] --> FORMAL[buildFormalPersonalContractData<br/>正签报价内的个性化报价]
    BUILD --> COOPER[buildCooperPersonalContractDataByBillCodeInfo<br/>协同C报价单]
    BUILD --> SUB[buildPersonalContractDataBySubOrderInfo<br/>S单报价数据]

    ROUTE[queryPersonalQuoteInfoV2] --> BSS[BillSigningSourceStrategy<br/>报价单策略]
    ROUTE --> SOS[SubOrderSigningSourceStrategy<br/>S单策略]
    ROUTE --> COS[ChangeOrderSigningSourceStrategy<br/>变更单策略]
```

### 4.9 个性化合同签约源策略（策略模式）

```mermaid
classDiagram
    class ContractSigningSource {
        <<interface>>
        +bindType() Integer
        +queryPersonalQuoteInfo(BindOrderInfo) List
        +hasInvalidStatusOrders(BindOrderInfo) boolean
        +buildGoodsInfo(BindOrderInfo) Map
        +buildSignableOrderInfos(String) List
        +checkPersonalCanCreate(String) boolean
        +buildPersonalDrawing(BindOrderInfo) DrawingDTO
        +hasCPart(BindOrderInfo) boolean
        +hasBPart(BindOrderInfo) boolean
    }

    class AbstractContractSigningSource {
        <<abstract>>
        #queryPersonalQuoteInfo(BindOrderInfo) List
        #buildPersonalDrawing(BindOrderInfo) DrawingDTO
        #buildParam(BindOrderInfo) PersonalContractDataParam
        #filterByCompanyCode() List
        #mergeCategoryNames() String
        #getHasBoundOrderNos() Set
    }

    class BillSigningSourceStrategy {
        +bindType() BILL_CODE
        +hasInvalidStatusOrders() boolean
        +buildGoodsInfo() Map
    }

    class SubOrderSigningSourceStrategy {
        +bindType() SUB_ORDER
        +hasInvalidStatusOrders() boolean
        +buildGoodsInfo() Map
        +buildSignableOrderInfos() List
    }

    class ChangeOrderSigningSourceStrategy {
        +bindType() CHANGE_ORDER
        +hasInvalidStatusOrders() boolean
        +buildGoodsInfo() Map
    }

    class ContractSigningSourceRouter {
        -sourceMap Map
        +route(Integer) ContractSigningSource
    }

    ContractSigningSource <|.. AbstractContractSigningSource
    AbstractContractSigningSource <|-- BillSigningSourceStrategy
    AbstractContractSigningSource <|-- SubOrderSigningSourceStrategy
    AbstractContractSigningSource <|-- ChangeOrderSigningSourceStrategy
    ContractSigningSourceRouter --> ContractSigningSource
```

---

## 5. 事件驱动架构（ContractEvents）

### 5.1 合同生命周期事件

```mermaid
graph LR
    subgraph events[合同事件]
        E1[CONTRACT_SUBMIT<br/>合同提交]
        E2[CONTRACT_USER_SIGN<br/>用户签署]
        E3[CONTRACT_USER_CONFIRM<br/>用户确认]
        E4[CONTRACT_COMPANY_SIGN<br/>公司盖章]
        E5[CONTRACT_FINISH<br/>合同完成]
        E6[CONTRACT_CANCEL<br/>合同作废]
        E7[CONTRACT_AUDIT_SUBMIT<br/>提交审核]
        E8[CONTRACT_AUDIT_PASS<br/>审核通过]
        E9[CONTRACT_AUDIT_REJECT<br/>审核驳回]
    end

    subgraph listeners[Kafka监听器]
        L1[ContractSubmitListener]
        L2[UserSignCompanySealListener]
        L3[ContractConfirmListener]
        L4[ContractCompanySealListener]
        L5[ContractFinishListener]
        L6[ContractScriptAdvanceListener]
        L7[SignCompanySealAfterSubmitListener]
    end

    subgraph actions[触发动作]
        A1[取消历史销售合同]
        A2[盖公司章]
        A3[发送短信提醒]
        A4[创建款项/同步资金模型]
        A5[生成合同讲解脚本]
        A6[注册用户签章]
        A7[PDF转图片]
        A8[推送大表数据]
        A9[同步关键时间节点]
    end

    E1 --> L1 --> A1
    E1 --> L7 --> A6
    E2 --> L2 --> A2
    E3 --> L3 --> A3
    E4 --> L4 --> A3
    E5 --> L5 --> A4
    E5 --> L5 --> A8
    E5 --> L5 --> A9
    E6 --> L6 --> A5
    E1 --> A7
```

### 5.2 定时任务

| 定时任务 | 说明 |
|---------|------|
| `ApplyBpmSchedule` | 补偿BPM审批发起（异常重试） |
| `AsyncSignTimeCheckSchedule` | 异步校验签署时间 |
| `ChangePersonalContractFieldSchedule` | 同步变更个性化合同字段 |
| `ContractFieldCheckSchedule` | 合同字段一致性巡检 |
| `FormFieldConfigCheckSchedule` | 表单字段配置巡检 |
| `PrivacyAccessWarnSchedule` | 隐私数据访问告警 |

---

## 6. 数据模型与持久化

### 6.1 核心数据表关系

```mermaid
erDiagram
    CONTRACT ||--o{ CONTRACT_FIELD : "contractCode"
    CONTRACT ||--o{ CONTRACT_USER : "contractCode"
    CONTRACT ||--o{ CONTRACT_NODE : "contractCode"
    CONTRACT ||--o{ CONTRACT_ATTACH : "contractCode"
    CONTRACT ||--o{ CONTRACT_MATERIAL : "contractCode"
    CONTRACT ||--o{ CONTRACT_LOG : "contractCode"
    CONTRACT ||--o{ CONTRACT_COMPANY : "contractCode"
    CONTRACT ||--o{ CONTRACT_AUDIT : "contractCode"
    CONTRACT ||--o{ CONTRACT_PDF_IMAGE : "pdfKey"
    CONTRACT ||--o{ CONTRACT_COLLECTION_PLAN_RECORD : "contractCode"

    CONTRACT ||--o{ CONTRACT_RELATION : "contractCode"
    CONTRACT ||--o{ CONTRACT_RELATION : "relateContractCode"
    CONTRACT ||--o{ CONTRACT_QUOTATION_RELATION : "contractCode"

    CONTRACT {
        long id PK
        string contractCode UK
        string contractNo
        string projectOrderId
        string changeOrderId
        byte type
        byte businessType
        int status
        byte signChannelType
        byte userSignType
        byte userSignStatus
        byte userConfirmStatus
        byte auditType
        decimal amount
        int gbCode
        string companyCode
        string previewKey
        string userSignedKey
        string bothSignedKey
        string thirdSignedKey
        long platformInstanceId
        int pdfPageCount
        int pdfGenerationMode
        string bmpNo
        string relateContractCode
        string createUserId
        string modifyUserId
    }

    CONTRACT_FIELD {
        long id PK
        string contractCode FK
        string fieldKey
        string fieldValue
        byte delStatus
    }

    CONTRACT_USER {
        long id PK
        string contractCode FK
        string name
        string phone
        byte roleType
        byte certificateType
        string certificateNo
        byte isSign
        byte isAuth
        string authChannelNo
    }

    CONTRACT_NODE {
        long id PK
        string contractCode FK
        byte nodeType
        long fireTime
        byte delStatus
    }

    CONTRACT_QUOTATION_RELATION {
        long id PK
        string contractCode FK
        string billCode
        string companyCode
        int bindType
        int status
        byte delStatus
    }

    CONTRACT_RELATION {
        long id PK
        string contractCode FK
        string relateContractCode
        int relationType
    }
```

### 6.2 合同字段KV存储设计

合同扩展字段采用KV结构存储在`contract_field`表中，每个字段以`fieldKey`+`fieldValue`的形式持久化。这种设计使得：
- 不同合同类型可以存储不同的字段集合
- 支持动态字段扩展，无需DDL变更
- 通过`ContractFieldConfig`配置表控制字段的展示、校验、编辑规则

---

## 7. 关键业务流程

### 7.1 正签合同发起完整流程

```mermaid
graph TD
    START[用户点击发起正签] --> CHECK1[checkCanCreate<br/>签前校验]
    CHECK1 --> CHECK2[secondaryCheckCanCreate<br/>二次校验C报价单选择]
    CHECK2 --> DETAIL[detailV2<br/>获取合同详情]
    DETAIL --> FILL[用户填写合同信息]
    FILL --> SAVE_DRAFT[saveDraftContract<br/>保存草稿]
    SAVE_DRAFT --> PREVIEW[previewAsync<br/>预览PDF]
    PREVIEW --> SUBMIT[submit<br/>提交发起]

    SUBMIT --> SAVE_DB[保存合同数据到DB]
    SAVE_DB --> GEN_PDF[createOnlinePdf<br/>生成正式PDF]
    GEN_PDF --> MERGE[mergeLaunchSaveContract<br/>合并发起关联合同]
    MERGE --> GEN_PDF_ALL[并行生成所有合同PDF]

    GEN_PDF_ALL --> SEAL{是否需要盖章?}
    SEAL -->|是| COMPANY_SIGN[companySeal<br/>盖公司章]
    SEAL -->|否| USER_SIGN{签约方式}
    COMPANY_SIGN --> USER_SIGN

    USER_SIGN -->|线上签署| PENDING_SIGN[待用户签署]
    USER_SIGN -->|协议确认| PENDING_CONFIRM[待用户确认]
    USER_SIGN -->|线下签署| OFFLINE[线下签章+完成]

    PENDING_SIGN --> SHARE[分享链接给客户]
    SHARE --> SIGN[客户签署]
    SIGN --> SIGN_RESULT[contractSignResult<br/>获取签署结果]
    SIGN_RESULT --> FINISH[合同完成]

    PENDING_CONFIRM --> CONFIRM[用户验证码确认]
    CONFIRM --> FINISH
```

### 7.2 合同审核流程

```mermaid
sequenceDiagram
    participant SYS as 合同系统
    participant BPM as BPM审批系统
    participant AUDIT as 风控审核

    SYS->>BPM: applyContractBpm()
    Note over SYS,BPM: 组装审批人、附件、记录数据
    BPM-->>SYS: 返回processInstId
    SYS->>SYS: 更新状态为AUDITING

    alt 审核通过
        BPM->>SYS: dealContractResultForBpm(PASS)
        SYS->>SYS: 线上: 更新待签署/待确认
        SYS->>SYS: 线下: 直接完成
        SYS->>SYS: 更新关联合同状态
        SYS->>SYS: 发布CONTRACT_AUDIT_PASS事件
    else 审核驳回
        BPM->>SYS: dealContractResultForBpm(REJECT)
        SYS->>SYS: 个性化/补充协议: 更新为AUDIT_REJECT
        SYS->>SYS: 其他: 回退到DRAFT
        SYS->>SYS: 回滚用户状态
        SYS->>SYS: 解除报价单绑定(个性化)
        SYS->>SYS: 发布CONTRACT_AUDIT_REJECT事件
    end
```

---

## 8. 变更合同子系统（ContractChange）

变更合同通过策略模式支持多种变更场景：

```mermaid
classDiagram
    class ChangeContractStrategy {
        <<interface>>
        +changeDetail()
        +beforeSaveDraftCheck()
        +saveDraft()
        +beforeSubmitCheck()
        +changeContractSubmit()
        +changeContractConfirm()
    }

    class NormalChangeContractStrategy {
        +changeContractSubmit()
    }

    class ZQChangeContractStrategy {
        +changeContractSubmit()
    }

    class ChangeContractStrategyFactory {
        +getChangeContractStrategy() ChangeContractStrategy
    }

    ChangeContractStrategy <|.. NormalChangeContractStrategy
    ChangeContractStrategy <|.. ZQChangeContractStrategy
    ChangeContractStrategyFactory --> ChangeContractStrategy
```

### 变更合同差异计算

```mermaid
graph TD
    DIFF[buildChangeContractDiff] --> MODEL[buildModelDiff<br/>基础字段差异]
    DIFF --> QUOTE[buildQuotationModelDiff<br/>报价差异]
    DIFF --> DRAW[buildDrawingDiff<br/>图纸差异]
    DIFF --> ATTACH[buildAttachModelDiff<br/>附件差异]

    QUOTE --> BUDGET[getQuoteBillDiff<br/>报价单新旧对比]
    QUOTE --> DISCOUNT[优惠变更对比]
    QUOTE --> SIGN_OBJ[签约主体变更对比]
```

---

## 9. PDF生成子系统（ContractPdf）

### 9.1 PDF生成策略

```mermaid
graph TD
    REQ[createOnlinePdf] --> MODE{pdfGenerationMode?}
    MODE -->|FORMATTED| FREEFORM[ContractPdfCreateService<br/>createPdfByFreeform<br/>通过协议平台版式生成]
    MODE -->|UNFORMATTED| SELF[ContractPdfCreateService<br/>createPdfBySelfGeneration<br/>系统自行拼接生成]

    SELF --> FACTORY[CreateContractPdfBySelfStrategyFactory]
    FACTORY --> HOUSE[HouseFormalContractPdfBySelfStrategy<br/>整装正签]
    FACTORY --> DRAWING[DrawingContractPdfBySelfStrategy<br/>图纸合同]
    FACTORY --> GROUP[GroupFormalContractPdfBySelfStrategy<br/>团装正签]
    FACTORY --> REFORM[ReformAllFormalContractPdfBySelfStrategy<br/>翻新全案]
```

### 9.2 PDF字段映射（ContractPdfBuildService）

ContractPdfBuildService 负责从合同数据中提取并转换PDF模板所需的所有字段，包括：

| 分类 | 字段举例 |
|------|---------|
| 基本信息 | 合同编号、项目地址、面积、户型 |
| 签约信息 | 签约人信息、甲方/乙方信息、公司信息 |
| 报价信息 | 套餐名称、报价金额、优惠信息 |
| 承包约定 | 工期、承包方式、甲供材料 |
| 收款计划 | 各期款项节点、金额、比例 |
| 图纸信息 | 施工图纸URL、个性化图纸 |
| 保修信息 | 水电保修年限、防水保修年限 |
| 设计费 | 优惠前/后设计费、设计师职级 |

---

## 10. 隐私与安全（ContractPrivacy）

```mermaid
classDiagram
    class PrivacyOperateStrategy {
        <<interface>>
        +decryptPrivacyInfo()
        +recordAndPostProcess()
    }

    class CopyCustomerPhoneStrategy {
        +decryptPrivacyInfo() 手机号解密
    }

    class ViewContractPdfStrategy {
        +decryptPrivacyInfo() PDF查看解密
    }

    class ViewCustomerIdCardStrategy {
        +decryptPrivacyInfo() 身份证解密
    }

    class ViewPropertyAddressStrategy {
        +decryptPrivacyInfo() 房产地址解密
    }

    PrivacyOperateStrategy <|.. CopyCustomerPhoneStrategy
    PrivacyOperateStrategy <|.. ViewContractPdfStrategy
    PrivacyOperateStrategy <|.. ViewCustomerIdCardStrategy
    PrivacyOperateStrategy <|.. ViewPropertyAddressStrategy
```

---

## 11. 外部依赖关系总览

```mermaid
graph LR
    subgraph contract[ContractCore]
        C[合同模块]
    end

    subgraph fund[资金域]
        NFC[NerveCenter<br/>资金模型同步]
        PAY[PayServiceRpc<br/>支付/短信]
        OCT[OctopusRpc<br/>款项变更]
        ESC[EscrowRpc<br/>资金存管]
        ORC[OrderCenterRpc<br/>订单中心]
    end

    subgraph quotation[报价域]
        ABR[AtomBudgetRpc<br/>报价/预报价]
        ACR[AtomChangeRpc<br/>变更申请]
        ADR[AtomDrawingRpc<br/>图纸查询]
        QFS[QuotationFeignService<br/>报价查询/设计费]
    end

    subgraph order[订单域]
        OSQ[OrderStandardQueryRpc<br/>主订单查询]
        SOF[SubOrderFeignService<br/>S单查询]
    end

    subgraph signing[签署域]
        FFA[FreeformApiFacade<br/>协议平台]
        FAC[FaceAuthService<br/>人脸识别]
    end

    subgraph bpm[审批域]
        BPM[BpmService<br/>BPM审批]
        ADR2[AuditRpc<br/>风控审核]
    end

    subgraph user[用户域]
        MDM[MdmRpc<br/>分公司信息]
        MEM[MemberRpc<br/>用户信息]
        CER[CeresRpc<br/>人员服务]
        CRT[CertificateRpc<br/>证件服务]
    end

    C --> fund
    C --> quotation
    C --> order
    C --> signing
    C --> bpm
    C --> user
```

---

## 12. 设计模式总结

| 模式 | 应用位置 | 说明 |
|------|---------|------|
| **策略模式** | `ContractSigningSource` → 3种策略 | 按绑定类型（报价单/S单/变更单）差异化处理个性化合同数据 |
| **策略模式** | `ChangeContractStrategy` → 2种策略 | 正常变更/ZQ变更的差异化处理 |
| **策略模式** | `CreateContractPdfBySelfStrategy` → 4种策略 | 按业务类型差异化PDF自生成 |
| **策略模式** | `AuditCheckStrategy` | 设计费审核校验策略 |
| **策略模式** | `PrivacyOperateStrategy` | 不同隐私场景的解密策略 |
| **AOP切面模式** | `ContractContextAspect`, `ContractDetailAspect` | 自动准备和清理上下文数据 |
| **ThreadLocal模式** | `ContractContextHandler`, `ContractDetailContextHandler` | 请求级别的上下文数据传递 |
| **工厂模式** | `ChangeContractStrategyFactory`, `ContractSigningSourceRouter` | 根据类型路由到具体策略实现 |
| **事件驱动模式** | `ContractEventProducer` + Kafka Listeners | 合同状态变更触发异步后续处理 |
| **模板方法模式** | `AbstractContractSigningSource` | 定义个性化数据获取骨架，子类实现差异化逻辑 |
| **反射调用模式** | `ContractFieldCheckService`, `ContractMergeLaunchComputer` | 基于配置名称动态调用校验/条件方法 |
| **Builder模式** | `ContractReqDTO`, `SignableOrderInfo` | 复杂参数对象的构建 |

---

## 13. 子模块索引

| 子模块 | 文档链接 | 职责 |
|--------|----------|------|
| ContractChange | [ContractChange.md](ContractChange.md) | 变更合同的创建、提交、差异计算、确认 |
| ContractSubmission | [ContractSubmission.md](ContractSubmission.md) | 合同提交、PDF生成、设计费审核、补充协议BPM |
| ContractPdf | [ContractPdf.md](ContractPdf.md) | PDF字段映射、PDF生成策略、PDF转图片 |
| ContractSigning | [ContractSigning.md](ContractSigning.md) | 签署流程、公司授权、视频观看、自盖章 |
| ContractComboAndMaterial | [ContractComboAndMaterial.md](ContractComboAndMaterial.md) | 套餐信息、材料清单PDF |
| ContractConfig | [ContractConfig.md](ContractConfig.md) | Apollo配置、城市分公司配置、版本管理、管理后台 |
| ContractEvents | [ContractEvents.md](ContractEvents.md) | Kafka事件生产者/消费者、定时任务 |
| ContractPrivacy | [ContractPrivacy.md](ContractPrivacy.md) | 隐私数据解密策略 |
| ContractPresentation | [ContractPresentation.md](ContractPresentation.md) | H5端/PC端/小程序端合同展示层 |
| ContractDataModels | [ContractDataModels.md](ContractDataModels.md) | Excel配置导入、数据模型BO |
