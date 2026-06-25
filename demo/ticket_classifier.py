"""
工单业务场景提取器（多进程版）

每个 .md 文件启动一个子进程并行处理，主进程聚合后归一化+聚类。

使用方式:
    cd backend
    python demo/ticket_classifier.py
"""

import os
import re
import json
import asyncio
from pathlib import Path
from dataclasses import dataclass, asdict
from collections import Counter
from typing import Optional
from multiprocessing import Pool

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
        yield MockMessage('{"scenarios": ["mock-场景A", "mock-场景B"]}')

    query = mock_query
    ClaudeAgentOptions = MockClaudeAgentOptions


# ============ 配置 ============

TICKET_DIR = Path("/Users/zqy/work/工单分析/签约/全量工单_test")
OUTPUT_DIR = Path(__file__).parent

API_CONFIG = {
    "base_url": os.getenv("ANTHROPIC_BASE_URL", "https://token-plan-cn.xiaomimimo.com/anthropic"),
    "auth_token": os.getenv("ANTHROPIC_AUTH_TOKEN", "tp-cxq9g672kqgmcpmgvzhktpk7vucswrn9atq4i4ehwyxc6ngl"),
    "model": os.getenv("ANTHROPIC_MODEL", "mimo-v2.5-pro"),
}

BATCH_SIZE = 5


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


# ============ 工单解析 ============

def parse_ticket_file(file_path: Path) -> list[Ticket]:
    """解析单个工单文件"""
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
                description=description[:500],
                solution=solution[:500],
                created_at=created_at or "",
            ))

    return tickets


def _extract_field(text: str, pattern: str) -> Optional[str]:
    """提取字段值"""
    match = re.search(pattern, text)
    return match.group(1).strip() if match else None


# ============ LLM 调用 ============

async def call_llm(prompt: str) -> str:
    """调用 LLM"""
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
    """从文本中提取 JSON"""
    json_match = re.search(r'\{[\s\S]*\}', text)
    if json_match:
        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass
    return None


# ============ 场景提取 ============

EXTRACT_SCENARIOS_PROMPT = """你是签约业务工单分析专家。请分析以下工单，提取每条工单涉及的**业务场景**。

## 要求

- 业务场景要**具体到功能点级别**，如"合同变更-修改手机号"、"签约-人脸识别"、"签约-房本上传"
- 不要用"操作咨询"、"系统问题"等笼统分类
- 每条工单可以有 1-3 个业务场景
- 场景命名格式：**业务模块-具体功能点**（如：合同创建-客源校验、合同签署-业主端展示）

## 工单列表

{ticket_list}

## 输出格式

严格按以下 JSON 格式输出，不要输出其他内容：
{{
    "results": [
        {{"ticket_id": "工单ID", "scenarios": ["场景1", "场景2"]}},
        ...
    ]
}}
"""


async def extract_batch_scenarios(batch: list[Ticket]) -> list[dict]:
    """提取一批工单的业务场景"""
    ticket_lines = []
    for t in batch:
        ticket_lines.append(f"### 工单 {t.ticket_id}: {t.title}")
        ticket_lines.append(f"- 原始分类: {t.category}")
        ticket_lines.append(f"- 问题描述: {t.description[:300]}")
        ticket_lines.append(f"- 解决方案: {t.solution[:200]}")
        ticket_lines.append("")

    prompt = EXTRACT_SCENARIOS_PROMPT.format(ticket_list="\n".join(ticket_lines))
    result_text = await call_llm(prompt)
    data = extract_json(result_text)

    if data and "results" in data:
        return data["results"]
    return []


# ============ 子进程处理单个文件 ============

def process_single_file(file_path_str: str) -> dict:
    """子进程入口：处理单个 .md 文件的所有工单，返回 {ticket_id: [scenarios]}"""
    file_path = Path(file_path_str)
    file_name = file_path.name

    async def _run():
        tickets = parse_ticket_file(file_path)
        if not tickets:
            return {}

        print(f"  [{file_name}] 解析到 {len(tickets)} 个工单，开始提取场景...", flush=True)

        ticket_scenarios = {}

        # 分批处理
        for i in range(0, len(tickets), BATCH_SIZE):
            batch = tickets[i:i + BATCH_SIZE]
            batch_num = i // BATCH_SIZE + 1
            total_batches = (len(tickets) + BATCH_SIZE - 1) // BATCH_SIZE

            try:
                results = await extract_batch_scenarios(batch)
                for item in results:
                    tid = item.get("ticket_id", "")
                    scenarios = item.get("scenarios", [])
                    if tid and scenarios:
                        ticket_scenarios[tid] = scenarios

                matched = sum(1 for t in batch if t.ticket_id in ticket_scenarios)
                print(f"  [{file_name}] 批次 {batch_num}/{total_batches} → {matched}/{len(batch)}", flush=True)
            except Exception as e:
                print(f"  [{file_name}] 批次 {batch_num} 失败: {e}", flush=True)

        print(f"  [{file_name}] 完成，成功 {len(ticket_scenarios)}/{len(tickets)}", flush=True)
        return ticket_scenarios

    return asyncio.run(_run())


# ============ 归一化 & 聚类 ============

NORMALIZE_SCENARIOS_PROMPT = """你是业务场景归一化专家。以下是从工单中提取的业务场景列表，其中很多是同一业务场景的不同表述。

## 任务

请将这些场景**合并归一化**：
1. 语义相同或高度相似的场景合并为一个标准名称
2. 标准名称格式：**业务模块-具体功能点**（如：合同变更-修改手机号）
3. 合并后的标准名称要**简洁、通用**，能覆盖所有相似表述
4. 保留业务模块的层级结构（如"合同变更"是模块，"修改手机号"是功能点）

## 场景列表

{scenario_list}

## 输出格式

严格按以下 JSON 格式输出，不要输出其他内容：
{{
    "mappings": [
        {{"original": "原始场景名", "normalized": "归一化后的标准名"}},
        ...
    ]
}}

注意：每个原始场景都必须有对应的归一化结果。如果一个场景已经足够标准，可以映射到自身。
"""


async def normalize_scenarios(unique_scenarios: list[str]) -> dict[str, str]:
    """归一化场景名称，返回 {原始名: 标准名} 映射"""
    batch_size = 100
    all_mappings = {}

    for i in range(0, len(unique_scenarios), batch_size):
        batch = unique_scenarios[i:i + batch_size]
        scenario_list = "\n".join(f"- {s}" for s in batch)
        prompt = NORMALIZE_SCENARIOS_PROMPT.format(scenario_list=scenario_list)

        try:
            result_text = await call_llm(prompt)
            data = extract_json(result_text)
            if data and "mappings" in data:
                for m in data["mappings"]:
                    orig = m.get("original", "")
                    norm = m.get("normalized", "")
                    if orig and norm:
                        all_mappings[orig] = norm
        except Exception as e:
            print(f"    归一化批次失败: {e}")
            for s in batch:
                all_mappings[s] = s

    return all_mappings


CLUSTER_SCENARIOS_PROMPT = """你是业务场景聚类专家。以下是从工单中提取的业务场景列表，需要将它们聚类到 **{target_count} 个左右**的业务大类中。

## 聚类原则

1. 每个大类要**语义明确**，能概括其下所有场景
2. 大类名称格式：**业务模块-核心能力**（如：合同变更管理、身份认证流程、签约流程管理）
3. 相似功能的场景必须归入同一类（如"合同变更-修改手机号"和"合同变更-修改地址"都归入"合同变更管理"）
4. 目标 {target_count} 个大类，允许多 1-2 个或少 1-2 个

## 场景列表

{scenario_list}

## 输出格式

严格按以下 JSON 格式输出，不要输出其他内容：
{{
    "clusters": [
        {{"name": "大类名称", "description": "该大类包含的场景范围", "scenarios": ["属于该大类的场景名1", "场景名2", ...]}}
    ]
}}

注意：每个场景都必须出现在某个大类的 scenarios 列表中，不要遗漏。
"""


MERGE_CLUSTERS_PROMPT = """你是业务分类合并专家。以下是从工单中聚类出的业务大类列表，数量过多（{target_count} 个左右），需要合并到 **{target_count} 个**。

## 合并原则

1. 语义相近的大类必须合并（如"合同变更管理"和"合同变更-审批管理"合并为"合同变更管理"）
2. 合并后的名称要**简洁通用**
3. 低频大类合并到最相近的高频大类中

## 大类列表

{cluster_list}

## 输出格式

严格按以下 JSON 格式输出，不要输出其他内容：
{{
    "mappings": [
        {{"original": "原始大类名", "merged": "合并后的大类名"}},
        ...
    ]
}}

注意：每个原始大类都必须有对应的合并结果。如果一个大类不需要合并，merged 与 original 相同。
"""


async def cluster_scenarios(unique_scenarios: list[str], target_count: int = 25) -> dict[str, str]:
    """将场景聚类到 target_count 个大类"""
    batch_size = 150
    all_mappings = {}

    for i in range(0, len(unique_scenarios), batch_size):
        batch = unique_scenarios[i:i + batch_size]
        scenario_list = "\n".join(f"- {s}" for s in batch)
        prompt = CLUSTER_SCENARIOS_PROMPT.format(
            scenario_list=scenario_list,
            target_count=target_count,
        )

        try:
            result_text = await call_llm(prompt)
            data = extract_json(result_text)
            if data and "clusters" in data:
                for cluster in data["clusters"]:
                    cluster_name = cluster.get("name", "")
                    for s in cluster.get("scenarios", []):
                        if s and cluster_name:
                            all_mappings[s] = cluster_name
        except Exception as e:
            print(f"    聚类批次失败: {e}")
            for s in batch:
                all_mappings[s] = s

    # 第二轮：合并大类到目标数量
    cluster_names = sorted(set(all_mappings.values()))
    if len(cluster_names) > target_count + 5:
        print(f"    第一轮产生 {len(cluster_names)} 个大类，启动第二轮合并...")
        merge_prompt = MERGE_CLUSTERS_PROMPT.format(
            cluster_list="\n".join(f"- {c}" for c in cluster_names),
            target_count=target_count,
        )
        try:
            result_text = await call_llm(merge_prompt)
            data = extract_json(result_text)
            if data and "mappings" in data:
                merge_map = {m["original"]: m["merged"] for m in data["mappings"] if "original" in m and "merged" in m}
                all_mappings = {s: merge_map.get(c, c) for s, c in all_mappings.items()}
                final_count = len(set(all_mappings.values()))
                print(f"    合并后大类数: {final_count}")
        except Exception as e:
            print(f"    第二轮合并失败: {e}")

    return all_mappings


# ============ 主流程 ============

def main():
    import time
    start_time = time.time()

    print("=" * 60)
    print("工单业务场景提取器（多进程版）")
    print(f"工单目录: {TICKET_DIR}")
    print("=" * 60)

    # 1. 获取所有 .md 文件
    md_files = sorted(TICKET_DIR.glob("*.md"))
    print(f"\n找到 {len(md_files)} 个工单文件")

    # 2. 多进程并行提取场景（每个文件一个子进程）
    print(f"\n{'=' * 60}")
    print(f"阶段 1: 多进程提取场景（{len(md_files)} 个子进程并行）")
    print("=" * 60)

    file_paths = [str(f) for f in md_files]

    with Pool(processes=len(file_paths)) as pool:
        results = pool.map(process_single_file, file_paths)

    # 合并所有子进程结果
    ticket_scenarios: dict[str, list[str]] = {}
    for file_result in results:
        ticket_scenarios.update(file_result)

    # 读取所有工单（用于报告生成）
    all_tickets = []
    for file_path in md_files:
        all_tickets.extend(parse_ticket_file(file_path))

    elapsed_extract = time.time() - start_time
    print(f"\n  提取完成: {len(ticket_scenarios)}/{len(all_tickets)} 个工单")
    print(f"  耗时: {elapsed_extract:.0f} 秒")

    # 3. 场景归一化
    print(f"\n{'=' * 60}")
    print("阶段 2: 场景归一化")
    print("=" * 60)

    raw_scenarios = set()
    for scenarios in ticket_scenarios.values():
        raw_scenarios.update(scenarios)
    unique_scenarios = sorted(raw_scenarios)
    print(f"  原始场景数: {len(unique_scenarios)}")

    print(f"  正在归一化...")
    mappings = asyncio.run(normalize_scenarios(unique_scenarios))
    print(f"  归一化映射: {len(mappings)} 条")

    normalized_set = set(mappings.values())
    print(f"  归一化后场景数: {len(normalized_set)}")
    print(f"  合并减少: {len(unique_scenarios) - len(normalized_set)} 个")

    # 重新映射
    normalized_ticket_scenarios: dict[str, list[str]] = {}
    for tid, scenarios in ticket_scenarios.items():
        normalized = [mappings.get(s, s) for s in scenarios]
        normalized_ticket_scenarios[tid] = list(dict.fromkeys(normalized))

    # 4. 场景聚类
    print(f"\n{'=' * 60}")
    print("阶段 3: 场景聚类")
    print("=" * 60)

    normalized_scenarios_set = set()
    for scenarios in normalized_ticket_scenarios.values():
        normalized_scenarios_set.update(scenarios)
    unique_normalized = sorted(normalized_scenarios_set)
    print(f"  归一化场景数: {len(unique_normalized)}")

    print(f"  正在聚类到 ~25 个大类...")
    cluster_mappings = asyncio.run(cluster_scenarios(unique_normalized, target_count=25))
    print(f"  聚类映射: {len(cluster_mappings)} 条")

    cluster_set = set(cluster_mappings.values())
    print(f"  聚类后大类数: {len(cluster_set)}")

    # 重新映射
    clustered_ticket_scenarios: dict[str, list[str]] = {}
    for tid, scenarios in normalized_ticket_scenarios.items():
        clustered = [cluster_mappings.get(s, s) for s in scenarios]
        clustered_ticket_scenarios[tid] = list(dict.fromkeys(clustered))

    # 5. 统计汇总
    print(f"\n{'=' * 60}")
    print("统计汇总")
    print("=" * 60)

    all_scenarios = []
    for scenarios in clustered_ticket_scenarios.values():
        all_scenarios.extend(scenarios)

    scenario_counter = Counter(all_scenarios)

    elapsed_total = time.time() - start_time
    print(f"\n成功提取: {len(clustered_ticket_scenarios)}/{len(all_tickets)} 个工单")
    print(f"业务大类数: {len(scenario_counter)}")
    print(f"总场景次数: {len(all_scenarios)}")
    print(f"总耗时: {elapsed_total:.0f} 秒 ({elapsed_total/60:.1f} 分钟)")

    # 6. 保存结果
    save_results(all_tickets, clustered_ticket_scenarios, scenario_counter, mappings, cluster_mappings)
    generate_report(all_tickets, clustered_ticket_scenarios, scenario_counter, [])

    print(f"\n{'=' * 60}")
    print("完成！")
    print(f"场景频次: {OUTPUT_DIR / 'scenario_frequency.json'}")
    print(f"详细结果: {OUTPUT_DIR / 'ticket_scenarios.json'}")
    print(f"分析报告: {OUTPUT_DIR / 'scenario_report.md'}")


# ============ 保存与报告 ============

def save_results(
    all_tickets: list[Ticket],
    ticket_scenarios: dict[str, list[str]],
    scenario_counter: Counter,
    mappings: dict[str, str] = None,
    cluster_mappings: dict[str, str] = None,
):
    """保存结果文件"""
    freq_file = OUTPUT_DIR / "scenario_frequency.json"
    total_tickets = len(ticket_scenarios)
    freq_data = [
        {"scenario": s, "count": c, "percentage": f"{c / max(total_tickets, 1) * 100:.1f}%"}
        for s, c in scenario_counter.most_common()
    ]
    freq_file.write_text(json.dumps(freq_data, ensure_ascii=False, indent=2), encoding="utf-8")

    detail_file = OUTPUT_DIR / "ticket_scenarios.json"
    detail_data = []
    for t in all_tickets:
        detail_data.append({
            "ticket_id": t.ticket_id,
            "title": t.title,
            "original_category": t.category,
            "scenarios": ticket_scenarios.get(t.ticket_id, []),
        })
    detail_file.write_text(json.dumps(detail_data, ensure_ascii=False, indent=2), encoding="utf-8")

    if mappings:
        mapping_file = OUTPUT_DIR / "scenario_mappings.json"
        mapping_file.write_text(json.dumps(mappings, ensure_ascii=False, indent=2), encoding="utf-8")

    if cluster_mappings:
        cluster_file = OUTPUT_DIR / "scenario_cluster_mappings.json"
        cluster_file.write_text(json.dumps(cluster_mappings, ensure_ascii=False, indent=2), encoding="utf-8")


def generate_report(
    all_tickets: list[Ticket],
    ticket_scenarios: dict[str, list[str]],
    scenario_counter: Counter,
    errors: list,
):
    """生成 Markdown 分析报告"""
    total_tickets = len(all_tickets)
    extracted_count = len(ticket_scenarios)
    total_scenarios = len(scenario_counter)

    lines = []
    lines.append("# 工单业务场景分析报告")
    lines.append("")
    lines.append(f"> 生成时间: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"> 工单总数: **{total_tickets}** 个")
    lines.append(f"> 成功提取: **{extracted_count}** 个（{extracted_count / total_tickets * 100:.1f}%）")
    lines.append(f"> 业务大类数: **{total_scenarios}** 个")
    lines.append("")

    lines.append("## 一、总览")
    lines.append("")
    lines.append("| 指标 | 数值 |")
    lines.append("|------|------|")
    lines.append(f"| 工单总数 | {total_tickets} |")
    lines.append(f"| 成功提取工单数 | {extracted_count} |")
    lines.append(f"| 业务大类数 | {total_scenarios} |")
    lines.append(f"| 平均每工单场景数 | {sum(len(v) for v in ticket_scenarios.values()) / max(extracted_count, 1):.1f} |")
    lines.append("")

    lines.append("## 二、业务大类频次排名（高频 → 低频）")
    lines.append("")
    lines.append("| 排名 | 业务大类 | 出现次数 | 占比 | 频率 |")
    lines.append("|------|----------|----------|------|------|")

    avg = extracted_count / total_scenarios if total_scenarios else 0
    high_th = max(avg * 1.5, 5)
    low_th = max(avg * 0.3, 2)

    for rank, (scenario, count) in enumerate(scenario_counter.most_common(), 1):
        pct = count / extracted_count * 100
        freq = "🔴 高频" if count >= high_th else ("🟡 中频" if count >= low_th else "🟢 低频")
        lines.append(f"| {rank} | {scenario} | {count} | {pct:.1f}% | {freq} |")

    lines.append("")

    high_freq = [(s, c) for s, c in scenario_counter.most_common() if c >= high_th]
    if high_freq:
        lines.append("## 三、高频业务大类详情")
        lines.append("")

        scenario_tickets: dict[str, list[str]] = {}
        for tid, scenarios in ticket_scenarios.items():
            for s in scenarios:
                scenario_tickets.setdefault(s, []).append(tid)

        for scenario, count in high_freq:
            lines.append(f"### {scenario}（{count} 个工单）")
            lines.append("")
            tids = scenario_tickets.get(scenario, [])
            tid_to_title = {t.ticket_id: t.title for t in all_tickets}
            for tid in tids:
                title = tid_to_title.get(tid, "")
                lines.append(f"- [{tid}] {title}")
            lines.append("")

    lines.append("## 四、场景分布统计")
    lines.append("")
    count_dist = Counter(len(v) for v in ticket_scenarios.values())
    lines.append("| 场景数/工单 | 工单数 | 占比 |")
    lines.append("|-------------|--------|------|")
    for n_scenarios in sorted(count_dist.keys()):
        cnt = count_dist[n_scenarios]
        pct = cnt / extracted_count * 100
        lines.append(f"| {n_scenarios} 个场景 | {cnt} | {pct:.1f}% |")
    lines.append("")

    lines.append("## 五、原始分类 vs 提取场景对比")
    lines.append("")
    vague_categories = ["线上签约流程咨询", "操作咨询", "合同内容修改"]
    shown = 0
    for t in all_tickets:
        if any(vc in t.category for vc in vague_categories):
            scenarios = ticket_scenarios.get(t.ticket_id, [])
            if scenarios:
                lines.append(f"- **[{t.ticket_id}]** {t.title}")
                lines.append(f"  - 原始分类: {t.category}")
                lines.append(f"  - 提取场景: {', '.join(scenarios)}")
                shown += 1
                if shown >= 20:
                    lines.append(f"- ... 共 {sum(1 for t in all_tickets if any(vc in t.category for vc in vague_categories))} 个")
                    break
    lines.append("")

    report_file = OUTPUT_DIR / "scenario_report.md"
    report_file.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n📊 分析报告已生成: {report_file}")


if __name__ == "__main__":
    main()
