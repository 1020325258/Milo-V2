# -*- coding: utf-8 -*-
"""RAG-related prompt templates for knowledge citation."""

# RAG context format instructions for System Prompt injection
RAG_SYSTEM_PROMPT_TEMPLATE = """
## 知识库上下文

你拥有企业内部知识库的检索结果。请根据以下上下文回答用户问题。

### 使用规则

1. **必须使用知识库内容回答**：优先使用 Document Chunks 中的信息
2. **必须引用来源**：在回答中使用 `[文件名]` 格式标注信息来源
3. **生成引用列表**：在回答末尾生成 `### References` 部分，每个引用占一行
4. **禁止编造**：如果知识库中没有相关信息，明确告知用户

### 引用格式示例

```
根据知识库内容，修改手机号有以下方式 [ContractQAPairs_20260524.md]：
1. 变更签约合同的合同号码
2. 设置代理人新号码

### References

- ContractQAPairs_20260524.md
- ContractQAPairs_20260101.md
```

---

### Document Chunks

```json
{chunks_json}
```
"""


def format_rag_context(chunks: list) -> str:
    """Format retrieved chunks into RAG context for System Prompt injection.

    Args:
        chunks: List of KnowledgeChunk objects.

    Returns:
        Formatted context string with chunks JSON.
    """
    if not chunks:
        return ""

    chunks_data = []
    seen_files = set()

    for chunk in chunks:
        # 为每个文件生成唯一标识
        file_key = chunk.file_name
        if file_key not in seen_files:
            seen_files.add(file_key)
            chunks_data.append({
                "file_name": chunk.file_name,
                "file_id": chunk.file_id,
                "content": chunk.content[:800],
            })

    import json
    chunks_json = json.dumps(chunks_data, ensure_ascii=False, indent=2)

    return RAG_SYSTEM_PROMPT_TEMPLATE.format(chunks_json=chunks_json)
