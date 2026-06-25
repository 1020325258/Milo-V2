"""
工单 QA 问答对生成器

将工单文件中的每个工单问题，梳理为结构化的 QA 问答对。
- Q（问题）：背景信息必须完备，指明在什么场景下发生了什么问题
- A（答案）：具备确定性结论

使用方式:
    cd backend
    python demo/ticket_qa_generator.py
"""

import os
import re
import json
import asyncio
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

try:
    from claude_agent_sdk import query, ClaudeAgentOptions
except ImportError:
    print("[警告] claude_agent_sdk 未安装，将使用 mock 模式")

    class MockClaudeAgentOptions:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    class MockMessage:
        def __init__(self, result: str):
            self.result = result

    async def mock_query(prompt: str, options=None):
        yield MockMessage('{"qa_pairs": [{"question": "mock-question", "answer": "mock-answer"}]}')

    query = mock_query
    ClaudeAgentOptions = MockClaudeAgentOptions


# ============ 配置 ============

TICKET_FILE = Path("/Users/zqy/work/工单分析/签约/全量工单/ContractQAPairs_20260101-20260107.md")
OUTPUT_DIR = Path(__file__).parent

API_CONFIG = {
    "base_url": os.getenv("ANTHROPIC_BASE_URL", "https://token-plan-cn.xiaomimimo.com/anthropic"),
    "auth_token": os.getenv("ANTHROPIC_AUTH_TOKEN", "tp-cxq9g672kqgmcpmgvzhktpk7vucswrn9atq4i4ehwyxc6ngl"),
    "model": os.getenv("ANTHROPIC_MODEL", "mimo-v2.5-pro"),
}

BATCH_SIZE = 1
CONCURRENCY = 5  # 并发数


# ============ 数据模型 ============

@dataclass
class Ticket:
    """单个工单"""
    ticket_id: str
    title: str
    category: str
    issue_type: str
    description: str
    solution: str
    created_at: str = ""


@dataclass
class QAPair:
    """单个问答对"""
    ticket_id: str
    title: str
    category: str
    question: str
    answer: str


# ============ 工单解析 ============

def parse_ticket_file(file_path: Path) -> list[Ticket]:
    """解析工单文件，提取结构化工单数据"""
    content = file_path.read_text(encoding="utf-8")
    tickets = []

    pattern = r'## 【工单问题】(.+?)\n\n(.+?)(?=\n## 【工单问题】|\Z)'
    matches = re.finditer(pattern, content, re.DOTALL)

    for match in matches:
        title = match.group(1).strip()
        block = match.group(2)

        ticket_id = _extract_field(block, r'\*\*工单ID\*\*:\s*(\d+)')
        category = _extract_field(block, r'\*\*分类\*\*:\s*(.+)')
        issue_type = _extract_field(block, r'\*\*问题判定\*\*:\s*(.+)')
        created_at = _extract_field(block, r'\*\*创建时间\*\*:\s*(.+)')

        desc_match = re.search(r'### 问题描述\n\n(.+?)(?=\n###|\Z)', block, re.DOTALL)
        solution_match = re.search(r'### 解决方案\n\n(.+?)(?=\n###|\Z)', block, re.DOTALL)

        description = desc_match.group(1).strip() if desc_match else ""
        solution = solution_match.group(1).strip() if solution_match else ""

        if ticket_id:
            tickets.append(Ticket(
                ticket_id=ticket_id,
                title=title,
                category=category or "",
                issue_type=issue_type or "",
                description=description,
                solution=solution,
                created_at=created_at or "",
            ))

    return tickets


def _extract_field(text: str, pattern: str) -> Optional[str]:
    """从文本中提取字段值"""
    match = re.search(pattern, text)
    return match.group(1).strip() if match else None


# ============ LLM 调用 ============

async def call_llm(prompt: str) -> str:
    """调用 LLM 并返回结果文本"""
    result_text = ""
    async for message in query(
        prompt=prompt,
        options=ClaudeAgentOptions(
            model=API_CONFIG["model"],
            env={
                "ANTHROPIC_BASE_URL": API_CONFIG["base_url"],
                "ANTHROPIC_AUTH_TOKEN": API_CONFIG["auth_token"],
            },
            allowed_tools=[],
            max_turns=3,
        ),
    ):
        if hasattr(message, "result"):
            result_text = message.result
    return result_text


def extract_json(text: str) -> Optional[dict]:
    """从 LLM 返回文本中提取 JSON，支持 markdown 代码块包裹"""
    # 1. 先尝试从 ```json ... ``` 代码块中提取
    code_block = re.search(r'```(?:json)?\s*\n?([\s\S]*?)\n?\s*```', text)
    if code_block:
        try:
            return json.loads(code_block.group(1))
        except json.JSONDecodeError:
            pass

    # 2. 回退：匹配裸 JSON
    json_match = re.search(r'\{[\s\S]*\}', text)
    if json_match:
        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass
    return None


# ============ QA 问答对生成 ============

GENERATE_QA_PROMPT = """你是签约业务知识库专家。请将以下工单梳理为高质量的 QA 问答对，用于 SRE Agent 知识库检索。

## Q（问题）要求

1. **背景信息完备**：必须指明以下要素
   - **业务场景**：在什么业务流程中（如：合同签约、合同变更、实名认证等）
   - **操作上下文**：用户在做什么操作时遇到了问题
   - **具体现象**：发生了什么问题，报错信息或异常表现是什么
   - **系统/环境**：涉及哪个系统或端（如：设计师系统、业主端小程序、圣都家装小程序等）
2. **以用户视角提问**：模拟实际遇到该问题的用户口吻
3. **一个问题对应一个场景**：不要把多个不相关的问题合并

## A（答案）要求

1. **具备确定性结论**：给出明确的解决方案或结论，不要模棱两可
2. **步骤化**：如果涉及操作步骤，按步骤列出（最多 5 步）
3. **包含原因**：简要说明问题产生的根本原因（1-2 句）
4. **可操作性**：答案应让提问者能直接按照执行
5. **精简**：每个答案控制在 150 字以内，避免冗余描述

## 工单列表

{ticket_list}

## 输出格式

严格按以下 JSON 格式输出，不要输出其他内容：
{{
    "qa_pairs": [
        {{
            "ticket_id": "工单ID",
            "question": "梳理后的问题（Q）",
            "answer": "梳理后的答案（A）"
        }},
        ...
    ]
}}
"""


async def generate_batch_qa(batch: list[tuple[int, Ticket]]) -> list[dict]:
    """为一批工单生成 QA 问答对"""
    ticket_lines = []
    for idx, t in batch:
        ticket_lines.append(f"### 工单 {t.ticket_id}: {t.title}")
        ticket_lines.append(f"- 分类: {t.category}")
        ticket_lines.append(f"- 问题判定: {t.issue_type}")
        ticket_lines.append(f"- 创建时间: {t.created_at}")
        ticket_lines.append(f"- 问题描述: {t.description}")
        ticket_lines.append(f"- 解决方案: {t.solution}")
        ticket_lines.append("")

    prompt = GENERATE_QA_PROMPT.format(ticket_list="\n".join(ticket_lines))
    result_text = await call_llm(prompt)
    data = extract_json(result_text)

    if data and "qa_pairs" in data:
        return data["qa_pairs"]
    return []


# ============ 主流程 ============

async def main():
    print("=" * 60)
    print("工单 QA 问答对生成器")
    print(f"工单文件: {TICKET_FILE}")
    print("=" * 60)

    # 1. 读取工单
    if not TICKET_FILE.exists():
        print(f"错误: 工单文件不存在: {TICKET_FILE}")
        return

    all_tickets = parse_ticket_file(TICKET_FILE)
    print(f"\n共解析 {len(all_tickets)} 个工单")

    # 2. 分批生成 QA
    print(f"\n{'=' * 60}")
    print(f"开始生成 QA 问答对（每批 {BATCH_SIZE} 个工单）")
    print("=" * 60)

    indexed_tickets = list(enumerate(all_tickets))
    batches = [
        indexed_tickets[i:i + BATCH_SIZE]
        for i in range(0, len(indexed_tickets), BATCH_SIZE)
    ]
    print(f"共 {len(batches)} 批\n")

    # 逐批处理（带并发控制）
    all_qa_pairs: list[QAPair] = []
    errors = []
    sem = asyncio.Semaphore(CONCURRENCY)
    completed = 0
    total = len(batches)
    lock = asyncio.Lock()

    async def process_batch(batch_idx: int, batch: list[tuple[int, Ticket]]):
        nonlocal completed
        async with sem:
            batch_ids = [t.ticket_id for _, t in batch]
            try:
                results = await generate_batch_qa(batch)

                async with lock:
                    for item in results:
                        tid = item.get("ticket_id", "")
                        question = item.get("question", "")
                        answer = item.get("answer", "")

                        ticket = next((t for _, t in batch if t.ticket_id == tid), None)
                        if tid and question and answer and ticket:
                            all_qa_pairs.append(QAPair(
                                ticket_id=tid,
                                title=ticket.title,
                                category=ticket.category,
                                question=question,
                                answer=answer,
                            ))

                    completed += 1
                    print(f"  [{completed}/{total}] 工单 {batch_ids[0]} → {len(results)} 个 QA", flush=True)
            except Exception as e:
                async with lock:
                    completed += 1
                    errors.append((batch_idx, str(e)))
                    print(f"  [{completed}/{total}] 工单 {batch_ids[0]} → 失败: {e}", flush=True)

    tasks = [process_batch(idx, batch) for idx, batch in enumerate(batches, 1)]
    await asyncio.gather(*tasks)

    # 3. 保存结果
    print(f"\n{'=' * 60}")
    print("保存结果")
    print("=" * 60)

    save_results(all_qa_pairs)
    generate_markdown(all_qa_pairs, all_tickets)

    print(f"\n成功生成: {len(all_qa_pairs)}/{len(all_tickets)} 个 QA 问答对")
    if errors:
        print(f"失败批次: {len(errors)}")

    print(f"\n{'=' * 60}")
    print("完成！")
    print(f"JSON 结果: {OUTPUT_DIR / 'qa_pairs.json'}")
    print(f"Markdown 结果: {OUTPUT_DIR / 'qa_pairs.md'}")


# ============ 保存与输出 ============

def save_results(qa_pairs: list[QAPair]):
    """保存 QA 问答对为 JSON"""
    output_file = OUTPUT_DIR / "qa_pairs.json"
    data = [
        {
            "ticket_id": qa.ticket_id,
            "title": qa.title,
            "category": qa.category,
            "question": qa.question,
            "answer": qa.answer,
        }
        for qa in qa_pairs
    ]
    output_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  JSON 已保存: {output_file}")


def generate_markdown(qa_pairs: list[QAPair], all_tickets: list[Ticket]):
    """生成 Markdown 格式的 QA 文档"""
    lines = []
    lines.append("# 签约工单 QA 问答对")
    lines.append("")
    lines.append(f"> 生成时间: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"> 工单总数: {len(all_tickets)} 个")
    lines.append(f"> 生成 QA 数: {len(qa_pairs)} 个")
    lines.append(f"> 数据来源: {TICKET_FILE.name}")
    lines.append("")

    # 按分类分组
    category_map: dict[str, list[QAPair]] = {}
    for qa in qa_pairs:
        cat = qa.category or "未分类"
        category_map.setdefault(cat, []).append(qa)

    for category, qas in sorted(category_map.items()):
        lines.append(f"## {category}")
        lines.append("")

        for qa in qas:
            lines.append(f"### Q: {qa.question}")
            lines.append("")
            lines.append(f"**工单ID**: {qa.ticket_id}  ")
            lines.append(f"**原始标题**: {qa.title}")
            lines.append("")
            lines.append(f"**A**: {qa.answer}")
            lines.append("")
            lines.append("---")
            lines.append("")

    output_file = OUTPUT_DIR / "qa_pairs.md"
    output_file.write_text("\n".join(lines), encoding="utf-8")
    print(f"  Markdown 已保存: {output_file}")


if __name__ == "__main__":
    asyncio.run(main())
