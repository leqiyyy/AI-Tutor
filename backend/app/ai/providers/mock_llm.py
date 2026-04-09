"""Mock LLM provider for development/testing."""
import asyncio
from typing import List
from app.ai.base import LLMProvider, LLMMessage


MOCK_RESPONSES = [
    "根据课程知识库，这个问题涉及到核心概念。让我为您详细解释：\n\n该知识点在教材第3章有详细描述，主要包括以下几个方面：\n1. 基本定义与原理\n2. 典型应用场景\n3. 常见误区分析\n\n建议结合课程资料深入学习。",
    "这是一个很好的问题！从课程知识库检索到相关内容：\n\n**核心要点**\n- 该概念的定义：指在特定条件下发生的现象或过程\n- 与相关概念的区别：注意边界条件\n- 实际应用：在工程实践中广泛使用\n\n如需进一步了解，欢迎继续追问。",
    "根据您的问题，我从课程资料中找到了相关内容：\n\n这个知识点是本课程的重点之一。主要涉及：\n\n1. **理论基础**：基于经典理论推导\n2. **计算方法**：可采用公式法或图解法\n3. **注意事项**：边界条件的处理\n\n您还有其他疑问吗？",
]

_counter = 0


class MockLLMProvider(LLMProvider):
    async def chat(self, messages: List[LLMMessage], **kwargs) -> str:
        global _counter
        await asyncio.sleep(0.3)  # Simulate latency
        # Extract last user message for keyword matching
        last_user = next(
            (m.content for m in reversed(messages) if m.role == "user"), ""
        )
        if "tcp" in last_user.lower() or "握手" in last_user:
            return (
                "TCP三次握手过程：\n\n"
                "**第一次握手**：客户端发送SYN报文（SYN=1, seq=x）\n"
                "**第二次握手**：服务器回复SYN+ACK报文（SYN=1, ACK=1, seq=y, ack=x+1）\n"
                "**第三次握手**：客户端发送ACK报文（ACK=1, ack=y+1），连接建立\n\n"
                "第三次握手**可以携带数据**。"
            )
        response = MOCK_RESPONSES[_counter % len(MOCK_RESPONSES)]
        _counter += 1
        return response
