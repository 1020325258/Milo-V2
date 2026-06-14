# 日志类型枚举 (LogTypeEnum)

用于 contract_log 表的 type 字段。

| code | 名称 | 说明 |
|------|------|------|
| 1 | STATUS_CHANGE | 状态变更 |
| 2 | SUBMIT_AUDIT | 提交审核 |
| 3 | AUDIT_REJECT | 审核驳回 |
| 4 | AUDIT_PASS | 审核通过 |
| 5 | USER_SIGN | 签约人签署 |
| 6 | USER_CONFIRM | 用户确认 |
| 7 | COMPANY_SIGN | 盖公司章 |
| 8 | FINISH | 完成 |
| 9 | AUDIT_CREATE_FAIL | 发起审核失败 |
| 10 | COMPANY_SIGN_FAIL | 盖公司章失败 |
| 11 | APPLY_SEAL | 申请用章 |
| 12 | SUBMIT | 发起签约 |
| 13 | UNDO_CONTRACT | 撤销签约 |
| 14 | DELETE | 删除 |
| 16 | DATA_SUPPLEMENT | 房屋资料上传完毕 |
| 17 | CANCEL | 操作合同取消 |
| 18 | UNDO_AUDIT | 审核撤销 |
| 19 | THIRD_PART_SEAL | 盖第三方章 |
| 20 | WATCH_VIDEO | 观看视频 |
| 21 | CREATE_PDF_ERROR | 生成 PDF 异常 |
| 22 | GET_SIGN_URL_ERROR | 获取手签异常 |
| 23 | PREVIEW_PDF | 预览合同 |
| 24 | CONTRACT_BIND_CHANGE | 合同换绑 |
| 25 | CONTRACT_UNBIND | 合同解绑 |