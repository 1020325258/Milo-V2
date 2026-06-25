"""
基础 AgentScope Demo

使用 DashScope (Qwen3.7-Plus) 模型创建一个简单的对话 Agent。

使用方式:
    export DASHSCOPE_API_KEY=your_api_key
    python demo/basic_agent.py
"""

import os
import asyncio

from agentscope.agent import Agent
from agentscope.model import DashScopeChatModel
from agentscope.credential import DashScopeCredential
from agentscope.message import Msg, TextBlock


async def main():
    # 1. 配置 DashScope 凭证
    api_key = os.getenv("DASHSCOPE_API_KEY")
    if not api_key:
        print("请设置环境变量 DASHSCOPE_API_KEY")
        print("  export DASHSCOPE_API_KEY=your_api_key")
        return

    credential = DashScopeCredential(api_key=api_key)

    # 2. 创建模型
    model = DashScopeChatModel(
        credential=credential,
        model="qwen3.7-plus",
        parameters=DashScopeChatModel.Parameters(
            temperature=0.7,
            max_tokens=2048,
        ),
        stream=True,
    )

    # 3. 创建 Agent
    agent = Agent(
        name="小助手",
        system_prompt="你是一个友好的 AI 助手，请用简洁清晰的中文回答问题。",
        model=model,
    )

    # 4. 对话循环
    print("=" * 50)
    print("AgentScope 基础对话 Demo")
    print("模型: Qwen3.7-Plus")
    print("输入 'quit' 或 'exit' 退出")
    print("=" * 50)

    while True:
        try:
            user_input = input("\n你: ").strip()
            if not user_input:
                continue
            if user_input.lower() in ("quit", "exit", "q"):
                print("再见！")
                break

            # 构造用户消息
            user_msg = Msg(
                name="user",
                content=[TextBlock(text=user_input)],
                role="user",
            )

            # 调用 Agent 获取回复
            print("助手: ", end="", flush=True)
            response = await agent.reply(user_msg)

            # 输出回复
            for block in response.content:
                if hasattr(block, "text"):
                    print(block.text)

        except KeyboardInterrupt:
            print("\n再见！")
            break
        except Exception as e:
            print(f"\n错误: {e}")


if __name__ == "__main__":
    asyncio.run(main())
