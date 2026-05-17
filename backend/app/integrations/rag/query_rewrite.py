from __future__ import annotations

import re
from typing import Any


EN_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "do",
    "does",
    "for",
    "from",
    "how",
    "if",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "the",
    "to",
    "what",
    "when",
    "where",
    "which",
    "why",
    "with",
}

# Keep ASCII defaults for deterministic behavior across mixed file encodings.
ZH_STOPWORDS: set[str] = set()

COURSE_DOMAIN_EXPANSIONS: tuple[tuple[tuple[str, ...], tuple[str, ...]], ...] = (
    (
        ("链路层", "数据链路层"),
        ("数据链路层", "链路层"),
    ),
    (
        ("协议层", "分层模型", "层次模型", "OSI", "TCP/IP模型", "TCP/IP五层", "协议栈"),
        ("OSI模型", "TCP/IP模型", "五层模型", "协议栈"),
    ),
    (
        ("网络层", "IP层"),
        ("网络层", "IP层", "IP"),
    ),
    (
        ("传输层", "TCP", "UDP"),
        ("传输层", "TCP", "UDP"),
    ),
    (
        ("TCP/IP", "TCPIP", "TCP-IP", "TCP_IP", "TCP/IP协议族"),
        ("TCP/IP", "TCPIP", "TCP-IP", "TCP/IP协议族"),
    ),
    (
        ("三次握手", "四次握手", "四次挥手", "TCP握手", "TCP连接", "连接建立", "连接释放"),
        ("TCP", "连接建立", "三次握手", "四次挥手", "四次握手", "连接释放"),
    ),
    (
        ("粘包", "半包", "消息边界", "无边界", "拆包"),
        ("TCP", "字节流", "消息边界", "粘包", "半包", "拆包"),
    ),
    (
        ("应用层", "HTTP", "DNS"),
        ("应用层", "HTTP", "DNS"),
    ),
)

QUERY_INTENT_RULES: tuple[dict[str, Any], ...] = (
    {
        "intent": "comparison",
        "triggers": (
            "区别",
            "比较",
            "对比",
            "不同",
            "相同",
            "异同",
            "vs",
            "versus",
            "compare",
            "difference",
            "different",
            "differ",
        ),
        "focus_terms": ("区别", "对比", "相同点", "不同点", "适用场景"),
        "answer_focus": "比较概念、机制或方法之间的相同点、差异点和适用场景。",
    },
    {
        "intent": "procedure",
        "triggers": (
            "如何",
            "怎么",
            "步骤",
            "流程",
            "过程",
            "实现",
            "配置",
            "操作",
            "how",
            "how to",
            "procedure",
            "steps",
        ),
        "focus_terms": ("步骤", "流程", "方法", "过程", "实现"),
        "answer_focus": "查找过程、步骤、算法流程或操作方法。",
    },
    {
        "intent": "formula_calculation",
        "triggers": (
            "公式",
            "计算",
            "求解",
            "求出",
            "怎么算",
            "怎么计算",
            "推导",
            "证明",
            "变量",
            "单位",
            "calculate",
            "formula",
            "derive",
            "prove",
        ),
        "focus_terms": ("公式", "变量", "推导", "计算步骤", "单位"),
        "answer_focus": "查找公式、变量含义、推导过程、计算步骤和单位约束。",
    },
    {
        "intent": "exercise_help",
        "triggers": (
            "题目",
            "作业",
            "练习",
            "解题",
            "答案",
            "选择题",
            "填空",
            "证明题",
            "exercise",
            "homework",
        ),
        "focus_terms": ("解题思路", "关键步骤", "易错点", "检查方法"),
        "answer_focus": "查找解题思路、关键步骤、易错点和检查方法。",
    },
    {
        "intent": "example_application",
        "triggers": (
            "例子",
            "举例",
            "案例",
            "应用",
            "场景",
            "example",
            "case",
            "application",
        ),
        "focus_terms": ("例子", "案例", "应用场景", "实际用途"),
        "answer_focus": "查找示例、案例、应用场景和实际用途。",
    },
    {
        "intent": "definition",
        "triggers": (
            "什么是",
            "是什么",
            "定义",
            "含义",
            "概念",
            "what is",
            "define",
            "definition",
        ),
        "focus_terms": ("定义", "概念", "含义", "核心特征"),
        "answer_focus": "查找概念定义、含义、核心特征和边界。",
    },
    {
        "intent": "causal_explanation",
        "triggers": (
            "为什么",
            "原因",
            "影响",
            "导致",
            "机制",
            "原理",
            "why",
            "reason",
            "cause",
        ),
        "focus_terms": ("原因", "机制", "原理", "影响", "关系"),
        "answer_focus": "查找原因、机制、原理、影响和因果关系。",
    },
    {
        "intent": "summary_review",
        "triggers": (
            "总结",
            "概括",
            "整理",
            "复习",
            "重点",
            "overview",
            "summary",
            "review",
        ),
        "focus_terms": ("总结", "知识点", "框架", "重点", "脉络"),
        "answer_focus": "查找课程知识点框架、重点和复习脉络。",
    },
)


def build_query_rewrite_bundle(
    *,
    question: str,
    enabled: bool,
    mode: str | None,
    max_variants: int,
) -> dict[str, Any]:
    normalized_question = _normalize_text(question)
    effective_question = normalized_question or (question or "").strip()
    normalized_mode = _normalize_mode(mode)
    intent = analyze_query_intent(effective_question)

    if not enabled or normalized_mode == "none":
        return {
            "enabled": False,
            "mode": "disabled",
            "queries": [effective_question],
            "variant_count": 1,
            "primary_query": effective_question,
            **intent,
        }

    limit = max(1, int(max_variants))
    variants: list[str] = []
    _append_unique(variants, effective_question)

    generated = _generate_variants(effective_question, normalized_mode, intent)
    for candidate in generated:
        _append_unique(variants, candidate)
        if len(variants) >= limit:
            break

    return {
        "enabled": True,
        "mode": normalized_mode,
        "queries": variants[:limit],
        "variant_count": len(variants[:limit]),
        "primary_query": variants[0] if variants else effective_question,
        **intent,
    }


def analyze_query_intent(question: str) -> dict[str, Any]:
    normalized = _normalize_text(question)
    lowered = normalized.lower()
    matches: list[tuple[dict[str, Any], list[str]]] = []
    for rule in QUERY_INTENT_RULES:
        signals = [
            trigger
            for trigger in rule["triggers"]
            if trigger and _trigger_in_text(str(trigger), lowered)
        ]
        if signals:
            matches.append((rule, signals))

    if not matches:
        return {
            "intent": "general_course_qa",
            "intent_confidence": 0.35,
            "intent_signals": [],
            "retrieval_focus_terms": [],
            "answer_focus": "查找与问题直接相关的课程资料证据。",
        }

    matches.sort(key=lambda item: len(item[1]), reverse=True)
    rule, signals = matches[0]
    confidence = min(0.95, 0.55 + 0.12 * len(signals))
    return {
        "intent": rule["intent"],
        "intent_confidence": round(confidence, 2),
        "intent_signals": signals[:6],
        "retrieval_focus_terms": list(rule["focus_terms"]),
        "answer_focus": rule["answer_focus"],
    }


def _trigger_in_text(trigger: str, lowered_text: str) -> bool:
    token = trigger.strip().lower()
    if not token:
        return False
    if re.search(r"[a-z]", token):
        return (
            re.search(rf"(?<![a-z0-9_-]){re.escape(token)}(?![a-z0-9_-])", lowered_text)
            is not None
        )
    return token in lowered_text


def _generate_variants(question: str, mode: str, intent: dict[str, Any]) -> list[str]:
    filtered_terms = _filtered_terms(question)
    outputs: list[str] = []

    domain_query = " ".join(_domain_expansion_terms(question, limit=6)).strip()
    # Let LightRAG's keyword extractor infer broad intent words. The outer
    # rewrite layer should only contribute conservative aliases/terms, not
    # generic prompts such as "steps", "definition", or "key points".
    intent_query = " ".join(filtered_terms[:8]).strip()
    compact_query = " ".join(filtered_terms[:12]).strip()
    keyword_query = " ".join(_keyword_terms(filtered_terms, limit=6)).strip()

    if domain_query:
        outputs.append(domain_query)
    if intent_query and intent.get("intent") != "general_course_qa":
        outputs.append(intent_query)
    if mode in {"hybrid", "compact"} and compact_query:
        outputs.append(compact_query)
    if mode in {"hybrid", "keywords"} and keyword_query:
        outputs.append(keyword_query)
    return outputs


def _domain_expansion_terms(question: str, limit: int) -> list[str]:
    text = question or ""
    terms: list[str] = []
    for triggers, expansions in COURSE_DOMAIN_EXPANSIONS:
        if not any(trigger and trigger in text for trigger in triggers):
            continue
        for term in expansions:
            _append_unique(terms, term)
            if len(terms) >= limit:
                return terms
    return terms


def _filtered_terms(question: str) -> list[str]:
    terms = _terms(question)
    if not terms:
        return []

    filtered: list[str] = []
    seen = set()
    for term in terms:
        lowered = term.lower()
        if lowered in seen:
            continue
        if lowered in EN_STOPWORDS or lowered in ZH_STOPWORDS:
            continue
        seen.add(lowered)
        filtered.append(term)
    return filtered


def _keyword_terms(filtered_terms: list[str], limit: int) -> list[str]:
    if not filtered_terms:
        return []
    scored = sorted(
        ((term, len(term)) for term in filtered_terms),
        key=lambda item: item[1],
        reverse=True,
    )
    selected = [term for term, _ in scored[: max(1, int(limit))]]
    if not selected:
        return []

    # Keep deterministic, human-readable order while still favoring informative terms.
    selected_set = {token.lower() for token in selected}
    ordered = [term for term in filtered_terms if term.lower() in selected_set]
    return ordered[: max(1, int(limit))]


def _terms(text: str) -> list[str]:
    latin_tokens = re.findall(r"[A-Za-z][A-Za-z0-9_-]{1,}", (text or "").lower())
    cjk_tokens = re.findall(r"[\u4e00-\u9fff]{2,8}", text or "")
    return [token for token in [*latin_tokens, *cjk_tokens] if token]


def _normalize_mode(mode: str | None) -> str:
    normalized = (mode or "hybrid").strip().lower()
    if normalized == "simple":
        return "hybrid"
    if normalized not in {"none", "hybrid", "compact", "keywords"}:
        return "hybrid"
    return normalized


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def _append_unique(values: list[str], candidate: str) -> None:
    normalized = _normalize_text(candidate)
    if not normalized:
        return
    existing = {item.lower() for item in values}
    if normalized.lower() in existing:
        return
    values.append(normalized)
