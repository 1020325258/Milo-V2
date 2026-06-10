# -*- coding: utf-8 -*-
"""RAG-related prompt templates for knowledge citation."""

# RAG context format instructions for System Prompt injection
RAG_SYSTEM_PROMPT_TEMPLATE = """
## 知识库上下文

你拥有企业内部知识库的检索结果。请根据以下上下文回答用户问题。

### 使用规则

1. **必须使用知识库内容回答**：优先使用 Document Chunks 中的信息
2. **必须引用来源**：在回答中使用 `[chunk-xxx]` 格式标注信息来源
3. **生成引用列表**：在回答末尾生成 `### References` 部分
4. **禁止编造**：如果知识库中没有相关信息，明确告知用户

### 引用格式示例

```
根据知识库内容，修改手机号有以下方式 [chunk-001]：
1. 变更签约合同的合同号码
2. 设置代理人新号码

### References

- [chunk-001] ContractQAPairs_20260524.md
- [chunk-002] ContractQAPairs_20260101.md
```

---

### Document Chunks

```json
{chunks_json}
```

### Reference Document List

```
{reference_list}
```
"""


def format_rag_context(chunks: list) -> str:
    """Format retrieved chunks into RAG context for System Prompt injection.

    Args:
        chunks: List of KnowledgeChunk objects.

    Returns:
        Formatted context string with chunks JSON and reference list.
    """
    if not chunks:
        return ""

    chunks_data = []
    ref_list = []

    for i, chunk in enumerate(chunks):
        ref_id = f"chunk-{i+1:03d}"
        chunks_data.append({
            "reference_id": ref_id,
            "content": chunk.content[:800],  # 限制每条长度
        })
        ref_list.append(f"[{ref_id}] {chunk.file_name}")

    import json
    chunks_json = json.dumps(chunks_data, ensure_ascii=False, indent=2)
    reference_list = "\n".join(ref_list)

    return RAG_SYSTEM_PROMPT_TEMPLATE.format(
        chunks_json=chunks_json,
        reference_list=reference_list,
    )
