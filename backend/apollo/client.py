# -*- coding: utf-8 -*-
"""Apollo OpenAPI HTTP 客户端。

职责：封装 Apollo OpenAPI 的 HTTP 调用细节，返回原始数据。
参考实现：com.yycome.sreagent.infrastructure.gateway.ontology.ApolloConfigGateway

Apollo OpenAPI 端点：
- 查询单个配置项：GET /openapi/v1/envs/{env}/apps/{appId}/clusters/{cluster}/namespaces/{ns}/items/{key}
- 查询 namespace 下所有配置：GET /openapi/v1/envs/{env}/apps/{appId}/clusters/{cluster}/namespaces/{ns}/items
- 查询 release 信息：GET /openapi/v1/envs/{env}/apps/{appId}/clusters/{cluster}/namespaces/{ns}/releases/latest
"""
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class ApolloClient:
    """Apollo OpenAPI HTTP 客户端。

    只负责 HTTP 通信，不包含业务逻辑。
    """

    def __init__(
        self,
        base_url: str = "http://apollo.portal.life.ke.com",
        token: str = "",
        timeout: float = 10.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout

    async def get_item(
        self, env: str, app_id: str, cluster: str, namespace: str, key: str,
    ) -> dict[str, Any] | None:
        """查询单个配置项。

        Returns:
            Apollo 响应 dict（含 key, value, comment 等），不存在返回 None。
        """
        url = (
            f"{self.base_url}/openapi/v1/envs/{env}/apps/{app_id}"
            f"/clusters/{cluster}/namespaces/{namespace}/items/{key}"
        )
        return await self._get(url)

    async def list_items(
        self, env: str, app_id: str, cluster: str, namespace: str,
    ) -> list[dict[str, Any]] | None:
        """列出 namespace 下所有配置项。

        Returns:
            配置项列表，每个元素含 key, value, comment 等。
        """
        url = (
            f"{self.base_url}/openapi/v1/envs/{env}/apps/{app_id}"
            f"/clusters/{cluster}/namespaces/{namespace}/items"
        )
        return await self._get(url)

    async def get_latest_release(
        self, env: str, app_id: str, cluster: str, namespace: str,
    ) -> dict[str, Any] | None:
        """查询 namespace 最新 release 信息。

        Returns:
            Release 信息 dict（含 releaseTime, comment, configurations 等）。
        """
        url = (
            f"{self.base_url}/openapi/v1/envs/{env}/apps/{app_id}"
            f"/clusters/{cluster}/namespaces/{namespace}/releases/latest"
        )
        return await self._get(url)

    async def _get(self, url: str) -> Any:
        """发送 GET 请求。

        Returns:
            响应 JSON，404 或非 200 返回 None。
        """
        headers = {"Content-Type": "application/json;charset=UTF-8"}
        if self.token:
            headers["Authorization"] = self.token

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(url, headers=headers)

            if response.status_code == 404:
                logger.info("Apollo resource not found: %s", url)
                return None

            if response.status_code != 200:
                logger.warning(
                    "Apollo API error: status=%d, url=%s, body=%s",
                    response.status_code, url, response.text[:500],
                )
                return None

            return response.json()
