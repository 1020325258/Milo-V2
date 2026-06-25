# -*- coding: utf-8 -*-
"""合同域枚举定义。

从 contract-data-dictionary/references/ 同步，用于 sre_query 工具自动翻译枚举值。
"""

from .contract_type import CONTRACT_TYPE_ENUM
from .contract_status import CONTRACT_STATUS_ENUM
from .business_type import BUSINESS_TYPE_ENUM
from .role_type import ROLE_TYPE_ENUM
from .node_type import NODE_TYPE_ENUM
from .log_type import LOG_TYPE_ENUM
from .sign_channel_type import SIGN_CHANNEL_TYPE_ENUM
from .user_sign_type import USER_SIGN_TYPE_ENUM
from .audit_type import AUDIT_TYPE_ENUM
from .pdf_generation_mode import PDF_GENERATION_MODE_ENUM
from .certificate_type import CERTIFICATE_TYPE_ENUM
from .bind_type import BIND_TYPE_ENUM
from .contract_object_type import CONTRACT_OBJECT_TYPE_ENUM
from .contract_submit_status import CONTRACT_SUBMIT_STATUS_ENUM
from .contract_auth_status import CONTRACT_AUTH_STATUS_ENUM
from .contract_audit_status import CONTRACT_AUDIT_STATUS_ENUM
from .contract_audit_scene import CONTRACT_AUDIT_SCENE_ENUM
from .contract_attach_veracity import CONTRACT_ATTACH_VERACITY_ENUM
from .seal_status import SEAL_STATUS_ENUM
from .self_seal_status import SELF_SEAL_STATUS_ENUM
from .sign_result import SIGN_RESULT_ENUM
from .sign_scene_type import SIGN_SCENE_TYPE_ENUM
from .process_status import PROCESS_STATUS_ENUM
from .process_node_type import PROCESS_NODE_TYPE_ENUM
from .process_node_status import PROCESS_NODE_STATUS_ENUM
from .free_form_role_type import FREE_FORM_ROLE_TYPE_ENUM
from .person_role_type import PERSON_ROLE_TYPE_ENUM

# 枚举名 -> 枚举值映射的统一注册表
ENUM_REGISTRY = {
    "ContractTypeEnum": CONTRACT_TYPE_ENUM,
    "ContractStatusEnum": CONTRACT_STATUS_ENUM,
    "BusinessTypeEnum": BUSINESS_TYPE_ENUM,
    "RoleTypeEnum": ROLE_TYPE_ENUM,
    "NodeTypeEnum": NODE_TYPE_ENUM,
    "LogTypeEnum": LOG_TYPE_ENUM,
    "SignChannelTypeEnum": SIGN_CHANNEL_TYPE_ENUM,
    "UserSignTypeEnum": USER_SIGN_TYPE_ENUM,
    "AuditTypeEnum": AUDIT_TYPE_ENUM,
    "PdfGenerationModeEnum": PDF_GENERATION_MODE_ENUM,
    "CertificateTypeEnum": CERTIFICATE_TYPE_ENUM,
    "BindTypeEnum": BIND_TYPE_ENUM,
    "ContractObjectTypeEnum": CONTRACT_OBJECT_TYPE_ENUM,
    "ContractSubmitStatusEnum": CONTRACT_SUBMIT_STATUS_ENUM,
    "ContractAuthStatusEnum": CONTRACT_AUTH_STATUS_ENUM,
    "ContractAuditStatusEnum": CONTRACT_AUDIT_STATUS_ENUM,
    "ContractAuditSceneEnum": CONTRACT_AUDIT_SCENE_ENUM,
    "ContractAttachVeracityEnum": CONTRACT_ATTACH_VERACITY_ENUM,
    "SealStatusEnum": SEAL_STATUS_ENUM,
    "SelfSealStatusEnum": SELF_SEAL_STATUS_ENUM,
    "SignResultEnum": SIGN_RESULT_ENUM,
    "SignSceneTypeEnum": SIGN_SCENE_TYPE_ENUM,
    "ProcessStatusEnum": PROCESS_STATUS_ENUM,
    "ProcessNodeTypeEnum": PROCESS_NODE_TYPE_ENUM,
    "ProcessNodeStatusEnum": PROCESS_NODE_STATUS_ENUM,
    "FreeFormRoleTypeEnum": FREE_FORM_ROLE_TYPE_ENUM,
    "PersonRoleTypeEnum": PERSON_ROLE_TYPE_ENUM,
}
