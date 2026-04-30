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
        ("数据链路层", "链路层", "成帧", "差错控制", "流量控制", "媒体访问控制", "MAC", "CRC", "CSMA/CD"),
    ),
    (
        ("协议层", "分层模型", "层次模型", "OSI", "TCP/IP模型", "TCP/IP五层", "协议栈"),
        ("网络分层", "协议层", "协议栈", "OSI模型", "TCP/IP模型", "五层模型", "应用层", "传输层", "网络层", "数据链路层", "物理层", "封装"),
    ),
    (
        ("网络层", "IP层"),
        ("网络层", "IP", "路由选择", "转发", "寻址", "ICMP"),
    ),
    (
        ("传输层", "TCP", "UDP"),
        ("传输层", "TCP", "UDP", "可靠传输", "流量控制", "拥塞控制", "端到端"),
    ),
    (
        ("应用层", "HTTP", "DNS"),
        ("应用层", "HTTP", "DNS", "SMTP", "FTP", "客户服务器", "进程通信"),
    ),
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

    if not enabled or normalized_mode == "none":
        return {
            "enabled": False,
            "mode": "disabled",
            "queries": [effective_question],
            "variant_count": 1,
            "primary_query": effective_question,
        }

    limit = max(1, int(max_variants))
    variants: list[str] = []
    _append_unique(variants, effective_question)

    generated = _generate_variants(effective_question, normalized_mode)
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
    }


def _generate_variants(question: str, mode: str) -> list[str]:
    filtered_terms = _filtered_terms(question)
    outputs: list[str] = []

    domain_query = " ".join(_domain_expansion_terms(question, limit=20)).strip()
    compact_query = " ".join(filtered_terms[:12]).strip()
    keyword_query = " ".join(_keyword_terms(filtered_terms, limit=6)).strip()

    if domain_query:
        outputs.append(domain_query)
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
