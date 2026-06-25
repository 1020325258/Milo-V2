# -*- coding: utf-8 -*-
"""日志类型枚举 (LogTypeEnum)。

对应 contract_log.type 字段。
"""

LOG_TYPE_ENUM = {
    1: "STATUS_CHANGE",
    2: "SUBMIT_AUDIT",
    3: "AUDIT_REJECT",
    4: "AUDIT_PASS",
    5: "USER_SIGN",
    6: "USER_CONFIRM",
    7: "COMPANY_SIGN",
    8: "FINISH",
    9: "AUDIT_CREATE_FAIL",
    10: "COMPANY_SIGN_FAIL",
    11: "APPLY_SEAL",
    12: "SUBMIT",
    13: "UNDO_CONTRACT",
    14: "DELETE",
    16: "DATA_SUPPLEMENT",
    17: "CANCEL",
    18: "UNDO_AUDIT",
    19: "THIRD_PART_SEAL",
    20: "WATCH_VIDEO",
    21: "CREATE_PDF_ERROR",
    22: "GET_SIGN_URL_ERROR",
    23: "PREVIEW_PDF",
    24: "CONTRACT_BIND_CHANGE",
    25: "CONTRACT_UNBIND",
}
