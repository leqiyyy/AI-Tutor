"""LightRAG query-mode router for course RAG questions."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from app.core.config import settings


RAG_MODES = {"naive", "local", "global", "hybrid", "mix"}
Classifier = Callable[[dict[str, Any]], Awaitable[dict[str, Any] | None]]


@dataclass(frozen=True)
class RagModeDecision:
    enabled: bool
    mode: str
    confidence: float
    reason: str
    selected_by: str
    top_k: int
    chunk_top_k: int
    max_entity_tokens: int
    max_relation_tokens: int
    max_total_tokens: int
    llm_attempted: bool = False
    llm_used: bool = False
    llm_error: str | None = None
    signals: list[str] = field(default_factory=list)
    kb_stats: dict[str, Any] = field(default_factory=dict)

    def to_query_options(self) -> dict[str, Any]:
        return {
            "top_k": self.top_k,
            "chunk_top_k": self.chunk_top_k,
            "max_entity_tokens": self.max_entity_tokens,
            "max_relation_tokens": self.max_relation_tokens,
            "max_total_tokens": self.max_total_tokens,
        }

    def to_meta(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "mode": self.mode,
            "confidence": round(float(self.confidence), 4),
            "reason": self.reason,
            "selected_by": self.selected_by,
            "top_k": self.top_k,
            "chunk_top_k": self.chunk_top_k,
            "max_entity_tokens": self.max_entity_tokens,
            "max_relation_tokens": self.max_relation_tokens,
            "max_total_tokens": self.max_total_tokens,
            "llm_attempted": self.llm_attempted,
            "llm_used": self.llm_used,
            "llm_error": self.llm_error,
            "signals": list(self.signals),
            "kb_stats": dict(self.kb_stats or {}),
            "router_version": "rules_llm_v1",
        }


async def route_rag_mode(
    *,
    question: str,
    answer_mode: str | None,
    role: str,
    attachments: list[dict] | None,
    kb_stats: dict[str, Any] | None,
    llm_classifier: Classifier | None = None,
) -> RagModeDecision:
    """Select a LightRAG query mode, with rules first and optional LLM fallback."""

    fallback = _fallback_decision(kb_stats or {})
    if not bool(getattr(settings, "RAG_MODE_ROUTER_ENABLED", False)):
        return fallback

    rule_decision, should_try_llm = _rule_decision(
        question=question,
        answer_mode=answer_mode,
        role=role,
        attachments=attachments or [],
        kb_stats=kb_stats or {},
    )

    if not should_try_llm or not bool(getattr(settings, "RAG_MODE_ROUTER_LLM_FALLBACK_ENABLED", True)):
        return rule_decision
    if llm_classifier is None:
        return rule_decision

    try:
        payload = {
            "question": question,
            "answer_mode": answer_mode or "auto",
            "role": role or "student",
            "attachments": _attachment_summary(attachments or []),
            "kb_stats": kb_stats or {},
            "rule_decision": rule_decision.to_meta(),
        }
        raw = await llm_classifier(payload)
        parsed = _normalize_llm_decision(raw)
    except Exception as exc:
        return _replace_decision(
            rule_decision,
            llm_attempted=True,
            llm_error=str(exc)[:300],
        )

    if not parsed:
        return _replace_decision(rule_decision, llm_attempted=True, llm_error="empty_or_invalid_llm_decision")

    confidence = float(parsed.get("confidence") or 0.0)
    min_confidence = float(getattr(settings, "RAG_MODE_ROUTER_LLM_MIN_CONFIDENCE", 0.68) or 0.68)
    mode = _normalize_mode(parsed.get("mode") or parsed.get("rag_mode"))
    if not mode or confidence < min_confidence:
        return _replace_decision(
            rule_decision,
            llm_attempted=True,
            llm_error=f"low_confidence_or_invalid_mode:{mode}:{confidence}",
        )

    top_k, chunk_top_k = _adaptive_top_k(mode=mode, kb_stats=kb_stats or {})
    return RagModeDecision(
        enabled=True,
        mode=mode,
        confidence=min(0.98, max(confidence, rule_decision.confidence)),
        reason=str(parsed.get("reason") or "llm_router_classification")[:300],
        selected_by="llm_fallback",
        top_k=top_k,
        chunk_top_k=chunk_top_k,
        max_entity_tokens=rule_decision.max_entity_tokens,
        max_relation_tokens=rule_decision.max_relation_tokens,
        max_total_tokens=rule_decision.max_total_tokens,
        llm_attempted=True,
        llm_used=True,
        signals=[*rule_decision.signals, "llm_classifier"],
        kb_stats=kb_stats or {},
    )


def build_router_prompt(payload: dict[str, Any]) -> tuple[str, str]:
    """Return system/user prompt for optional LLM mode classification."""

    system = (
        "你是课程RAG系统的轻量检索路由器。只判断是否应该使用哪一种LightRAG query mode，"
        "不要回答用户问题。必须只输出JSON。可选mode只有 naive, local, global, hybrid, mix。\n"
        "naive: 直接查原文chunks，适合定义、事实、原文定位、知识库较小的问题。\n"
        "local: 围绕一个具体实体/概念展开。\n"
        "global: 适合主题级总结、宏观关系。\n"
        "hybrid: 适合机制、过程、因果、对比、概念关系。\n"
        "mix: 适合图片、表格、公式、图表、多模态或需要图谱+文本同时召回的问题。"
    )
    user = (
        "请根据以下信息选择mode，输出格式："
        "{\"mode\":\"hybrid\",\"confidence\":0.80,\"reason\":\"...\"}\n\n"
        f"{json.dumps(payload, ensure_ascii=False)}"
    )
    return system, user


def _fallback_decision(kb_stats: dict[str, Any]) -> RagModeDecision:
    mode = _normalize_mode(getattr(settings, "RAGANYTHING_QUERY_MODE", "mix")) or "mix"
    return RagModeDecision(
        enabled=False,
        mode=mode,
        confidence=1.0,
        reason="router_disabled_use_configured_query_mode",
        selected_by="disabled",
        top_k=max(1, int(getattr(settings, "RAG_LIGHTRAG_TOP_K", 12) or 12)),
        chunk_top_k=max(1, int(getattr(settings, "RAG_LIGHTRAG_CHUNK_TOP_K", 6) or 6)),
        max_entity_tokens=max(512, int(getattr(settings, "RAG_LIGHTRAG_MAX_ENTITY_TOKENS", 2000) or 2000)),
        max_relation_tokens=max(512, int(getattr(settings, "RAG_LIGHTRAG_MAX_RELATION_TOKENS", 3000) or 3000)),
        max_total_tokens=max(2048, int(getattr(settings, "RAG_LIGHTRAG_MAX_TOTAL_TOKENS", 8000) or 8000)),
        kb_stats=kb_stats,
    )


def _rule_decision(
    *,
    question: str,
    answer_mode: str | None,
    role: str,
    attachments: list[dict],
    kb_stats: dict[str, Any],
) -> tuple[RagModeDecision, bool]:
    text = _normalize_text(question)
    raw_text = str(question or "")
    signals: list[str] = []
    mode = "naive"
    confidence = 0.62
    reason = "default_fast_chunk_retrieval"
    needs_llm = True

    if _has_image_attachment(attachments) or _contains_any(text, _MULTIMODAL_TERMS):
        mode, confidence, reason, needs_llm = "mix", 0.93, "multimodal_or_visual_query", False
        signals.append("multimodal")
    elif _contains_any(text, _EXACT_SOURCE_TERMS):
        mode, confidence, reason, needs_llm = "naive", 0.86, "exact_source_or_original_text_lookup", False
        signals.append("source_lookup")
    elif _contains_any(text, _RELATION_TERMS):
        mode, confidence, reason, needs_llm = "hybrid", 0.84, "mechanism_relation_or_comparison_query", False
        signals.append("relation_reasoning")
    elif _contains_any(text, _SUMMARY_TERMS):
        mode, confidence, reason, needs_llm = "hybrid", 0.78, "summary_or_knowledge_organization_query", True
        signals.append("summary")
    elif _contains_any(text, _ENTITY_FOCUS_TERMS):
        mode, confidence, reason, needs_llm = "local", 0.72, "specific_concept_expansion_query", True
        signals.append("entity_focus")

    chunk_count = int(kb_stats.get("chunk_count") or 0)
    if chunk_count <= 0:
        mode, confidence, reason, needs_llm = "naive", 0.9, "empty_or_unready_kb_use_minimal_lookup", False
        signals.append("empty_kb")
    elif chunk_count <= int(getattr(settings, "RAG_MODE_ROUTER_SMALL_KB_CHUNK_THRESHOLD", 30) or 30):
        if mode in {"local", "global", "hybrid"} and not _contains_any(text, _RELATION_TERMS):
            mode, reason = "naive", "small_kb_prefer_chunk_retrieval"
            signals.append("small_kb")
            needs_llm = False

    if str(answer_mode or "").strip().lower() in {"strict_course", "course", "rag", "strict", "检索"}:
        signals.append("strict_course_mode")
        if mode == "naive" and _contains_any(text, _RELATION_TERMS + _SUMMARY_TERMS):
            mode = "hybrid"
            confidence = max(confidence, 0.82)
            reason = "strict_course_relation_or_summary_query"

    if not raw_text.strip():
        mode, confidence, reason, needs_llm = "naive", 0.95, "empty_question_fallback", False

    top_k, chunk_top_k = _adaptive_top_k(mode=mode, kb_stats=kb_stats)
    return (
        RagModeDecision(
            enabled=True,
            mode=mode,
            confidence=confidence,
            reason=reason,
            selected_by="rules",
            top_k=top_k,
            chunk_top_k=chunk_top_k,
            max_entity_tokens=max(512, int(getattr(settings, "RAG_LIGHTRAG_MAX_ENTITY_TOKENS", 2000) or 2000)),
            max_relation_tokens=max(512, int(getattr(settings, "RAG_LIGHTRAG_MAX_RELATION_TOKENS", 3000) or 3000)),
            max_total_tokens=max(2048, int(getattr(settings, "RAG_LIGHTRAG_MAX_TOTAL_TOKENS", 8000) or 8000)),
            signals=signals,
            kb_stats=kb_stats,
        ),
        needs_llm,
    )


def _adaptive_top_k(*, mode: str, kb_stats: dict[str, Any]) -> tuple[int, int]:
    base_top_k = max(1, int(getattr(settings, "RAG_LIGHTRAG_TOP_K", 12) or 12))
    base_chunk_top_k = max(1, int(getattr(settings, "RAG_LIGHTRAG_CHUNK_TOP_K", 6) or 6))
    chunk_count = int(kb_stats.get("chunk_count") or 0)

    if chunk_count <= 0:
        return min(base_top_k, 4), min(base_chunk_top_k, 3)
    if chunk_count <= int(getattr(settings, "RAG_MODE_ROUTER_SMALL_KB_CHUNK_THRESHOLD", 30) or 30):
        return min(base_top_k, 5), min(base_chunk_top_k, 3)
    if chunk_count <= int(getattr(settings, "RAG_MODE_ROUTER_MEDIUM_KB_CHUNK_THRESHOLD", 100) or 100):
        return min(base_top_k, 8), min(base_chunk_top_k, 4)
    if mode == "mix":
        return base_top_k, base_chunk_top_k
    if mode == "naive":
        return min(base_top_k, 10), base_chunk_top_k
    return base_top_k, base_chunk_top_k


def _normalize_llm_decision(raw: Any) -> dict[str, Any] | None:
    if raw is None:
        return None
    if isinstance(raw, dict):
        return raw
    text = str(raw or "").strip()
    if not text:
        return None
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.IGNORECASE | re.DOTALL).strip()
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if match:
        text = match.group(0)
    try:
        parsed = json.loads(text)
    except Exception:
        return None
    return parsed if isinstance(parsed, dict) else None


def _replace_decision(decision: RagModeDecision, **updates: Any) -> RagModeDecision:
    data = decision.__dict__.copy()
    data.update(updates)
    return RagModeDecision(**data)


def _normalize_mode(value: Any) -> str | None:
    mode = str(value or "").strip().lower()
    aliases = {
        "chunk": "naive",
        "chunks": "naive",
        "vector": "naive",
        "graph": "hybrid",
        "multimodal": "mix",
    }
    mode = aliases.get(mode, mode)
    return mode if mode in RAG_MODES else None


def _attachment_summary(attachments: list[dict]) -> list[dict[str, Any]]:
    return [
        {
            "file_type": item.get("file_type"),
            "mime_type": item.get("mime_type"),
            "name": item.get("name") or item.get("file_name"),
        }
        for item in attachments[:5]
        if isinstance(item, dict)
    ]


def _has_image_attachment(attachments: list[dict]) -> bool:
    for item in attachments:
        file_type = str((item or {}).get("file_type") or "").lower()
        mime_type = str((item or {}).get("mime_type") or "").lower()
        if file_type == "image" or mime_type.startswith("image/"):
            return True
    return False


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", "", str(text or "").lower())


def _contains_any(text: str, needles: tuple[str, ...]) -> bool:
    return any(needle in text for needle in needles)


_MULTIMODAL_TERMS = (
    "图片", "图中", "图里", "图表", "表格", "公式", "曲线", "截图", "流程图", "示意图",
    "image", "figure", "table", "formula", "chart",
)
_EXACT_SOURCE_TERMS = (
    "原文", "哪一页", "在哪里", "哪部分", "哪个文件", "提到", "引用", "出处", "根据资料",
    "资料中", "文档中", "课件中",
)
_RELATION_TERMS = (
    "关系", "区别", "联系", "对比", "比较", "影响", "导致", "为什么", "如何", "机制",
    "过程", "原理", "原因", "作用", "依赖", "关联", "异同", "怎么实现", "怎样实现",
)
_SUMMARY_TERMS = (
    "总结", "归纳", "梳理", "知识点", "重点", "框架", "结构", "脉络", "复习", "提纲",
)
_ENTITY_FOCUS_TERMS = (
    "解释", "讲一下", "介绍", "说明", "是什么", "定义", "概念", "含义",
)
