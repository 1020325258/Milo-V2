# -*- coding: utf-8 -*-
"""节点类型枚举 (NodeTypeEnum)。

对应 contract_node.nodeType 字段。
"""

NODE_TYPE_ENUM = {
    1: "CREATE",
    2: "SUBMIT",
    3: "LATEST_AUDIT_CREATE",
    4: "LATEST_AUDIT_PASS",
    5: "USER_CONFIRM",
    6: "APPLY_SEAL",
    7: "USER_SIGN",
    8: "COMPANY_SIGN",
    9: "FINISH",
    10: "DELETE",
    11: "LATEST_AUDIT_REJECT",
    12: "DATA_SUPPLEMENT_TIME",
    13: "CANCEL",
    14: "USER_CONFIRM_SIGN_MIX_TIME",
    15: "AUTH",
}
