"""Question intent routing before the RAG main chain.

The router is intentionally conservative: it only bypasses RAG for high-signal
system/direct/tool cases, leaving normal course questions on the existing
RAG-Anything path.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal


AnswerMode = Literal["auto", "strict_course", "quick_llm", "teacher_tool"]


@dataclass(frozen=True)
class QuestionRoute:
    route: str
    intent: str
    needs_retrieval: bool
    confidence: float
    reason: str
    answer_mode: AnswerMode
    forced_by_mode: bool = False

    def to_meta(self) -> dict:
        retrieval_used = self.route == "course_rag" and self.needs_retrieval
        return {
            "route": self.route,
            "intent": self.intent,
            "needs_retrieval": self.needs_retrieval,
            "retrieval_used": retrieval_used,
            "confidence": self.confidence,
            "reason": self.reason,
            "answer_mode": self.answer_mode,
            "source_policy": "strict_course" if self.route == "course_rag" else "none",
            "forced_by_mode": self.forced_by_mode,
            "router_version": "rules_v1",
        }


def normalize_answer_mode(value: str | None) -> AnswerMode:
    normalized = str(value or "auto").strip().lower()
    aliases = {
        "default": "auto",
        "course": "strict_course",
        "rag": "strict_course",
        "strict": "strict_course",
        "strict_rag": "strict_course",
        "knowledge": "strict_course",
        "fast": "quick_llm",
        "quick": "quick_llm",
        "llm": "quick_llm",
        "tool": "teacher_tool",
        "teacher": "teacher_tool",
    }
    normalized = aliases.get(normalized, normalized)
    if normalized not in {"auto", "strict_course", "quick_llm", "teacher_tool"}:
        return "auto"
    return normalized  # type: ignore[return-value]


def route_question(
    *,
    question: str,
    role: str = "student",
    answer_mode: str | None = None,
    has_attachments: bool = False,
) -> QuestionRoute:
    mode = normalize_answer_mode(answer_mode)
    normalized = _normalize_intent_text(question)
    role_key = str(role or "").strip().lower()

    direct_intent = classify_direct_intent(question)
    if direct_intent:
        route = {
            "greeting": "direct_answer",
            "identity": "direct_answer",
            "capability": "direct_answer",
            "kb_status": "system_status",
            "user_profile": "user_profile",
            "off_topic": "off_topic",
        }.get(direct_intent, "direct_answer")
        return QuestionRoute(
            route=route,
            intent=direct_intent,
            needs_retrieval=False,
            confidence=0.9,
            reason=f"matched_{direct_intent}_rule",
            answer_mode=mode,
        )

    if mode == "quick_llm":
        return QuestionRoute(
            route="quick_llm",
            intent="quick_llm",
            needs_retrieval=False,
            confidence=0.88,
            reason="user_selected_quick_llm",
            answer_mode=mode,
            forced_by_mode=True,
        )

    if mode == "teacher_tool":
        return QuestionRoute(
            route="teacher_tool",
            intent=_classify_teacher_tool_intent(normalized) or "teacher_tool",
            needs_retrieval=False,
            confidence=0.86,
            reason="user_selected_teacher_tool",
            answer_mode=mode,
            forced_by_mode=True,
        )

    teacher_tool_intent = _classify_teacher_tool_intent(normalized)
    if mode == "auto" and teacher_tool_intent and role_key in {"teacher", "admin", "instructor"}:
        return QuestionRoute(
            route="teacher_tool",
            intent=teacher_tool_intent,
            needs_retrieval=False,
            confidence=0.78,
            reason=f"matched_{teacher_tool_intent}_rule",
            answer_mode=mode,
        )

    if has_attachments:
        return QuestionRoute(
            route="course_rag",
            intent="attachment_grounded_qa",
            needs_retrieval=True,
            confidence=0.72,
            reason="attachment_present",
            answer_mode=mode,
        )

    return QuestionRoute(
        route="course_rag",
        intent="course_rag",
        needs_retrieval=True,
        confidence=0.55,
        reason="default_course_rag",
        answer_mode=mode,
    )


def classify_direct_intent(content: str) -> str | None:
    normalized = _normalize_intent_text(content)
    if not normalized:
        return None

    if normalized in {
        "你好",
        "您好",
        "嗨",
        "哈喽",
        "hello",
        "hi",
        "hey",
        "在吗",
        "在不在",
        "老师你好",
        "助教你好",
        "ai你好",
        "ai助教你好",
    }:
        return "greeting"

    if _contains_any(normalized, ("你叫什么", "你是谁", "你是啥", "你是什么", "你的名字", "怎么称呼你")):
        return "identity"

    if _contains_any(normalized, ("我叫什么", "我是谁", "我的名字", "我的姓名", "怎么称呼我")):
        return "user_profile"

    if _contains_any(
        normalized,
        (
            "你能做什么",
            "你可以做什么",
            "你可以实现什么功能",
            "你有什么功能",
            "你会做什么",
            "功能介绍",
            "怎么使用你",
            "你能帮我什么",
            "你可以帮我什么",
        ),
    ):
        return "capability"

    if _contains_any(
        normalized,
        (
            "知识库有资料吗",
            "知识库里有资料吗",
            "知识库有没有资料",
            "目前知识库",
            "当前知识库",
            "课程资料上传了吗",
            "老师上传资料了吗",
            "有哪些资料",
            "有什么资料",
            "资料状态",
            "知识库状态",
            "知识库里几个文档",
            "知识库有几个文档",
            "库里有几个文档",
            "库里几个文档",
            "有几个文档",
            "几个文档",
            "有多少文档",
            "文档数量",
            "几份资料",
            "有几份资料",
            "有多少资料",
            "资料数量",
        ),
    ):
        return "kb_status"

    if _contains_any(
        normalized,
        (
            "写情书",
            "讲个笑话",
            "今天天气",
            "股票",
            "彩票",
            "代写论文",
            "帮我作弊",
        ),
    ):
        return "off_topic"

    return None


def _classify_teacher_tool_intent(normalized: str) -> str | None:
    if _contains_any(normalized, ("学情", "班级分析", "学生分析", "学习情况", "薄弱点分析")):
        return "class_learning_analysis"
    if _contains_any(normalized, ("教案", "教学设计", "教学方案", "课堂设计", "备课")):
        return "lesson_plan"
    if _contains_any(normalized, ("出题", "生成题", "练习题", "测验", "试卷", "作业设计")):
        return "assessment_generation"
    if _contains_any(normalized, ("课堂活动", "互动活动", "讨论题", "导入活动")):
        return "class_activity"
    return None


def _normalize_intent_text(content: str) -> str:
    text = str(content or "").strip().lower()
    text = re.sub(r"[\s，。！？!?、,.；;：:\"'“”‘’（）()\[\]{}<>《》]+", "", text)
    return text


def _contains_any(text: str, needles: tuple[str, ...]) -> bool:
    return any(needle in text for needle in needles)
