# 合同扩展字段定义 (ContractFieldEnum)

`sre_query(action="contract_field")` 返回的 fieldKey 对应以下定义。

## fieldType=1：企业签约信息

| fieldKey | 含义 | 取值说明 |
|----------|------|----------|
| legalPhone | 法定代表人手机号（加密） | |
| legalCertificateType | 法定代表人证件类型 | 见「证件类型枚举」 |
| legalName | 法定代表人姓名 | |
| legalCertificateNo | 法定代表人证件号码（加密） | |
| companyName | 甲方公司名称 | |
| companyCreditCode | 甲方公司统一社会信用代码 | |
| companyAgentName | 甲方公司经办人姓名 | |
| companyAgentPhone | 甲方公司经办人手机号（加密） | |
| companyAgentCertificateType | 甲方公司经办人证件类型 | 见「证件类型枚举」 |
| companyAgentCertificateNo | 甲方公司经办人证件号码（加密） | |
| **signRole** | **甲方公司签约人** | **3=公司代办人 4=法定代表人** |

## fieldType=2：房屋信息

| fieldKey | 含义 |
|----------|------|
| resblockName / resblockId | 小区名称 / 编码 |
| districtName / districtId | 行政区名称 / 编码 |
| gbName / gbCode | 城市名称 / 编码 |
| buildingName / buildingId | 楼栋名称 / 编码 |
| unitName / unitId | 单元名称 / 编码 |
| floorName / floorId | 楼层名称 / 编码 |
| houseName / houseId | 门牌号名称 / 编码 |
| houseCertificateAddress | 房本地址 |
| houseCertificateNo | 房产证编号 |
| area | 建筑面积 |
| houseType | 房屋类型：0=未知 1=新房 2=老房 |
| houseBuildType | 户型结构：0=未知 1=复式 2=平层 3=跃层 4=错层 5=LOFT 6=跃复一体 7=排屋 8=别墅 9=自建房 |
| structure | 住宅结构：1=砖结构 2=砖混结构 3=钢筋混凝土框架结构 4=钢筋混凝土核心筒剪力墙结构 5=其他 |
| parlorCnt / roomCnt / cookroomCnt / toiletCnt / balconyCnt / storageCnt | 客厅/卧室/厨房/卫生间/阳台/储物间 数量 |

## fieldType=3：承包约定信息

| fieldKey | 含义 | 取值说明 |
|----------|------|----------|
| projectContractModeCode | 工程承包方式 | 0=未知 1=乙方包工包料 2=乙方包工部分包料 3=乙方包工甲方包料 |
| constructionDrawMode | 施工图纸方式 | 1=甲方自行设计 2=签订设计服务协议 3=未签订 |
| needDesignerAmount | 是否约定设计费 | 0=不在正签合同约定 1=在正签合同中约定 |
| clearDay | 甲方提供施工条件的时间 | |
| beforeDeliveryDaysToWork | 提前通知开工天数 | |

## fieldType=4：签约信息

| fieldKey | 含义 | 取值说明 |
|----------|------|----------|
| contractObjectType | 主体类型 | 1=个人合同 2=公对公合同 |
| businessType | 业务类型 | 见「业务类型枚举」 |
| signChannelType | 签约形式 | 1=线上签约 2=线下补录 |
| userSignType | 签署方式 | 1=协议确认 2=正式签署 |
| userSignTime | 用户签约时间 | |
| companySignTime | 公司签署时间 | |
| unitedCompanyName | 乙方公司名称 | |

## fieldType=5：工期信息

| fieldKey | 含义 |
|----------|------|
| planStartTime | 计划开工日期 |
| totalDuration / totalPeriod | 总工期 |

## fieldType=6：个人签约信息

| fieldKey | 含义 |
|----------|------|
| houseOwnerName / ownerName | 房屋产权人 / 产权人姓名 |
| ownerPhone | 产权人手机号（加密） |
| ownerCertificateType | 产权人证件类型 |
| ownerCertificateNo | 产权人证件号码（加密） |
| haveAgent | 是否有代理人：0=没有 1=有 |
| agentName / agentPhone | 代理人姓名 / 手机号（加密） |
| agentCertificateType / agentCertificateNo | 代理人证件类型 / 号码（加密） |
| contractSignName / contractSignPhone | 合同签约人姓名 / 手机号（加密） |

## fieldType=7：设计师信息

| fieldKey | 含义 |
|----------|------|
| designerName | 设计师姓名 |
| designerUcId | 设计师系统号 |

## fieldType=8：税率信息

| fieldKey | 含义 |
|----------|------|
| taxRate | 发票税率 |

## fieldType=9：纠纷处理

| fieldKey | 含义 | 取值说明 |
|----------|------|----------|
| disputeDealMode | 纠纷处理方式 | 1=提交杭州仲裁委员会仲裁 2=依法向人民法院起诉 |

## fieldType=10：甲供清单

| fieldKey | 含义 |
|----------|------|
| materialList | 甲供材料清单 |

## fieldType=11：报价信息

| fieldKey | 含义 |
|----------|------|
| comboName | 所选套餐 |
| pricingArea | 计价面积 |
| houseLayout | 改后户型 |
| quotePrice | 正签/正式套餐合同报价总金额 |
| personalTotalPrice | 定软电品类报价总金额 |
| contractPriceTotal | 正签/正式套餐合同总金额 |

## fieldType=12：收款计划

| fieldKey | 含义 |
|----------|------|
| collectionPlanConfigInfo | 工程款/合同款收款计划 |