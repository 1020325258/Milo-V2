# -*- coding: utf-8 -*-
"""SRE 数据查询 Agent Tool。

职责：封装 SRE 查询接口为 Agent 可调用的工具，处理业务逻辑和格式化。
不直接处理 HTTP 通信，而是委托给 SreQueryClient。
"""
import logging
from typing import Any, Dict

from agentscope.tool import ToolBase
from agentscope.permission import PermissionContext, PermissionDecision, PermissionBehavior
from agentscope.message import TextBlock
from agentscope.tool._response import ToolChunk

from .client import SreQueryClient

logger = logging.getLogger(__name__)


class SreQueryTool(ToolBase):
    """查询 SRE 生产环境数据的统一工具。

    支持能力：
    - decrypt: 解密身份证号、手机号等敏感信息
    - contract: 查询合同信息（按 contract_code 或 project_order_id）
    - contract_node: 查询合同节点
    - contract_user: 查询签约人
    - contract_field: 查询合同扩展字段
    - contract_quotation: 查询签约单据
    - config_snap: 查询配置快照
    - city_company_info: 查询城市公司配置
    - contract_log: 查询合同操作日志
    - field_config: 查询字段配置
    - protocol_config: 查询协议配置
    - dim_combos: 查询维度组合
    """

    name = "sre_query"
    description = (
        "查询 SRE 生产环境数据，用于排查线上问题。"
        "支持查询：合同信息、合同节点、签约人、扩展字段、签约单据、"
        "配置快照、城市公司配置、操作日志、字段配置、协议配置、维度组合。"
        "还支持解密身份证号、手机号等敏感信息。"
        "当需要排查生产环境合同相关问题时使用此工具。"
        "注意：返回数据中的枚举字段（如 type、status、roleType、isSign、nodeType 等）"
        "的含义请参考 contract-data-dictionary 技能中的数据字典。"
    )
    input_schema = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": [
                    "decrypt",
                    "contract",
                    "contract_node",
                    "contract_user",
                    "contract_field",
                    "contract_quotation",
                    "config_snap",
                    "city_company_info",
                    "contract_log",
                    "field_config",
                    "protocol_config",
                    "dim_combos",
                ],
                "description": (
                    "查询操作类型：\n"
                    "- decrypt: 解密敏感信息（身份证号、手机号）\n"
                    "- contract: 查询合同信息（按 contract_code 或 project_order_id）\n"
                    "- contract_node: 查询合同节点\n"
                    "- contract_user: 查询签约人\n"
                    "- contract_field: 查询合同扩展字段\n"
                    "- contract_quotation: 查询签约单据\n"
                    "- config_snap: 查询配置快照\n"
                    "- city_company_info: 查询城市公司配置\n"
                    "- contract_log: 查询合同操作日志\n"
                    "- field_config: 查询字段配置\n"
                    "- protocol_config: 查询协议配置\n"
                    "- dim_combos: 查询维度组合"
                ),
            },
            "contract_code": {
                "type": "string",
                "description": "合同编号（以C开头+数字，如C1776759658764987），contract/contract_node/contract_user/contract_field/contract_quotation/contract_log 时使用",
            },
            "project_order_id": {
                "type": "string",
                "description": "订单号（18位纯数字，如826041310000003912），contract/config_snap 时使用",
            },
            "platform_instance_id": {
                "type": "string",
                "description": "协议平台合同实例id（9位纯数字，如128266249），用于查询协议平台相关数据",
            },
            "encrypted_text": {
                "type": "string",
                "description": "需要解密的密文，decrypt 时使用",
            },
            "log_type": {
                "type": "integer",
                "description": "日志类型（可选），contract_log 时使用",
            },
            "business_type": {
                "type": "integer",
                "description": "业务类型，city_company_info/field_config/dim_combos 时使用",
            },
            "gb_code": {
                "type": "integer",
                "description": "城市code，city_company_info/field_config/dim_combos 时使用",
            },
            "company_code": {
                "type": "string",
                "description": "分公司code，city_company_info/field_config/dim_combos 时使用",
            },
            "version": {
                "type": "integer",
                "description": "版本号，city_company_info/field_config/dim_combos 时使用",
            },
            "contract_type": {
                "type": "integer",
                "description": "合同类型，city_company_info/field_config/dim_combos 时使用",
            },
            "form_id": {
                "type": "integer",
                "description": "版式ID，protocol_config 时使用",
            },
            "page_num": {
                "type": "integer",
                "description": "页码（默认1），field_config 时使用",
            },
            "page_size": {
                "type": "integer",
                "description": "每页大小（默认50），field_config 时使用",
            },
        },
        "required": ["action"],
    }
    is_concurrency_safe = True
    is_read_only = True

    # ── 字段含义映射 ──────────────────────────────────────────────
    # key = "action.field" 或 "field"（通用兜底）
    # value = (中文含义, 枚举类型名或None)
    _FIELD_MEANINGS: Dict[str, tuple] = {
        # ── 通用字段 ──
        "contractCode": ("合同编号", None),
        "delStatus": ("删除标记", None),
        "ctime": ("创建时间", None),
        "mtime": ("更新时间", None),
        # ── contract ──
        "contract.contractNo": ("合同编号", None),
        "contract.businessType": ("业务类型", "BusinessTypeEnum"),
        "contract.projectOrderId": ("订单号", None),
        "contract.type": ("合同类型", "ContractTypeEnum"),
        "contract.status": ("合同状态", "ContractStatusEnum"),
        "contract.pdfGenerationMode": ("PDF生成模式", "PdfGenerationModeEnum"),
        "contract.userQueryStatus": ("用户可见性", None),
        "contract.userConfirmStatus": ("用户确认状态", None),
        "contract.userSignStatus": ("用户签署状态", None),
        "contract.signChannelType": ("签署方式", "SignChannelTypeEnum"),
        "contract.userSignType": ("用户签署方式", "UserSignTypeEnum"),
        "contract.auditType": ("审核类型", "AuditTypeEnum"),
        "contract.amount": ("合同金额", None),
        "contract.relateContractCode": ("关联合同编号", None),
        "contract.platformInstanceId": ("协议平台实例ID", None),
        "contract.errorMessage": ("发起失败信息", None),
        # ── contract_user ──
        "contract_user.roleType": ("用户角色", "RoleTypeEnum"),
        "contract_user.name": ("姓名", None),
        "contract_user.phone": ("手机号(加密)", None),
        "contract_user.isSign": ("是否为签约人", "IsSignEnum"),
        "contract_user.isAuth": ("是否已认证", None),
        "contract_user.certificateType": ("证件类型", "CertificateTypeEnum"),
        "contract_user.certificateNo": ("证件号码(加密)", None),
        # ── contract_node ──
        "contract_node.nodeType": ("节点类型", "NodeTypeEnum"),
        "contract_node.fireTime": ("发生时间戳", None),
        # ── contract_log ──
        "contract_log.type": ("操作类型", "LogTypeEnum"),
        "contract_log.content": ("日志内容", None),
        "contract_log.remark": ("备注", None),
        # ── contract_field ──
        "contract_field.fieldKey": ("字段名称", None),
        "contract_field.fieldValue": ("字段值", None),
        # ── contract_quotation ──
        "contract_quotation.billCode": ("关联单据编号", None),
        "contract_quotation.bindType": ("绑定类型", "BindTypeEnum"),
        "contract_quotation.status": ("关联状态", None),
        # ── city_company_info ──
        "city_company_info.businessType": ("业务类型", "BusinessTypeEnum"),
        "city_company_info.contractType": ("合同类型", "ContractTypeEnum"),
        "city_company_info.signChannelType": ("签署方式", "SignChannelTypeEnum"),
        "city_company_info.auditType": ("审核类型", "AuditTypeEnum"),
        "city_company_info.processMode": ("流程模式", None),
        "city_company_info.formId": ("版式ID", None),
        "city_company_info.version": ("版本号", None),
    }

    def _get_meaning(self, action: str, field_name: str) -> tuple:
        """查询字段含义，返回 (含义, 枚举类型名) 或 None。

        优先匹配 "action.field"，未命中则匹配 "field"（通用兜底）。
        """
        return (
            self._FIELD_MEANINGS.get(f"{action}.{field_name}")
            or self._FIELD_MEANINGS.get(field_name)
        )

    def __init__(self, client: SreQueryClient):
        """初始化 SRE 查询工具。

        Args:
            client: SRE 查询接口客户端。
        """
        self.client = client

    async def check_permissions(
        self,
        tool_input: Dict[str, Any],
        context: PermissionContext,
    ) -> PermissionDecision:
        """检查权限。SRE 查询是只读操作，始终允许。"""
        return PermissionDecision(
            behavior=PermissionBehavior.ALLOW,
            message="SRE query is always allowed (read-only).",
        )

    async def __call__(
        self,
        action: str,
        contract_code: str = "",
        project_order_id: str = "",
        platform_instance_id: str = "",
        encrypted_text: str = "",
        log_type: int = None,
        business_type: int = None,
        gb_code: int = None,
        company_code: str = "",
        version: int = None,
        contract_type: int = None,
        form_id: int = None,
        page_num: int = None,
        page_size: int = None,
        **kwargs: Any,
    ) -> ToolChunk:
        """执行 SRE 查询。

        Args:
            action: 操作类型。
            contract_code: 合同编号（以C开头+数字）。
            project_order_id: 订单号（18位纯数字）。
            platform_instance_id: 协议平台合同实例id（9位纯数字）。
            encrypted_text: 需要解密的密文。
            log_type: 日志类型。
            business_type: 业务类型。
            gb_code: 城市code。
            company_code: 分公司code。
            version: 版本号。
            contract_type: 合同类型。
            form_id: 版式ID（6位纯数字）。
            page_num: 页码。
            page_size: 每页大小。

        Returns:
            ToolChunk with formatted query results.
        """
        try:
            # 验证参数
            validation_error = self._validate_params(
                action, contract_code, project_order_id, platform_instance_id,
                encrypted_text, form_id, business_type, gb_code, company_code,
                version, contract_type,
            )
            if validation_error:
                return self._error_response(validation_error)

            # 构建查询参数
            params = self._build_params(
                action, contract_code, project_order_id, platform_instance_id,
                encrypted_text, log_type, business_type, gb_code, company_code,
                version, contract_type, form_id, page_num, page_size,
            )

            # 执行查询
            response = await self.client.query(action, params)

            # 处理返回结果
            return self._format_response(action, response)

        except Exception as e:
            logger.exception("SreQueryTool failed: action=%s", action)
            return self._error_response(f"查询异常: {str(e)}")

    def _validate_params(
        self,
        action: str,
        contract_code: str,
        project_order_id: str,
        platform_instance_id: str,
        encrypted_text: str,
        form_id: int,
        business_type: int,
        gb_code: int,
        company_code: str,
        version: int,
        contract_type: int,
    ) -> str:
        """验证参数，返回错误消息或空字符串。"""
        if not action:
            return "缺少必需参数: action"

        # 根据 action 验证必需参数
        if action == "decrypt":
            if not encrypted_text:
                return "decrypt 操作需要 encrypted_text 参数"

        elif action == "contract":
            if not contract_code and not project_order_id:
                return "contract 操作需要 contract_code 或 project_order_id 参数（合同号以C开头，订单号为18位数字）"

        elif action in ("contract_node", "contract_user", "contract_field", "contract_quotation", "contract_log"):
            if not contract_code:
                return f"{action} 操作需要 contract_code 参数（合同号以C开头，如C1776759658764987）"

        elif action == "config_snap":
            if not project_order_id:
                return "config_snap 操作需要 project_order_id 参数（18位纯数字订单号）"

        elif action == "city_company_info":
            missing = []
            if business_type is None:
                missing.append("business_type")
            if gb_code is None:
                missing.append("gb_code")
            if not company_code:
                missing.append("company_code")
            if version is None:
                missing.append("version")
            if contract_type is None:
                missing.append("contract_type")
            if missing:
                return f"city_company_info 操作需要以下参数: {', '.join(missing)}"

        elif action == "protocol_config":
            if form_id is None and not platform_instance_id:
                return "protocol_config 操作需要 form_id 或 platform_instance_id 参数"

        elif action not in ("field_config", "dim_combos"):
            return f"未知的操作类型: {action}"

        return ""

    def _build_params(
        self,
        action: str,
        contract_code: str,
        project_order_id: str,
        platform_instance_id: str,
        encrypted_text: str,
        log_type: int,
        business_type: int,
        gb_code: int,
        company_code: str,
        version: int,
        contract_type: int,
        form_id: int,
        page_num: int,
        page_size: int,
    ) -> Dict[str, Any]:
        """构建查询参数。"""
        params = {}

        if action == "decrypt":
            params["text"] = encrypted_text

        elif action == "contract":
            if contract_code:
                params["contractCode"] = contract_code
            if project_order_id:
                params["projectOrderId"] = project_order_id

        elif action in ("contract_node", "contract_user", "contract_field", "contract_quotation", "contract_log"):
            params["contractCode"] = contract_code
            if action == "contract_log" and log_type is not None:
                params["type"] = log_type

        elif action == "config_snap":
            params["projectOrderId"] = project_order_id

        elif action == "city_company_info":
            params["businessType"] = business_type
            params["gbCode"] = gb_code
            params["companyCode"] = company_code
            params["version"] = version
            params["type"] = contract_type

        elif action == "field_config":
            if business_type is not None:
                params["businessType"] = business_type
            if gb_code is not None:
                params["gbcode"] = gb_code
            if company_code:
                params["companyCode"] = company_code
            if contract_type is not None:
                params["contractType"] = contract_type
            if version is not None:
                params["version"] = version
            if page_num is not None:
                params["pageNum"] = page_num
            if page_size is not None:
                params["pageSize"] = page_size

        elif action == "protocol_config":
            if form_id is not None:
                params["formId"] = form_id
            if platform_instance_id:
                params["platformInstanceId"] = platform_instance_id

        elif action == "dim_combos":
            if business_type is not None:
                params["businessType"] = business_type
            if gb_code is not None:
                params["gbcode"] = gb_code
            if company_code:
                params["companyCode"] = company_code
            if contract_type is not None:
                params["contractType"] = contract_type
            if version is not None:
                params["version"] = version

        return params

    def _format_response(self, action: str, response: Dict[str, Any]) -> ToolChunk:
        """格式化查询结果。"""
        # 检查接口返回状态
        if not response.get("success"):
            message = response.get("message", "查询失败")
            return self._error_response(message)

        data = response.get("data")

        # 查询结果为空
        if data is None:
            return self._info_response("查询结果为空")

        # 根据 action 格式化数据
        if action == "decrypt":
            return self._format_decrypt(data)
        elif action == "contract":
            return self._format_contract(action, data)
        elif action == "contract_node":
            return self._format_contract_node(action, data)
        elif action == "contract_user":
            return self._format_contract_user(action, data)
        elif action == "contract_field":
            return self._format_contract_field(action, data)
        elif action == "contract_quotation":
            return self._format_contract_quotation(action, data)
        elif action == "config_snap":
            return self._format_config_snap(action, data)
        elif action == "city_company_info":
            return self._format_city_company_info(action, data)
        elif action == "contract_log":
            return self._format_contract_log(action, data)
        elif action == "field_config":
            return self._format_field_config(action, data)
        elif action == "protocol_config":
            return self._format_protocol_config(action, data)
        elif action == "dim_combos":
            return self._format_dim_combos(action, data)
        else:
            return self._format_generic(data)

    # ── 格式化方法 ──────────────────────────────────────────────

    def _format_decrypt(self, data: Any) -> ToolChunk:
        """格式化解密结果。"""
        return ToolChunk(
            content=[TextBlock(id="sre_result", text=f"## 解密结果\n\n{data}")]
        )

    def _format_contract(self, action: str, data: Any) -> ToolChunk:
        """格式化合同信息。"""
        if isinstance(data, list):
            return self._format_list(action, data, "合同列表")
        return self._format_object(action, data, "合同信息")

    def _format_contract_node(self, action: str, data: Any) -> ToolChunk:
        """格式化合同节点。"""
        if isinstance(data, list):
            return self._format_list(action, data, "合同节点")
        return self._format_object(action, data, "合同节点")

    def _format_contract_user(self, action: str, data: Any) -> ToolChunk:
        """格式化签约人。"""
        if isinstance(data, list):
            return self._format_list(action, data, "签约人")
        return self._format_object(action, data, "签约人")

    def _format_contract_field(self, action: str, data: Any) -> ToolChunk:
        """格式化合同扩展字段。"""
        if isinstance(data, dict):
            lines = ["## 合同扩展字段\n"]
            lines.append("| 字段 | 值 | 含义 |")
            lines.append("|------|-----|------|")
            for key, value in data.items():
                meaning = self._get_meaning(action, key)
                col3 = meaning[0] if meaning else "-"
                lines.append(f"| {key} | {value} | {col3} |")
            return ToolChunk(
                content=[TextBlock(id="sre_result", text="\n".join(lines))]
            )
        return self._format_generic(data)

    def _format_contract_quotation(self, action: str, data: Any) -> ToolChunk:
        """格式化签约单据。"""
        if isinstance(data, list):
            return self._format_list(action, data, "签约单据")
        return self._format_object(action, data, "签约单据")

    def _format_config_snap(self, action: str, data: Any) -> ToolChunk:
        """格式化配置快照。"""
        return self._format_object(action, data, "配置快照")

    def _format_city_company_info(self, action: str, data: Any) -> ToolChunk:
        """格式化城市公司配置。"""
        if isinstance(data, list):
            return self._format_list(action, data, "城市公司配置")
        return self._format_object(action, data, "城市公司配置")

    def _format_contract_log(self, action: str, data: Any) -> ToolChunk:
        """格式化合同操作日志。"""
        if isinstance(data, list):
            return self._format_list(action, data, "合同操作日志")
        return self._format_object(action, data, "合同操作日志")

    def _format_field_config(self, action: str, data: Any) -> ToolChunk:
        """格式化字段配置。"""
        if isinstance(data, dict) and "list" in data:
            return self._format_list(action, data["list"], "字段配置")
        if isinstance(data, list):
            return self._format_list(action, data, "字段配置")
        return self._format_object(action, data, "字段配置")

    def _format_protocol_config(self, action: str, data: Any) -> ToolChunk:
        """格式化协议配置。"""
        if isinstance(data, list):
            return self._format_list(action, data, "协议配置")
        return self._format_object(action, data, "协议配置")

    def _format_dim_combos(self, action: str, data: Any) -> ToolChunk:
        """格式化维度组合。"""
        if isinstance(data, list):
            return self._format_list(action, data, "维度组合")
        return self._format_object(action, data, "维度组合")

    def _format_object(self, action: str, obj: Dict[str, Any], title: str) -> ToolChunk:
        """格式化单个对象为 Markdown 表格，含字段含义列。"""
        if not isinstance(obj, dict):
            return self._format_generic(obj)

        lines = [f"## {title}\n"]
        lines.append("| 字段 | 值 | 含义 |")
        lines.append("|------|-----|------|")
        for key, value in obj.items():
            # 截断过长的值
            str_value = str(value)
            if len(str_value) > 200:
                str_value = str_value[:200] + "..."
            # 查字段含义
            meaning = self._get_meaning(action, key)
            if meaning:
                desc, enum_name = meaning
                col3 = f"{desc} (见 {enum_name})" if enum_name else desc
            else:
                col3 = "-"
            lines.append(f"| {key} | {str_value} | {col3} |")

        return ToolChunk(
            content=[TextBlock(id="sre_result", text="\n".join(lines))]
        )

    def _format_list(self, action: str, items: list, title: str) -> ToolChunk:
        """格式化列表为 Markdown 表格，含字段含义行。"""
        if not items:
            return self._info_response(f"{title}为空")

        # 如果是字典列表，使用表格格式
        if isinstance(items[0], dict):
            keys = list(items[0].keys())
            lines = [f"## {title}\n"]
            lines.append(f"| {' | '.join(keys)} |")
            lines.append(f"| {' | '.join(['---'] * len(keys))} |")
            # 含义行
            meanings = []
            for key in keys:
                meaning = self._get_meaning(action, key)
                if meaning:
                    desc, enum_name = meaning
                    cell = f"{desc}(见 {enum_name})" if enum_name else desc
                else:
                    cell = ""
                meanings.append(cell)
            lines.append(f"| {' | '.join(meanings)} |")

            for item in items:
                values = []
                for key in keys:
                    str_value = str(item.get(key, ""))
                    if len(str_value) > 100:
                        str_value = str_value[:100] + "..."
                    values.append(str_value)
                lines.append(f"| {' | '.join(values)} |")

            return ToolChunk(
                content=[TextBlock(id="sre_result", text="\n".join(lines))]
            )

        # 其他类型直接展示
        return self._format_generic(items)

    def _format_generic(self, data: Any) -> ToolChunk:
        """通用格式化。"""
        text = f"## 查询结果\n\n```json\n{data}\n```"
        return ToolChunk(
            content=[TextBlock(id="sre_result", text=text)]
        )

    # ── 响应格式化 ─────────────────────────────────────────────

    @staticmethod
    def _error_response(message: str) -> ToolChunk:
        return ToolChunk(
            content=[TextBlock(id="sre_error", text=f"❌ {message}")]
        )

    @staticmethod
    def _info_response(message: str) -> ToolChunk:
        return ToolChunk(
            content=[TextBlock(id="sre_info", text=f"ℹ️ {message}")]
        )
