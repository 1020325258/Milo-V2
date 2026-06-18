# ContractPdfBuildService 代码分析

> **注意**: 该类的所有 public 方法均通过**反射调用**，方法名不可删除或修改。

---

## 一、基础合同信息

### 1. `getContractNo()`

| 维度 | 说明 |
|------|------|
| **方法职责** | 获取合同编号 |
| **数据来源** | `ContractContextHandler.getContext().getContract().getContractNo()` |
| **计算逻辑** | 直接取值，空则返回空字符串 |
| **输出 key** | `contractNo` |

---

### 2. `getProjectContractAddress()` / `getAddress()`

| 维度 | 说明 |
|------|------|
| **方法职责** | 获取房本地址（产权证地址） |
| **数据来源** | `ContractContextHandler.getContext().getContractReq().getProjectInfo().queryCertificateAddress()` |
| **计算逻辑** | 直接调用 `queryCertificateAddress()` 方法获取 |
| **输出 key** | `projectContractAddress` |
| **备注** | `getAddress()` 是 `getProjectContractAddress()` 的别名，逻辑完全相同 |

---

### 3. `getFloorName()`

| 维度 | 说明 |
|------|------|
| **方法职责** | 获取楼层名称 |
| **数据来源** | `ContractContextHandler.getContractReq().getProjectInfo().getFloorName()` |
| **计算逻辑** | 非空则取值，否则空字符串 |
| **输出 key** | `floorName` |

---

### 4. `getStructureInfo()`

| 维度 | 说明 |
|------|------|
| **方法职责** | 获取住宅结构和户型信息 |
| **数据来源** | `ContractContextHandler.getContractReq().getProjectInfo()` |
| **计算逻辑** | 住宅结构通过 `StructureEnum.getNameByCode()` 枚举转换；室/厅/厨/卫/阳台数直接取值转 String |
| **输出 key** | `structure`、`roomCnt`、`parlorCnt`、`cookroomCnt`、`toiletCnt`、`balconyCnt` |

---

### 5. `getArea()`

| 维度 | 说明 |
|------|------|
| **方法职责** | 获取建筑面积 |
| **数据来源** | `ContractContextHandler.getContractReq().getProjectInfo().getArea()` |
| **计算逻辑** | 直接取值 |
| **输出 key** | `area` |

---

## 二、承包约定信息

### 6. `getPromiseInfo()`

| 维度 | 说明 |
|------|------|
| **方法职责** | 获取承包约定信息（承包方式、开工条件、施工图纸方式、设计费、税率、纠纷处理等） |
| **数据来源** | `ContractContextHandler.getContractReq().getPromiseInfo()` |
| **计算逻辑** | 多个字段通过枚举转换（`ProjectContractModeEnum`、`ConstructionDrawModeEnum`），Null 安全处理；**特殊处理**：`B_LABOR_PART_MATERIALS_A_PART_MATERIALS_V2` 会映射为 `B_LABOR_PART_MATERIALS_A_PART_MATERIALS` 的 code 值 |
| **输出 key** | `ProjectContractMode`（code）、`ProjectContractModeName`（名称）、`openWorkDayToConstruct`、`constructionDrawMode`、`afterDiscountDesignerAmount`、`beforeDeliveryDaysToWork`、`taxRate`（带%后缀）、`disputeDealMode` |
| **条件分支** | `needDesignerAmount=YES` 且 `afterDiscountDesignerAmount` 非空时才显示设计费，否则显示"/" |

---

### 7. `getProjectDay()`

| 维度 | 说明 |
|------|------|
| **方法职责** | 获取工程工期天数 |
| **数据来源** | `ContractProjectInfoReq`（totalDuration/totalDurationEnum）、`Contract`（businessType/gbCode）、`ContractApolloConfig` |
| **计算逻辑** | 优先取 `totalDuration` 数值，null 则取 `TotalDurationEnum` 枚举名称；超过 Apollo 配置的上下限时显示"/" |
| **输出 key** | `projectDay` |
| **条件分支** | ① 整装/团装等不同业务类型工期上下限不同（Apollo 配置）；② **团装 2.5** 工期从 Apollo 按 gbCode 获取，配置为空则抛异常 |

---

### 8. `getPlanOpenDate()`

| 维度 | 说明 |
|------|------|
| **方法职责** | 获取计划开工日期 |
| **数据来源** | `projectInfo.getPlanStartTime()` |
| **计算逻辑** | 直接取值 |
| **输出 key** | `planOpenDate` |

---

## 三、设计师/预算员信息

### 9. `getDesignerName()`

| 维度 | 说明 |
|------|------|
| **方法职责** | 获取设计师姓名 |
| **数据来源** | `commonContractService.getDesignerInfo(projectOrderId)`，通过 `projectOrderId` 远程查询 |
| **计算逻辑** | 查询结果非空且姓名非空则取值，否则默认"/" |
| **输出 key** | `designerName` |

---

### 10. `getPreDiscountDesignerAmount()`

| 维度 | 说明 |
|------|------|
| **方法职责** | 获取设计服务费（优惠前）及大写金额 |
| **数据来源** | `projectInfo.getPreDiscountDesignerAmount()` |
| **计算逻辑** | 金额通过 `AmountUtil.getShowAmount()` 格式化；大写通过 `MoneyConvertUtil.convert()` 转换 |
| **输出 key** | `preDiscountDesignerAmount`（格式化后金额）、`preDiscountDesignerAmountText`（大写） |

---

### 11. `getDesignerLevel()`

| 维度 | 说明 |
|------|------|
| **方法职责** | 获取设计师级别 |
| **数据来源** | 优先取 `projectInfo.getDesignerLevelName()`，为空则通过 `DesignerLevelEnum.getNameByCode()` 从 code 转换 |
| **计算逻辑** | 先取名称，名称为空再从 code 枚举转换 |
| **输出 key** | `designerLevel` |

---

### 12. `getAfterDiscountDesignerAmount()`

| 维度 | 说明 |
|------|------|
| **方法职责** | 获取设计服务费（优惠后） |
| **数据来源** | `projectInfo.getAfterDiscountDesignerAmount()` |
| **计算逻辑** | `AmountUtil.getShowAmount()` 格式化 |
| **输出 key** | `afterDiscountDesignerAmount` |

---

### 13. `getBudgeter()`

| 维度 | 说明 |
|------|------|
| **方法职责** | 获取预算员姓名 |
| **数据来源** | `projectOrderFeignService.queryProjectServerInfo(projectOrderId, ServerTypeEnum.BUDGETER)` 远程调用 |
| **计算逻辑** | 调用订单服务查询预算员，非空则取 name |
| **输出 key** | `budgeter` |

---

### 14. `getDesignContractAmountInfo()`

| 维度 | 说明 |
|------|------|
| **方法职责** | 获取设计合同金额的完整描述文本（仅涉及被窝品牌） |
| **数据来源** | 内部调用 `getDesignerLevel()`、`getPreDiscountDesignerAmount()`、`getAfterDiscountDesignerAmount()` |
| **计算逻辑** | 优惠前 = 优惠后时，只展示一段话（不含优惠后描述）；不等时展示完整描述含优惠后金额 |
| **输出 key** | `designContractAmountInfo` |
| **条件分支** | 优惠前后金额相等 vs 不等，生成不同模板文本 |

---

## 四、签约方（甲方）信息

### 15. `getSignUserInfo()`

| 维度 | 说明 |
|------|------|
| **方法职责** | 获取甲方签约信息（客户姓名/手机/证件号、代理人信息） |
| **数据来源** | `ContractContextHandler.getContractReq().getSignInfo()` |
| **计算逻辑** | 敏感字段（手机、证件号）通过 `cipherService.decrypt()` 批量解密；无代理人时全部显示"/" |
| **输出 key** | `ownerAddress`、`jiafangXingming`、`firstPartyConnectPhone`、`customerIdNo`、`agentName`、`agentIdNo`、`agentPhone` |
| **条件分支** | ① `haveAgent=NO`：代理人字段全部"/"；② `contractObjectType=COMPANY`：客户名→公司名，手机→"/"，证件号→信用代码；公司经办人签约时覆盖代理人信息 |

---

### 16. `getSignUserInfoV2()`

| 维度 | 说明 |
|------|------|
| **方法职责** | 获取 2.5 版合同的甲方签约信息 |
| **数据来源** | `signInfo`，字段名使用中文拼音格式（如 `wanLianJiaFangXingMing`） |
| **计算逻辑** | 与 `getSignUserInfo()` 类似，但增加了**证件类型**字段，且字段命名符合 2.5 模板 |
| **输出 key** | `wanLianJiaFangLianXiDiZhi`、`wangLianJiaFangXingMing`、`wanLianJiaFangLianXiFangShi`、`wanLianJiaFangShenFenZhengHao`、`wangLianJiaFangZhengJianLeiXing`、`wanLianWeiTuoDaiLiRenShenFenZhengHao`、`wanLianWeiTuoDaiLiRenLianXiDianHua`、`wanLianWeiTuoDaiLiRenXingMing`、`WeiTuoDaiLiRenZhengJianLeiXing` |
| **条件分支** | ① `PERSON`：填充个人信息字段；② `COMPANY` + `COMPANY_AGENT` 角色：填充委托代理人字段 |

---

### 17. `getCompanyInfoV2()`

| 维度 | 说明 |
|------|------|
| **方法职责** | 获取 2.5 版合同甲方单位信息 |
| **数据来源** | `signInfo.getCompanyName()`、`signInfo.getCompanyCreditCode()` |
| **计算逻辑** | 直接取值 |
| **输出 key** | `wanLianJiaFangDanWeiMingCheng`（公司名称）、`companySealCode`（信用编码） |

---

### 18. `getAgentUserInfo()`

| 维度 | 说明 |
|------|------|
| **方法职责** | 获取代理人信息 |
| **数据来源** | `signInfo` |
| **计算逻辑** | 个人签约有代理人 → 取个人代理人信息；企业签约 → 取公司代理人信息。敏感字段解密 |
| **输出 key** | `agentName`、`agentIdNoType`、`agentIdNo`、`agentPhone` |
| **条件分支** | `PERSON` + `haveAgent=YES`；`COMPANY`（`signRole` 为 null 或 `COMPANY_AGENT`） |

---

### 19. `getFirstPartUserInfo()`

| 维度 | 说明 |
|------|------|
| **方法职责** | 获取甲方信息（统一的客户/公司接口） |
| **数据来源** | `signInfo`，批量解密 |
| **计算逻辑** | 个人签约：取业主信息 + 有代理人时取代理人信息；企业签约：取公司信息 + `COMPANY_AGENT` 角色时取经办人信息 |
| **输出 key** | `firstPartName`、`firstPartPhone`、`firstPartCertificateNo`、`firstCertificateType`、`firstAgentPartName`、`firstAgentCertificateType`、`firstAgentPartCertificateNo`、`firstAgentPartPhone` |
| **条件分支** | `PERSON` vs `COMPANY`；有无代理人；`signRole` 类型 |

---

### 20. `getFirstPartAddressInfo()`

| 维度 | 说明 |
|------|------|
| **方法职责** | 获取甲方地址 |
| **数据来源** | `signInfo` |
| **计算逻辑** | 个人→住所地址；公司→注册地址 |
| **输出 key** | `firstPartAddress` |
| **条件分支** | `PERSON` vs `COMPANY` |

---

### 21. `getLegalUserInfo()`

| 维度 | 说明 |
|------|------|
| **方法职责** | 获取法定代表人信息 |
| **数据来源** | `signInfo` 的法律代表字段 |
| **计算逻辑** | 证件号解密 |
| **输出 key** | `legalName`、`legalCertificateType`、`legalCertificateNo` |

---

### 22. `getCompanyAgentUserInfo()`

| 维度 | 说明 |
|------|------|
| **方法职责** | 获取公司代理人信息 |
| **数据来源** | `signInfo` 的公司代理人字段 |
| **计算逻辑** | 证件号、手机号解密 |
| **输出 key** | `agentName`、`agentPhone`、`agentIdNoType`、`agentIdNo` |

---

### 23. `getSignatoryUserInfo()`

| 维度 | 说明 |
|------|------|
| **方法职责** | 获取**实际签约人**信息（可能是业主/代理人/公司经办人/法人） |
| **数据来源** | `signInfo` + `contractUnifyService.getSignatoryRoleType()` 判断实际签约角色 |
| **计算逻辑** | 根据 `signatoryRoleType` 分 4 种角色取不同字段，敏感信息解密 |
| **输出 key** | `signatoryName`、`signatoryCertificateType`、`signatoryCertificateNo`、`signatoryPhone` |
| **条件分支** | `OWNER` / `AGENT` / `COMPANY_AGENT` / `LEGAL` 四种角色 |

---

## 五、乙方（公司）信息

### 24. `getCompanyInfo()`

| 维度 | 说明 |
|------|------|
| **方法职责** | 获取乙方分公司信息 |
| **数据来源** | `commonContractService.getCompanyInfo(companyCode)` |
| **计算逻辑** | `companyCode` 取值逻辑因合同类型不同：个性化合同→签约公司 code；个人/资金存管合同→合同上的 companyCode；其他→上下文城市公司 code |
| **输出 key** | `companyCode`、`companyName`、`companyAddress`、`companyPhone`、`companySealCode`、`companyBank`、`companyAccount` |
| **条件分支** | 个性化合同 / 个人合同 / 资金存管合同 / 其他，取不同的 companyCode 来源 |

---

### 25. `getMultiCompanyInfo()`

| 维度 | 说明 |
|------|------|
| **方法职责** | 获取多主体乙方分公司信息 |
| **数据来源** | `ContractContextHandler.getContext().getContractCompanyList()` |
| **计算逻辑** | 遍历多个主体，每个主体的 key 加编号后缀（第2个主体为 `company2XXX`，第3个为 `company3XXX`）；无多主体数据时 fallback 到 `getCompanyInfo()` |
| **输出 key** | 第1个主体：`companyCode/Name/...`；第N个：`company{N}Code/Name/...` |
| **条件分支** | 空列表时退化为单主体逻辑 |

---

### 26. `getSecondPartyCompanyInfo()`

| 维度 | 说明 |
|------|------|
| **方法职责** | 获取乙方销售公司名称 |
| **数据来源** | `contractCompanyInfoService.getByCompanyCode(signCompanyCode)` |
| **计算逻辑** | 从签约公司 code 查询公司名称 |
| **输出 key** | `salesCompanyName` |

---

## 六、金额相关

### 27. `getContractAmount()`

| 维度 | 说明 |
|------|------|
| **方法职责** | 获取合同金额及大写 |
| **数据来源** | 套餐正式/全服务汇总合同→`planAllDTO.getPlanInfo().getContractPriceTotal()`；其他→`projectInfo.getAmount()` |
| **计算逻辑** | 套餐正式合同额外计算：供应商承担金额、供应商+客户承担总额及其大写 |
| **输出 key** | `contractAmount`、`contractAmountText`；套餐正式合同额外输出 `planDeveloperTotalPrice`、`planDeveloperTotalPriceText`、`planDeveloperAndClientTotalPrice`、`planDeveloperAndClientTotalPriceText` |
| **条件分支** | `PACKAGE_FORMAL` / `FULL_SERVICE_SUMMARY` vs 其他合同类型 |

---

### 28. `getContractAdvanceAmount()`

| 维度 | 说明 |
|------|------|
| **方法职责** | 获取首期款合同金额信息 |
| **数据来源** | 根据是否支持预报价，取 `quotation` 或 `projectInfo` 中的金额 |
| **计算逻辑** | 计算 B 支付金额 + 预计合同金额 = B+C 金额 |
| **输出 key** | `advanceAmount`、`advanceAmountText`、`expectContractAmount`、`expectContractAmountText`、`advanceToBAmount`、`advanceToBAmountText`、`advanceToBCAmount`、`advanceToBCAmountText` |
| **条件分支** | `getAdvanceFromQuotation`=true → 从报价模块取；false → 从项目模块取 |

---

### 29. `getContractAmountV2()`

| 维度 | 说明 |
|------|------|
| **方法职责** | 获取 2.5 版合同金额大写 |
| **数据来源** | `planAllDTO.getPlanInfo().getContractPriceTotal()` |
| **计算逻辑** | `MoneyConvertUtil` 转大写 |
| **输出 key** | `wanLianGongChengKuanDaXie` |

---

### 30. `getQuotationTotalAmount()`

| 维度 | 说明 |
|------|------|
| **方法职责** | 获取报价总价 |
| **数据来源** | `planAllDTO.getPlanInfo().getQuotePrice()` |
| **计算逻辑** | 直接取值 |
| **输出 key** | `quotationTotalAmount` |

---

### 31. `getPersonalContractAmount()`

| 维度 | 说明 |
|------|------|
| **方法职责** | 获取个性化合同金额 |
| **数据来源** | 首期款→`amountInfo.getQuoteTotalAmount()`；个性化主材→`contract.getAmount()` |
| **计算逻辑** | 首期款取报价总金额并保留2位小数；主材合同取合同金额 |
| **输出 key** | `personalTotalPrice`、`personalTotalPriceText` |
| **条件分支** | `PERSONALIZED_CONTRACT`（含首期款）vs 其他个性化合同，金额来源不同 |

---

### 32. `getBrandTotalAmount()`

| 维度 | 说明 |
|------|------|
| **方法职责** | 获取品类报价总金额和预收总金额 |
| **数据来源** | `amountInfo.getQuoteTotalAmount()`、`amountInfo.getDueTotalAmount()` |
| **计算逻辑** | 保留2位小数，四舍五入 |
| **输出 key** | `quoteTotalAmount`、`dueTotalAmount` |

---

### 33. `getAdvanceRate()`

| 维度 | 说明 |
|------|------|
| **方法职责** | 获取首期款收款比例 |
| **数据来源** | 优先 `projectInfo.getAdvanceRate()`；预报价模式从 `quotation` 取；null 时默认 20%（来自 `FundTaskTypeEnum.ADVANCE_COLLECTION_PROGRESS`） |
| **计算逻辑** | 小数 → 百分比格式化（`0.1` → `10%`），不保留小数位 |
| **输出 key** | `advanceRate` |

---

### 34. `getPercentageOfTotalOrderAmount()`

| 维度 | 说明 |
|------|------|
| **方法职责** | 获取订单总金额百分比及一期收款金额 |
| **数据来源** | `contractApolloConfig.getPercentageConfigByGbCode(gbCode)` 获取百分比配置；`contract.getAmount()` 获取合同金额 |
| **计算逻辑** | 百分比配置转百分比格式；合同金额 × 百分比 = 一期收款金额 |
| **输出 key** | `percentageOfTotalOrderAmount`、`firstInstallmentAmountByPercentage`、`firstInstallmentAmountByPercentageText` |

---

### 35. `getRemainingPercentageOfTotalOrderAmount()`

| 维度 | 说明 |
|------|------|
| **方法职责** | 获取剩余百分比及二期收款金额 |
| **数据来源** | 同上，取 `remainingPercentageOfTotalOrderAmount` 配置 |
| **计算逻辑** | 合同金额 × 剩余百分比 = 二期收款金额 |
| **输出 key** | `remainingPercentageOfTotalOrderAmount`、`secondInstallmentAmountByRemainingPercentage`、`secondInstallmentAmountByRemainingPercentageText` |

---

## 七、收款计划

### 36. `getCollectionPlanInfo()`

| 维度 | 说明 |
|------|------|
| **方法职责** | 获取收款计划（各期付款金额和比例） |
| **数据来源** | `contractReq.getCollectionPlanConfigInfo().getContent()`、`planAllDTO.getPlanInfo().getContractPriceTotal()` |
| **计算逻辑** | 遍历收款计划项：金额 = `price`（非零时）或 `contractAmount × rate`；分别格式化为旧版 `PAY_PLAN_FORMAT` 和新版 `PAY_PLAN_FORMAT_NEW` 两种文本；前三期分别输出独立金额字段 |
| **输出 key** | `payPlan`（旧版格式）、`payPlanNew`（新版格式）、`firstPayAmount/Text`、`secondPayAmount/Text`、`thirdPayAmount/Text` |
| **条件分支** | **团装 2.5 第一期**：新版格式追加"其中合同总金额的20%部分作为定金" |

---

## 八、优惠/优惠券

### 37. `getCoupon()`

| 维度 | 说明 |
|------|------|
| **方法职责** | 获取优惠券信息 |
| **数据来源** | `planAllDTO.getCouponList()`、`contractBusinessService.getCouponRemarkList(planAllDTO)` |
| **计算逻辑** | 遍历优惠券列表，筛选 `DIRECT_COUPON`（直减券）取 `lapseAmount`；备注列表用 `\n` 拼接 |
| **输出 key** | `couponAmount`（直减金额）、`couponRemark`（优惠备注文本） |

---

## 九、附件类（报价单/精装细则/图纸/配置清单等）

### 38. `getBudgetUrl()`

| 维度 | 说明 |
|------|------|
| **方法职责** | 获取报价单图片 URL（旧版，每页独立格式） |
| **数据来源** | `planAllDTO.getPlanAttachmentList()` 筛选 `PlanAttachment.报价单` |
| **计算逻辑** | PDF → 图片转换（`pdfToImageService.pdf2ImagePublicParallel`），每页带签约日期封装为 `Photo` 对象 |
| **输出 key** | `budgetUrl` |
| **条件分支** | 无版式模式（`UNFORMATTED`）直接返回空；中控模式下缺少报价单则抛异常 |

---

### 39. `getBudgetUrlV2()`

| 维度 | 说明 |
|------|------|
| **方法职责** | 获取报价单图片（新版，最后一页盖章） |
| **数据来源** | 首期款合同→从 `quotation` 取预报价文件 URL；其他→从 `planAttachmentList` 取 |
| **计算逻辑** | PDF → 图片，最后一页标记 `sign=true`（盖章） |
| **输出 key** | `budgetUrlV2` |
| **条件分支** | ① 无版式模式→空；② 正签+全案模式→空；③ 首期款合同→取预报价文件；④ 翻新工程首期款→额外检查页数上限 |

---

### 40. `getDecorateRuleUrl()`

| 维度 | 说明 |
|------|------|
| **方法职责** | 获取精装细则图片 URL（2.5 北京专用） |
| **数据来源** | `commonContractService.getComboCodesByPlanAllDTO()` 获取套餐 codes → `comboInfoService.getDecorateRule()` 获取精装细则图片 |
| **计算逻辑** | 遍历所有套餐，获取每个套餐的精装细则图片 URL，附加签约日期 |
| **输出 key** | `decorateRuleUrl`（`Photo` 格式）、`decorateRuleUrlV2`（`PhotoInfo` 格式，最后一页标记盖章） |

---

### 41. `getDecorateRuleUrlV2()`

| 维度 | 说明 |
|------|------|
| **方法职责** | 获取精装细则图片（新版，最后一页盖章） |
| **数据来源** | 同 `getDecorateRuleUrl()`，从套餐获取 |
| **计算逻辑** | 与旧版类似，但统一使用 `PhotoInfo` 格式，最后一页标记盖章 |
| **输出 key** | `decorateRuleUrlV2` |
| **条件分支** | 正签+全案模式→不附带 |

---

### 42. `getAdvanceDecorateRuleUrl()`

| 维度 | 说明 |
|------|------|
| **方法职责** | 获取首期款精装细则图片 |
| **数据来源** | 套餐 ID 通过 `getAdvancePackageId()` 获取（兼容不同版本取值） |
| **计算逻辑** | 与 `getDecorateRuleUrlV2()` 类似，仅用于首期款合同 |
| **输出 key** | `decorateRuleUrlV2` |

---

### 43. `getBudgetRuleUrl()`

| 维度 | 说明 |
|------|------|
| **方法职责** | 获取预算编制说明（不盖章） |
| **数据来源** | `comboInfoService.getBudgetDesc()` |
| **计算逻辑** | 按套餐遍历获取预算编制说明图片 |
| **输出 key** | `budgetRuleUrl` |
| **条件分支** | 无版式模式→空 |

---

### 44. `getMaterialUrl()`

| 维度 | 说明 |
|------|------|
| **方法职责** | 获取材料配送清单（不盖章） |
| **数据来源** | `comboInfoService.getMaterialList()` |
| **计算逻辑** | 按套餐遍历获取材料配送清单图片 |
| **输出 key** | `materialUrl` |
| **条件分支** | 无版式模式→空；无图片则不输出 |

---

### 45. `getInternalConfigurationsUrl()`

| 维度 | 说明 |
|------|------|
| **方法职责** | 获取套餐套内配置清单 |
| **数据来源** | `planAllDTO.getPlanAttachmentList()` 筛选 `PlanAttachment.套餐套内配置清单` |
| **计算逻辑** | 查找对应类型附件并转图片 |
| **输出 key** | `internalConfigurationsUrl` |
| **条件分支** | 团装无配置清单时 fallback 取报价单 URL |

---

### 46. `getExtraConfigurationsUrl()`

| 维度 | 说明 |
|------|------|
| **方法职责** | 获取加载配置清单 |
| **数据来源** | `planAttachmentList` 筛选 `PlanAttachment.加载配置清单` |
| **输出 key** | `extraConfigurationsUrl` |

---

### 47. `getPersonalQuotionUrl()`

| 维度 | 说明 |
|------|------|
| **方法职责** | 获取套外个性化报价单 |
| **数据来源** | V2.5→调用 `getPersonalBudgetUrlV2()`；旧版→`planAttachmentList` 筛选 `PlanAttachment.套外个性化报价单`（支持多文件） |
| **计算逻辑** | V2.5 逻辑更复杂，需校验 C 部分、文件存在性等 |
| **输出 key** | `personalQuotionUrl` |
| **条件分支** | `processV25` → 走 V2.5 逻辑；否则走旧版多文件逻辑 |

---

### 48. `getPersonalBudgetUrlV2()`

| 维度 | 说明 |
|------|------|
| **方法职责** | 获取个性化报价单（2.5 版本，支持 B/C 部分校验） |
| **数据来源** | `ContractSourceDataBO.getPersonalContractDataList()` 获取个性化合同数据 → 取报价文件 URL |
| **计算逻辑** | ① 仅个性化主材/图纸报价合同需要；② 全案模式不附带；③ 团装 2.5 金额为0不附带；④ B/BC 付款方式且金额为0时需校验是否有 C 部分报价；⑤ PDF→图片，最后一页盖章 |
| **输出 key** | `personalBudgetUrl` |
| **条件分支** | 合同类型、合同模式、业务类型、是否 B/BC 付款方式 |

---

### 49. `getPersonalDrawing()`

| 维度 | 说明 |
|------|------|
| **方法职责** | 获取个性化设计图纸 |
| **数据来源** | `personalContractDataList` → `contractSigningSourceRouter.route().buildPersonalDrawingImgList()` |
| **计算逻辑** | 根据商品行查询图纸信息，按绑定类型路由获取图纸图片列表 |
| **输出 key** | `personalDrawing` |
| **条件分支** | 仅个性化主材/图纸报价合同需要；全案模式不附带 |

---

### 50. `getBaseConstructionDrawUrl()`

| 维度 | 说明 |
|------|------|
| **方法职责** | 获取基础图纸 |
| **数据来源** | `planAttachmentList` 筛选 `PlanAttachment.基础图纸` |
| **输出 key** | `baseConstructionDrawUrl` |

---

### 51. `getDrawingUrl_2_5()`

| 维度 | 说明 |
|------|------|
| **方法职责** | 获取施工图纸图片（2.5 版，所有页都盖章） |
| **数据来源** | `ContractContextHandler.getDrawingDTO()` → 筛选 `基础图纸` 类型且 PDF 扩展名 |
| **计算逻辑** | 从图纸 DTO 获取预览路径列表，每页标记 `sign=true` |
| **输出 key** | `drawingUrl` |

---

### 52. `getDrawingUrlV2()`

| 维度 | 说明 |
|------|------|
| **方法职责** | 获取施工图纸（支持自定义盖章位置） |
| **数据来源** | 同 `getDrawingUrl_2_5()` |
| **计算逻辑** | 仅最后一页标记 `sign=true`，其余不盖章 |
| **输出 key** | `drawingUrlV2` |

---

### 53. `getMaterialForB()`

| 维度 | 说明 |
|------|------|
| **方法职责** | 获取 B 承担部分材料清单 |
| **数据来源** | `ContractContextHandler.getDrawingDTO()` |
| **计算逻辑** | 团装正签→筛选 `商品清单`；团装/整装销售合同→筛选 `软装配置清单`；仅 B/BC 付款方式时才处理。PDF→图片，最后一页盖章 |
| **输出 key** | `materialForB` |
| **条件分支** | 团装（`GROUP_DECORATE`）vs 整装（`HOUSE_CERTIFICATE`）× 正签/销售 × 是否 B/BC 付款方式 |

---

## 十、附件配置类（通用附件获取逻辑）

### 54. `getServicePromise()`

| 维度 | 说明 |
|------|------|
| **方法职责** | 获取十心实意服务承诺附件 |
| **数据来源** | `getAttachConfig()` → `contractAttachConfigService` |
| **输出 key** | `servicePromise` |
| **条件分支** | 全案+其他附件合同 或 非全案（正式套餐/首期款） |

---

### 55. `getValuationExplanation()`

| 维度 | 说明 |
|------|------|
| **方法职责** | 获取基础套餐金额计价说明 |
| **数据来源** | 同上 |
| **输出 key** | `valuationExplanation` |
| **条件分支** | 同 `getServicePromise()` |

---

### 56. `getPersonalSignNotification()`

| 维度 | 说明 |
|------|------|
| **方法职责** | 获取个性化签约告知函 |
| **数据来源** | 同上 |
| **输出 key** | `personalSignNotification` |
| **条件分支** | 全案+其他附件 或 非全案个性化合同 |

---

### 57. `getCategoryInformation()`

| 维度 | 说明 |
|------|------|
| **方法职责** | 获取品类信息说明 |
| **数据来源** | 同上 |
| **输出 key** | `categoryInformation` |
| **条件分支** | 同 `getPersonalSignNotification()` |

---

### 58. `getGroupCategoryInformation()`

| 维度 | 说明 |
|------|------|
| **方法职责** | 获取新零售产品品类信息说明（团装） |
| **数据来源** | `getAttachConfig(GROUP_CATEGORY_INFORMATION, ...)` |
| **输出 key** | `groupCategoryInformation` |

---

### 59. `getInstallationAndDelivery()`

| 维度 | 说明 |
|------|------|
| **方法职责** | 获取安装交付增值服务费标准 |
| **数据来源** | `getAttachConfig(INSTALLATION_AND_DELIVERY, ...)` |
| **输出 key** | `installationAndDelivery` |

---

### 60. `getCustomAttach()`

| 维度 | 说明 |
|------|------|
| **方法职责** | 获取个性化自定义附件 |
| **数据来源** | `contractCustomAttachConfigService.getContractCustomAttachWithDefault()` |
| **计算逻辑** | 按 gbCode/businessType/companyCode/contractFormType 查询配置，根据合同类型取对应图片 URL（逗号分隔多张） |
| **输出 key** | `contractCustomAttach` |
| **条件分支** | 无版式模式→空；仅首期款/正签/销售合同支持；按合同类型取 `advanceImageUrl` / `packageFormalImageUrl` / `personalImageUrl` |

---

### 61. `getDurationDescriptionAttach()`

| 维度 | 说明 |
|------|------|
| **方法职责** | 获取工期说明附件 |
| **数据来源** | `contractAttachConfigService` 获取 `DURATION_DESCRIPTION_ATTACH` 类型配置 |
| **输出 key** | `durationDescAttach` |

---

## 十一、保修信息

### 62. `getGuaranteeInfo()`

| 维度 | 说明 |
|------|------|
| **方法职责** | 获取保修年限信息 |
| **数据来源** | `contractReq.getGuaranteeInfo()` |
| **计算逻辑** | 兼容直接数值和枚举两种存储方式 |
| **输出 key** | `otherGuaranteeYear`、`waterElectricGuaranteeYear`、`waterProofGuaranteeYear` |

---

### 63. `getWaterElectricGuaranteeYear()`

| 维度 | 说明 |
|------|------|
| **方法职责** | 获取电气管线保修年限 |
| **数据来源** | `getContractBusinessConfig()` → Apollo 配置 |
| **计算逻辑** | 数字→中文大写（如"五"），默认"/" |
| **输出 key** | `waterElectricGuaranteeYear` |

---

### 64. `getWaterProofGuaranteeYear()`

| 维度 | 说明 |
|------|------|
| **方法职责** | 获取防水工程保修年限 |
| **数据来源** | 同上 |
| **输出 key** | `waterProofGuaranteeYear` |

---

### 65. `getOtherGuaranteeYear()`

| 维度 | 说明 |
|------|------|
| **方法职责** | 获取其他部位保修年限 |
| **数据来源** | 同上 |
| **输出 key** | `otherGuaranteeYear` |

---

### 66. `getContractBusinessConfig()`

| 维度 | 说明 |
|------|------|
| **方法职责** | 获取业务配置（保修年限的底层查询方法） |
| **计算逻辑** | 团装→从团装配置按 gbCode 取；其他→按 gbCode + 是否开渠查询，查不到兜底取非开渠配置 |
| **条件分支** | `GROUP_DECORATE` vs 其他；开渠 vs 非开渠（兜底） |

---

## 十二、套餐信息

### 67. `getPackageNameByPackageId()`

| 维度 | 说明 |
|------|------|
| **方法职责** | 获取套餐名称（认购/设计） |
| **数据来源** | 支持预报价→从 `quotation` 取；否则→`quotationFeignService.getPackageList()` 按 packageId 查 |
| **计算逻辑** | 预报价模式直接取套餐名；其他模式通过 RPC 获取套餐列表匹配 |
| **输出 key** | `packageName` |
| **条件分支** | `advanceSupportPreQuotation` → 直接取；否则 → RPC 查询 |

---

### 68. `getPackageNameFromPlanAllDTO()`

| 维度 | 说明 |
|------|------|
| **方法职责** | 从报价方案获取套餐名称 |
| **数据来源** | `planAllDTO.getPlanInfo().getComboName()` |
| **输出 key** | `packageName` |

---

### 69. `getComboCodesByContractType()`

| 维度 | 说明 |
|------|------|
| **方法职责** | 根据合同类型获取套餐 code 列表（工具方法） |
| **计算逻辑** | 首期款→取 `getAdvancePackageId()`；其他→从 PlanAllDTO 获取 |

---

## 十三、面积信息

### 70. `getAreaV2()`

| 维度 | 说明 |
|------|------|
| **方法职责** | 获取 2.5 版面积（计价面积） |
| **数据来源** | 设计费类合同→`projectInfo` 的计价面积/建筑面积；其他→`planAllDTO.getPlanInfo().getPricingArea()` |
| **计算逻辑** | 设计费合同优先取 `valuationArea`，为空 fallback 到 `area`；其他合同从报价获取 |
| **输出 key** | `wanLianZhuangXiuGongChengMianJi`、`valuationArea` |
| **条件分支** | `DESIGN_FEE_DESIGN_TYPES` vs 其他合同类型 |

---

### 71. `getAdvanceContractArea()`

| 维度 | 说明 |
|------|------|
| **方法职责** | 获取首期款合同面积（支持不同城市取不同面积类型） |
| **数据来源** | 支持预报价→从 `quotation` 取；否则根据城市配置取计价面积或建筑面积 |
| **计算逻辑** | `expectAmountUseAreaType` 判断取计价面积还是建筑面积 |
| **输出 key** | `valuationArea`、`area`（互斥，不使用的显示"/"） |
| **条件分支** | 预报价模式 / `VALUATION_AREA` 类型 / 建筑面积类型 |

---

### 72. `getFormalAreaInfo()`

| 维度 | 说明 |
|------|------|
| **方法职责** | 获取正签合同面积信息 |
| **数据来源** | 建筑面积城市列表 + `planAllDTO` 计价面积 |
| **计算逻辑** | gbCode 在使用建筑面积城市列表中→取建筑面积；否则→取计价面积 |
| **输出 key** | `valuationArea`、`area`（互斥） |
| **条件分支** | 按城市 gbCode 判断 |

---

### 73. `getAdvanceValuationArea()`（已废弃）

| 维度 | 说明 |
|------|------|
| **方法职责** | 获取首期款计价面积（旧版） |
| **输出 key** | `valuationArea` |
| **备注** | 已标注 `@Deprecated`，后续由 `getAdvanceContractArea()` 代替 |

---

## 十四、2.5 版专用字段

### 74. `getProjectDayV2()`

| 维度 | 说明 |
|------|------|
| **方法职责** | 获取 2.5 版工期 |
| **数据来源** | 同 `getProjectDay()` 但无团装特殊处理 |
| **输出 key** | `wanLianGongChengQiXian` |

---

### 75. `getHuXingV2()`

| 维度 | 说明 |
|------|------|
| **方法职责** | 获取原始户型描述 |
| **数据来源** | `projectInfo` 的各房间数量字段 |
| **计算逻辑** | 拼接为"X室X厅X厨X卫X阳X储物间"格式 |
| **输出 key** | `wanLianGongChengHuXing` |

---

### 76. `getProjectContractAddressV2()`

| 维度 | 说明 |
|------|------|
| **方法职责** | 获取 2.5 版房本地址 |
| **输出 key** | `wanLianGongChengShiGongDiDian` |

---

### 77. `getPlanOpenDateV2()`

| 维度 | 说明 |
|------|------|
| **方法职责** | 获取 2.5 版计划开工日期 |
| **输出 key** | `wanLianYuJiKaiGongRiQi` |

---

## 十五、认购/重签相关

### 78. `getSubContractInfoV2()`

| 维度 | 说明 |
|------|------|
| **方法职责** | 获取 2.5 认购合同信息 |
| **数据来源** | `signInfo` + `projectInfo`（金额、地址） |
| **计算逻辑** | 客户信息 + 合同金额大写 + 拼接地址（省-区-小区-楼栋-单元-房号） |
| **输出 key** | `wanLianJiaFangXingMing`、`wanLianJiaFangLianXiFangShi`、`wanLianJiaFangShenFenZhengHao`、`earnestAmount`、`earnestAmountDesc`、`wanLianJiaFangLianXiDiZhi` |

---

### 79. `getLastContractNo()`

| 维度 | 说明 |
|------|------|
| **方法职责** | 获取上一份有效合同编号（2.0 认购重签） |
| **数据来源** | `contractService.getLatestContract()` |
| **计算逻辑** | 查询该订单该合同类型最新合同 |
| **输出 key** | `projectOrderType`（"2.0"）、`contractType`、`lastContractNo` |

---

### 80. `getLastContractNoV2()`

| 维度 | 说明 |
|------|------|
| **方法职责** | 获取上一份合同编号（2.5 版） |
| **计算逻辑** | 调用 `getLastContractNo()` 后覆盖 `projectOrderType` 为 "2.5" |
| **输出 key** | 同上，`projectOrderType` = "2.5" |

---

### 81. `getHaveSignedFormalContractNo()`

| 维度 | 说明 |
|------|------|
| **方法职责** | 获取已签署/作废的正签合同编号（2.0→2.5 迁移场景） |
| **数据来源** | `contractService.getContractList()` 筛选状态为 CANCEL 或 FINISH |
| **计算逻辑** | 取第一个匹配的合同编号 |
| **输出 key** | `lastContractNo`、`contractType` |

---

### 82. `getLatestSignedFormalContractNo()`

| 维度 | 说明 |
|------|------|
| **方法职责** | 获取最新已签署的正签合同编号 |
| **数据来源** | 合并发起→从 `ContractContextHandler.getContext().getContractSubmitCoreList()` 获取；单独发起→从 `contractService` 查询 |
| **计算逻辑** | 合并发起的补充协议从 ThreadLocal 取正签合同编号；单独发起的查数据库取最新已签署 |
| **输出 key** | `latestSignedFormalContractNo` |
| **条件分支** | `MERGE_LAUNCH_SUPPLEMENT` vs 其他 |

---

## 十六、项目基本信息

### 83. `getApplyDate()`

| 维度 | 说明 |
|------|------|
| **方法职责** | 获取申请日期 |
| **计算逻辑** | 取当前日期 |
| **输出 key** | `applyDate` |

---

### 84. `getContractSubmitDate()`

| 维度 | 说明 |
|------|------|
| **方法职责** | 获取合同提交日期（拆分为年/月/日） |
| **计算逻辑** | 从 `Calendar` 取当前年月日 |
| **输出 key** | `submitContractYear`、`submitContractMonth`、`submitContractDay` |

---

### 85. `getProjectOrderId()`

| 维度 | 说明 |
|------|------|
| **方法职责** | 获取项目单号 |
| **输出 key** | `projectOrderId` |

---

### 86. `getEffectiveDate()`

| 维度 | 说明 |
|------|------|
| **方法职责** | 获取协议生效日期 |
| **输出 key** | `effectiveDate` |

---

### 87. `getHouseType()`

| 维度 | 说明 |
|------|------|
| **方法职责** | 获取房屋类型描述 |
| **数据来源** | `projectInfo.getHouseType()` → `HouseTypeEnum.getHouseTypeEnumByCode()` |
| **计算逻辑** | code 转枚举描述，UNKNOWN 则抛异常 |
| **输出 key** | `houseType` |

---

### 88. `getPartRoomRange()`

| 维度 | 说明 |
|------|------|
| **方法职责** | 获取局装房间修改范围 |
| **输出 key** | `partRoomRange` |

---

### 89. `getSecondDrawModeName()`

| 维度 | 说明 |
|------|------|
| **方法职责** | 获取施工图纸设计师姓名 |
| **计算逻辑** | 默认取设计师姓名；施工图纸方式为"附图"（`ATTACH`）时显示"/" |
| **输出 key** | `secondDrawModeName` |
| **条件分支** | `constructionDrawMode=ATTACH` → "/" |

---

### 90. `getDisputeDealMode()`

| 维度 | 说明 |
|------|------|
| **方法职责** | 获取纠纷处理方式 |
| **输出 key** | `disputeDealMode` |

---

### 91. `getBrandListText()`

| 维度 | 说明 |
|------|------|
| **方法职责** | 获取品类列表展示文本 |
| **数据来源** | `businessInfo.getBrandList()` + Apollo 配置品类名称映射 |
| **计算逻辑** | 遍历品类列表，按 a/b/c 编号生成"品类：XX；该品类总金额为：XX（元）"格式文本 |
| **输出 key** | `brandListText` |

---

### 92. `getResblockCustomDecorate()` / `getCustomCabinetBrand()` / `getCustomCabinetDecorate()` / `getRetailBrand()`

| 维度 | 说明 |
|------|------|
| **方法职责** | 获取各类自定义精装/品牌信息 |
| **数据来源** | `projectInfo` 的对应字段 |
| **输出 key** | 分别为 `resblockCustomDecorate`、`customCabinetBrand`、`customCabinetDecorate`、`retailBrand` |

---

## 十七、存管账户

### 93. `getEscrowAccountInfo()`

| 维度 | 说明 |
|------|------|
| **方法职责** | 获取存管账户开户信息 |
| **数据来源** | `ContractContextHandler.getContext().getEscrowInfo()` |
| **计算逻辑** | 解密手机号和证件号；与签约人手机号对比，**仅当不一致时**才输出存管账户信息 |
| **输出 key** | `escrowAccountUserName`、`escrowAccountUserPhone`、`escrowAccountUserIdNo`、`escrowAccountUserIdType` |
| **条件分支** | 存管账户手机号 ≠ 签约人手机号时才输出 |

---

## 十八、补充协议/和解协议

### 94. `getSupplementItemContent()`

| 维度 | 说明 |
|------|------|
| **方法职责** | 获取补充协议条款内容 |
| **数据来源** | `contractReq.getSupplementItemInfo()` |
| **计算逻辑** | 先调用 `contractUnifyService.supplementRequiredCheck()` 校验必填，然后直接取各条款文本 |
| **输出 key** | `constructionRisk`、`partAMethod`、`partBMethod`、`constructionProblem`、`newContent`、`originalContent` |

---

### 95. `getSupplementItemHiddenFlag()`

| 维度 | 说明 |
|------|------|
| **方法职责** | 获取补充协议各条款的显示/隐藏标识 |
| **数据来源** | `supplementItemInfo.getSelectedSupplementItem()` |
| **计算逻辑** | 默认所有段落隐藏（`CommonEnum.YES`）；遍历已选条款，匹配则设为显示（`CommonEnum.NO`） |
| **输出 key** | `houseTransactionFailedTerminationHidden`、`constructionRiskCustomerBearHidden`、`generalScenarioHidden` |
| **条件分支** | 3 种条款类型对应 3 个隐藏标识 |

---

### 96. `getSettlementItemContent()`

| 维度 | 说明 |
|------|------|
| **方法职责** | 获取和解协议条款内容 |
| **数据来源** | `contractReq.getSettlementItemInfo()` |
| **计算逻辑** | 校验问题描述和整改措施必填 |
| **输出 key** | `problem`、`correctiveAction` |

---

## 十九、首期款支付信息

### 97. `getAdvancePaidInfo()`

| 维度 | 说明 |
|------|------|
| **方法职责** | 获取首期款已支付信息 |
| **数据来源** | `contractService.getContractList()` 获取已签署首期款合同编号；`fundInfoService.getFundByOrderIdAndFundType()` 获取已付金额 |
| **计算逻辑** | 筛选已签署状态的首期款合同取编号；资金信息中已付金额为0时显示"/" |
| **输出 key** | `advanceContractNo`、`advancePaidAmount` |

---

## 二十、盖章相关

### 98. `getJiaFangYiFangSealKeyword()`

| 维度 | 说明 |
|------|------|
| **方法职责** | 获取甲方乙方盖章关键字 |
| **数据来源** | `contractCityCompanyConfigService.getConfigByContractType()` → `baseContractPdfCreateService.getJiaFangYiFangSealKeyword()` |
| **计算逻辑** | 根据 formId 委托给 BaseContractPdfCreateService 查询 |

---

## 二十一、团装开放日

### 99. `getGroupOpenDayDesc()`

| 维度 | 说明 |
|------|------|
| **方法职责** | 获取团装开放日配置描述 |
| **数据来源** | `contractApolloConfig.getGroupOpenDayDesc(gbCode)` |
| **输出 key** | `groupOpenDayDesc` |

---

## 二十二、解约协议（委托方法）

以下 8 个方法均委托给 `TerminalContractPdfBuildService` 处理：

| 方法 | 输出 key（推测） |
|------|------|
| `getTerminalSecondPartyCompanyInfo()` | 乙方公司信息 |
| `getTerminalProjectContractAddress()` | 项目地址 |
| `getTerminalSignContractInfo()` | 签约信息 |
| `getTerminalDetailFundInfo()` | 资金明细 |
| `getTerminalTotalFundInfo()` | 资金汇总 |
| `getTerminalRetrieveMaterialDays()` | 取材天数 |
| `getBreachPenaltyAmount()` | 违约金金额 |
| `getTerminalRelationHouseFormalInfo()` | 关联正签合同信息 |

---

## 二十三、空方法

### `get()`

返回空 Map，疑似占位方法或默认实现。

---

## 二十四、私有工具方法汇总

| 方法 | 职责 |
|------|------|
| `getImageUrlByType()` | 根据附件类型从列表中取单个 PDF 并转图片 JSON |
| `getMultipleImageUrlByType()` | 根据附件类型取**多个** PDF 并转图片 JSON（最后一页盖章） |
| `getMultipleImageListByType()` | 同上，返回图片 URL List 而非 JSON |
| `getAdvancePackageId()` | 兼容不同版本取首期款套餐 ID |
| `getAttachConfig()` | 通用附件配置获取（按城市/公司/类型，含默认降级） |
| `getContractBusinessConfig()` | 保修年限配置获取（团装/其他 + 开渠/非开渠兜底） |
| `resolveCustomAttachImageUrl()` | 根据合同类型解析自定义附件的不同字段 |

---

## 总体架构特征

1. **数据域驱动**：所有方法都从 `ContractContextHandler`（ThreadLocal）获取上下文数据，这是一个典型的 ThreadLocal 数据域模式
2. **反射调用**：方法名即为 PDF 模板的插件标识，通过反射将返回的 Map 合并到 PDF 模板变量中
3. **版本演进明显**：大量 `V2` 后缀方法（`xxxV2`）反映了 2.0→2.5 的版本升级，字段命名从英文转为拼音
4. **合同类型分支复杂**：核心差异在合同类型（PACKAGE_FORMAL/ADVANCE/PERSONAL/...）和业务类型（GROUP_DECORATE/HOUSE_CERTIFICATE/REFORM_ALL/...）
5. **安全处理**：敏感信息（手机号、证件号）统一通过 `cipherService` 解密
6. **附件处理模式统一**：PDF → 图片 → PhotoInfo JSON，最后一页盖章是标准模式