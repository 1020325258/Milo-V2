# 节点类型枚举 (NodeTypeEnum)

用于 contract_node 表的 nodeType 字段，记录合同流转的时间节点。

| code | 名称 | 说明 |
|------|------|------|
| 1 | CREATE | 合同创建时间 |
| 2 | SUBMIT | 发起合同时间 |
| 3 | LATEST_AUDIT_CREATE | 最新提交审核时间 |
| 4 | LATEST_AUDIT_PASS | 最新审核通过时间 |
| 5 | USER_CONFIRM | 用户确认时间 |
| 6 | APPLY_SEAL | 申请用章时间 |
| 7 | USER_SIGN | 用户签署完成时间 |
| 8 | COMPANY_SIGN | 盖公司章时间 |
| 9 | FINISH | 最终完成时间 |
| 10 | DELETE | 作废时间 |
| 11 | LATEST_AUDIT_REJECT | 最新审核驳回时间 |
| 12 | DATA_SUPPLEMENT_TIME | 房屋资料上传完毕时间 |
| 13 | CANCEL | 合同已取消时间 |
| 14 | USER_CONFIRM_SIGN_MIX_TIME | 用户确认/签署时间（虚拟节点） |
| 15 | AUTH | 授权时间 |