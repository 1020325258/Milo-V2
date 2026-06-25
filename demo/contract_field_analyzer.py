"""
合同字段取值逻辑分析器

使用 Claude Code SDK 分析三个核心类的字段取值链路：
1. ContractDetailAspect - 合同表单详情下发（数据准备）
2. ContractContextAspect - 合同提交切面数据预处理
3. ContractPdfBuildService - 合同 PDF 动态字段计算

使用方式:
    cd backend
    python demo/contract_field_analyzer.py
"""

import os
import json
import asyncio
from pathlib import Path

try:
    from claude_agent_sdk import query, ClaudeAgentOptions
except ImportError:
    print("[错误] claude_agent_sdk 未安装，请先安装: pip install claude-agent-sdk")
    exit(1)


# ============ 配置 ============

PROJECT_DIR = Path("/Users/zqy/work/project/nrs-sales-project")

# 三个核心类的文件路径
TARGET_FILES = [
    {
        "name": "ContractDetailAspect",
        "role": "合同表单详情下发（数据准备）",
        "path": PROJECT_DIR / "utopia-nrs-sales-project-service/src/main/java/com/ke/utopia/nrs/salesproject/service/contract/v2/ContractDetailAspect.java",
    },
    {
        "name": "ContractContextAspect",
        "role": "合同提交切面数据预处理",
        "path": PROJECT_DIR / "utopia-nrs-sales-project-service/src/main/java/com/ke/utopia/nrs/salesproject/service/contract/v2/ContractContextAspect.java",
    },
    {
        "name": "ContractPdfBuildService",
        "role": "合同 PDF 动态字段计算",
        "path": PROJECT_DIR / "utopia-nrs-sales-project-service/src/main/java/com/ke/utopia/nrs/salesproject/service/contract/v2/ContractPdfBuildService.java",
    },
]

# 输出目录
OUTPUT_DIR = Path(__file__).parent

API_CONFIG = {
    "base_url": os.getenv("ANTHROPIC_BASE_URL", "https://token-plan-cn.xiaomimimo.com/anthropic"),
    "auth_token": os.getenv("ANTHROPIC_AUTH_TOKEN", "tp-cxq9g672kqgmcpmgvzhktpk7vucswrn9atq4i4ehwyxc6ngl"),
    "model": os.getenv("ANTHROPIC_MODEL", "mimo-v2.5-pro"),
}


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


# ============ 分析 Prompt ============

ANALYZE_DETAIL_ASPECT = """你是 Java 代码分析专家。请分析以下 `ContractDetailAspect` 类的代码，这是**合同表单详情下发**的数据准备切面。

## 分析要求

请对每个方法分析：
1. **方法职责**：该方法准备什么数据
2. **数据来源**：调用了哪些 RPC/Service，入参是什么
3. **输出字段**：设置了 Context 的哪些字段
4. **条件分支**：根据不同合同类型/业务类型有哪些分支逻辑

## 输出格式

请用 Markdown 格式输出，每个方法一个小节，包含：
- 方法签名
- 职责描述
- 数据来源（RPC/Service 调用链）
- 输出到 Context 的字段
- 条件分支说明

## 代码

```java
{code}
```
"""


ANALYZE_CONTEXT_ASPECT = """你是 Java 代码分析专家。请分析以下 `ContractContextAspect` 类的代码，这是**合同提交切面数据预处理**。

## 分析要求

请对每个方法分析：
1. **方法职责**：该方法做什么预处理
2. **数据来源**：调用了哪些 RPC/Service，入参是什么
3. **输出字段**：设置了 Context 的哪些字段，或修改了请求参数的哪些字段
4. **条件分支**：根据不同合同类型/业务类型有哪些分支逻辑
5. **与 ContractDetailAspect 的关系**：该方法是否与 DetailAspect 中的方法对应，有什么差异

## 输出格式

请用 Markdown 格式输出，每个方法一个小节。

## 代码

```java
{code}
```
"""


ANALYZE_PDF_BUILD = """你是 Java 代码分析专家。请分析以下 `ContractPdfBuildService` 类的代码，这是**合同 PDF 动态字段计算**服务。

## 分析要求

请对每个 public 方法分析：
1. **方法职责**：该方法计算什么 PDF 字段
2. **数据来源**：从 Context 或其他 Service 获取什么数据
3. **计算逻辑**：字段值的计算/转换逻辑
4. **输出 key**：返回 Map 中的 key 名称（即 PDF 模板中的占位符）
5. **条件分支**：不同合同类型/版本的差异处理

## 输出格式

请用 Markdown 格式输出，每个方法一个小节。

## 代码

```java
{code}
```
"""


TRACE_FIELD_CHAIN = """你是合同系统架构专家。以下是对三个核心类的分析结果：

## 1. ContractDetailAspect（合同表单详情下发）
{detail_analysis}

## 2. ContractContextAspect（合同提交数据预处理）
{context_analysis}

## 3. ContractPdfBuildService（PDF 字段计算）
{pdf_analysis}

## 任务

请基于以上分析，输出一份**字段取值链路全景图**，要求：

1. **按业务维度分组**（如：签约人信息、合同金额、房屋信息、设计费、图纸、附件等）
2. **每个字段的完整链路**：
   - 前端字段名 → DetailAspect 准备 → ContextAspect 预处理 → PdfBuildService 计算
   - 标注每一步的数据来源（RPC/Service/数据库/Apollo配置）
3. **条件分支汇总**：同一字段在不同合同类型下的取值差异
4. **数据流向图**：用文字描述关键数据的流向

请用清晰的 Markdown 表格和层级结构输出。
"""


# ============ 主流程 ============

async def main():
    print("=" * 60)
    print("合同字段取值逻辑分析器")
    print("=" * 60)

    # 1. 读取三个文件
    file_contents = {}
    for f in TARGET_FILES:
        if not f["path"].exists():
            print(f"[错误] 文件不存在: {f['path']}")
            return
        content = f["path"].read_text(encoding="utf-8")
        file_contents[f["name"]] = content
        print(f"  ✅ {f['name']}: {len(content)} 字符, {content.count(chr(10))} 行")

    # 2. 分析 ContractDetailAspect
    print(f"\n{'=' * 60}")
    print("阶段 1: 分析 ContractDetailAspect（详情下发）")
    print("=" * 60)

    detail_prompt = ANALYZE_DETAIL_ASPECT.format(code=file_contents["ContractDetailAspect"])
    print("  正在分析...")
    detail_analysis = await call_llm(detail_prompt)
    print(f"  完成，输出 {len(detail_analysis)} 字符")

    # 3. 分析 ContractContextAspect
    print(f"\n{'=' * 60}")
    print("阶段 2: 分析 ContractContextAspect（提交预处理）")
    print("=" * 60)

    context_prompt = ANALYZE_CONTEXT_ASPECT.format(code=file_contents["ContractContextAspect"])
    print("  正在分析...")
    context_analysis = await call_llm(context_prompt)
    print(f"  完成，输出 {len(context_analysis)} 字符")

    # 4. 分析 ContractPdfBuildService
    print(f"\n{'=' * 60}")
    print("阶段 3: 分析 ContractPdfBuildService（PDF 字段计算）")
    print("=" * 60)

    pdf_prompt = ANALYZE_PDF_BUILD.format(code=file_contents["ContractPdfBuildService"])
    print("  正在分析...")
    pdf_analysis = await call_llm(pdf_prompt)
    print(f"  完成，输出 {len(pdf_analysis)} 字符")

    # 5. 生成字段链路全景图
    print(f"\n{'=' * 60}")
    print("阶段 4: 生成字段取值链路全景图")
    print("=" * 60)

    chain_prompt = TRACE_FIELD_CHAIN.format(
        detail_analysis=detail_analysis,
        context_analysis=context_analysis,
        pdf_analysis=pdf_analysis,
    )
    print("  正在生成...")
    chain_report = await call_llm(chain_prompt)
    print(f"  完成，输出 {len(chain_report)} 字符")

    # 6. 保存结果
    save_results(detail_analysis, context_analysis, pdf_analysis, chain_report)

    print(f"\n{'=' * 60}")
    print("完成！")
    print(f"详情下发分析: {OUTPUT_DIR / 'contract_detail_aspect_analysis.md'}")
    print(f"提交预处理分析: {OUTPUT_DIR / 'contract_context_aspect_analysis.md'}")
    print(f"PDF 字段分析: {OUTPUT_DIR / 'contract_pdf_build_analysis.md'}")
    print(f"字段链路全景图: {OUTPUT_DIR / 'contract_field_chain_report.md'}")


def save_results(detail, context, pdf, chain):
    """保存分析结果"""
    (OUTPUT_DIR / "contract_detail_aspect_analysis.md").write_text(detail, encoding="utf-8")
    (OUTPUT_DIR / "contract_context_aspect_analysis.md").write_text(context, encoding="utf-8")
    (OUTPUT_DIR / "contract_pdf_build_analysis.md").write_text(pdf, encoding="utf-8")
    (OUTPUT_DIR / "contract_field_chain_report.md").write_text(chain, encoding="utf-8")


if __name__ == "__main__":
    asyncio.run(main())
