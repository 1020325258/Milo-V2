# Ke-RAG 服务能力接入指南

> 贝壳内部知识检索增强服务（RAG）接口参考文档
> 开源项目：https://github.com/LianjiaTech/bella-rag

## 服务概述

Ke-RAG 提供一套**文件解析/知识管理/知识检索增强**的解决方案，主要能力包括：

- 文档结构化解析（PDF/DOC/DOCX/TXT/HTML/CSV/MD/XLSX/XLS）
- 知识索引构建
- 多路召回 + small2big 技术，综合结果可用率 > 85%
- 支持 Contextual RAG，检索准确率提升 20pp+
- 支持文档内图片 OCR 识别

## 认证方式

所有接口使用 Bearer Token 认证：

```
Authorization: Bearer {open_api_key}
```

**Open API Key**：`1a3e3bfa-1a3d-44b1-8485-559f8410a30d`
**签约支付工单知识库的 spaceId**： `be5fb25a-7ce8-4268-a7ac-cc90010bf976`

## 接口列表

### 1. 文件上传

**用途**：上传文件进行索引构建

**接口**：`POST https://openapi-ait.ke.com/v1/files`

**请求示例**：

```bash
curl --location 'https://openapi-ait.ke.com/v1/files' \
--header 'Authorization: Bearer {open_api_key}' \
--form 'file=@"/path/to/file.docx"' \
--form 'purpose="assistants"' \
--form 'metadata="{\"city_list\":[\"全国\"],\"user\":\"1000000029406069\"}"'
```

**参数说明**：

| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| file | File | 是 | 支持：PDF/DOC/DOCX/TXT/HTML/CSV/MD/XLSX/XLS，限制 20M 以内 |
| purpose | String | 是 | 固定值 `"assistants"` |
| metadata | JSON String | 否 | `{"city_list":["全国"], "user":"ucid"}` |

**注意事项**：
- 新接入用户上传文件 ak 默认不走 indexing 逻辑，需提供 ak-code 给李智林（29406069）进行加白
- 文件切片数 > 10w 会解析失败
- CSV 文件仅支持 bella 知识库模版上传

---

### 2. 文件解析进度查询

**用途**：轮询获取文件 indexing 的进度及状态

**接口**：`GET https://openapi-ait.ke.com/v1/files/{file_id}/progress?progress_name=file_indexing`

**请求示例**：

```bash
curl --location 'https://openapi-ait.ke.com/v1/files/{file_id}/progress?progress_name=file_indexing' \
--header 'Authorization: Bearer {open_api_key}'
```

**响应示例**：

```json
{
    "id": 110,
    "file_id": "file-2503041742350024000151-2075695711",
    "name": "file_indexing",
    "status": "generate_embeddings",
    "message": "",
    "percent": 80
}
```

**状态枚举**：

| status | 说明 |
|--------|------|
| queued | 解析排队中 |
| read_file | 文件读取 |
| *_parse | 文件解析 |
| build_recall_index | 索引实体构建 |
| generate_embeddings | 文件向量化 |
| multi_index_construction | 索引构建完成 |
| failed | 解析失败（查看 message 获取原因） |

**完成条件**：`status = multi_index_construction` 且 `percent = 100`

---

### 3. 文件后置处理状态查询

**用途**：查询文件后置处理器（摘要提取、上下文总结）的执行状态

**接口**：`GET https://openapi-ait.ke.com/v1/files/{file_id}/progress?progress_name={post_process_name}`

**后置处理器**：

| 处理器名称 | 说明 |
|------------|------|
| summary_question | 文件摘要提取（当前不对外开放查询） |
| context_summary | 文件背景信息总结，支持结构化文档（PDF/DOCX/DOC/EXCEL） |

**请求示例**：

```bash
curl --location 'https://openapi-ait.ke.com/v1/files/{file_id}/progress?progress_name=context_summary' \
--header 'Authorization: Bearer {open_api_key}'
```

**响应示例**：

```json
{
    "id": 112,
    "file_id": "file-2503041742350024000151-2075695711",
    "name": "context_summary",
    "status": "context_summary",
    "message": "",
    "percent": 100
}
```

---

### 4. 知识检索（Search）

**用途**：根据查询内容检索相关知识片段

**接口**：`POST https://openapi-ait.ke.com/v1/rag/search`

**接口文档**：https://weapons.ke.com/project/20296/interface/api/1850322

**请求示例**：

```bash
curl --location 'https://openapi-ait.ke.com/v1/rag/search' \
--header 'Authorization: Bearer {open_api_key}' \
--header 'Content-Type: application/json' \
--data '{
    "query": "机器学习的主要算法有哪些？",
    "scope": [{"type": "file", "ids": ["file_123", "file_456"]}],
    "limit": 5,
    "user": "user_00000000",
    "mode": "normal"
}'
```

**请求参数**：

| 参数 | 类型 | 必需 | 默认值 | 说明 |
|------|------|------|--------|------|
| query | String | 是 | - | 查询内容 |
| scope | Array | 是 | - | 检索范围，格式：`[{"type":"file","ids":["file_id1","file_id2"]}]` 或 `[{"type":"space","ids":["space_code"]}]` |
| limit | Integer | 否 | 3 | 检索数量 |
| user | String | 是 | - | 使用方 ucid（**必传，影响城市过滤**） |
| mode | String | 否 | - | 检索模式，见下方枚举 |

**检索模式枚举**：

| 模式 | 描述 | 策略配置 |
|------|------|----------|
| `fast` | 轻量搜索：追求速度，精度要求不高 | 语义检索，无重排器，最大补全策略 |
| `normal` | 精准搜索：平衡速度和质量 | 语义检索，有重排器，最大补全策略 |
| `ultra` | 全能搜索：高精度需求，支持图片理解 | 混合检索（向量+关键词），有重排器，上下文补全策略，支持图片内容识别 |

**响应示例**：

```json
{
    "code": 0,
    "message": "Success",
    "data": {
        "total": 10,
        "results": [
            {
                "content": "检索到的内容片段",
                "file_name": "文件名",
                "paths": ["引用信息逻辑位置"]
            }
        ]
    }
}
```

---

### 5. 检索生成增强（Chat）

**用途**：基于检索结果进行智能问答生成

**接口**：`POST https://openapi-ait.ke.com/v1/rag/chat`

**接口文档**：https://weapons.ke.com/project/20296/interface/api/1855163

**请求示例**：

```bash
curl --location 'https://openapi-ait.ke.com/v1/rag/chat' \
--header 'Authorization: Bearer {open_api_key}' \
--header 'Content-Type: application/json' \
--data '{
    "query": "机器学习的主要算法有哪些？",
    "scope": [{"type": "file", "ids": ["file_123", "file_456"]}],
    "user": "user_00000000",
    "response_type": "blocking",
    "timeout": 100,
    "model": "gpt-4o",
    "mode": "deep"
}'
```

**请求参数**：

| 参数 | 类型 | 必需 | 默认值 | 说明 |
|------|------|------|--------|------|
| query | String | 是 | - | 查询内容 |
| scope | Array | 是 | - | 检索范围 |
| user | String | 是 | - | 使用方 ucid |
| response_type | String | 否 | blocking | 响应方式：`blocking`（同步）、`stream`（流式）、`callback`（异步） |
| model | String | 否 | - | 生成模型，如 `gpt-4o` |
| mode | String | 否 | - | 检索模式，见下方枚举 |
| timeout | Integer | 否 | - | 超时时间（秒） |

**检索模式枚举**：

| 模式 | 描述 | 策略配置 |
|------|------|----------|
| `fast` | 轻量搜索 | 语义检索，无重排器，最大补全策略 |
| `normal` | 精准搜索 | 语义检索，有重排器，最大补全策略 |
| `ultra` | 全能搜索 | 混合检索，有重排器，上下文补全策略，支持图片内容识别 |
| `deep` | 智能 agent 搜索 | DeepRAG 模式，plan and solve 执行 pipeline，支持复杂问题分析，多步骤推理，耗时较长 |

**响应示例**（非 deep 模式，非流式）：

```json
{
    "code": 0,
    "message": "Success",
    "data": {
        "content": [
            {
                "type": "text",
                "text": "生成的回答内容"
            }
        ]
    }
}
```

---

## 链路日志查看

支持在请求 header 中传入 `X-BELLA-TRACE-ID` 记录请求链路日志。

**日志查询地址**：https://ait.ke.com/logs/trace

---

## space_code 获取方式

1. **Bella 平台**：空间管理 → 右上角查看空间编码
2. **File API 查询**：

```bash
curl --location --request GET 'https://openapi-ait.ke.com/v1/files/{file_id}' \
--header 'Authorization: Bearer {open_api_key}' \
--header 'Content-Type: application/json'
```

返回参数中的 `space_code` 即为所需值。

---

## 常见问题

**Q: 文档内图片信息是否支持参与检索？**
A: 支持。使用 `ultra` 或 `deep` 模式可进行图片 OCR 内容检索并由模型总结。OCR 识别能力对 2025/03/27 后上传的文档默认生效，存量文档需重新上传。

---

## 典型接入流程

```
1. 上传文件 → 获取 file_id
2. 轮询 file_indexing 进度 → 等待 multi_index_construction + 100%
3. （可选）轮询 context_summary 进度 → 等待 100%
4. 调用 search/chat 接口进行检索或问答
```

---

## 联系方式

- 技术问题：李智林（29406069）
- 白名单申请：提供 ak-code 给李智林
