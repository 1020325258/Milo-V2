# -*- coding: utf-8 -*-
"""SRE 查询接口客户端。

封装对 SreQueryController 的 HTTP 调用。
"""
import logging
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger(__name__)


class SreQueryClient:
    """SRE 查询接口客户端。

    封装对 http://preview.i.nrs-sales-project.home.ke.com/sre/* 接口的调用。
    所有请求都使用 GET 方法，通过 app=sreAgent 进行认证。
    """

    # action 到 API endpoint 的映射
    ENDPOINT_MAP: Dict[str, str] = {
        "decrypt": "/sre/decrypt",
        "contract": "/sre/contract",
        "contract_node": "/sre/contract-node",
        "contract_user": "/sre/contract-user",
        "contract_field": "/sre/contract-field",
        "contract_quotation": "/sre/contract-quotation-relation",
        "config_snap": "/sre/project-config-snap",
        "city_company_info": "/sre/contract-city-company-info",
        "contract_log": "/sre/contract-log",
        "field_config": "/sre/field-config",
        "protocol_config": "/sre/protocol-config",
        "dim_combos": "/sre/field-config-dim-combos",
    }

    def __init__(
        self,
        base_url: str = "http://preview.i.nrs-sales-project.home.ke.com",
        app: str = "sreAgent",
        timeout: float = 30.0,
    ):
        """初始化 SRE 查询客户端。

        Args:
            base_url: SRE 服务的基础 URL。
            app: 认证参数，固定为 "sreAgent"。
            timeout: HTTP 请求超时时间（秒）。
        """
        self.base_url = base_url.rstrip("/")
        self.app = app
        self.client = httpx.AsyncClient(timeout=timeout)

    async def query(
        self,
        action: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """统一查询入口。

        Args:
            action: 操作类型，对应不同的 API endpoint。
            params: 查询参数（不含 app 参数，会自动添加）。

        Returns:
            接口返回的 JSON 数据，格式为 {code, message, data, success}。

        Raises:
            httpx.HTTPStatusError: HTTP 状态码错误。
            httpx.TimeoutException: 请求超时。
        """
        endpoint = self._get_endpoint(action)
        if not endpoint:
            return {
                "code": 400,
                "message": f"未知的操作类型: {action}",
                "data": None,
                "success": False,
            }

        # 构建请求参数，添加认证参数
        request_params = {"app": self.app}
        if params:
            request_params.update(params)

        # 发送请求
        url = f"{self.base_url}{endpoint}"
        logger.info("SRE query: action=%s, url=%s, params=%s", action, url, request_params)

        try:
            response = await self.client.get(url, params=request_params)
            response.raise_for_status()
            return response.json()
        except httpx.TimeoutException:
            logger.error("SRE query timeout: action=%s, url=%s", action, url)
            return {
                "code": 504,
                "message": "查询超时，请稍后重试",
                "data": None,
                "success": False,
            }
        except httpx.HTTPStatusError as e:
            logger.error("SRE query HTTP error: action=%s, status=%s", action, e.response.status_code)
            return {
                "code": e.response.status_code,
                "message": f"HTTP 错误: {e.response.status_code}",
                "data": None,
                "success": False,
            }
        except Exception as e:
            logger.exception("SRE query failed: action=%s", action)
            return {
                "code": 500,
                "message": f"查询异常: {str(e)}",
                "data": None,
                "success": False,
            }

    def _get_endpoint(self, action: str) -> str:
        """映射 action 到 API endpoint。

        Args:
            action: 操作类型。

        Returns:
            API endpoint 路径，如果 action 未知则返回空字符串。
        """
        return self.ENDPOINT_MAP.get(action, "")

    async def close(self):
        """关闭 HTTP 客户端。"""
        await self.client.aclose()
