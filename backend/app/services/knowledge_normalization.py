from __future__ import annotations

import re
from typing import Any


_EXACT_ENTITY_ALIASES = {
    "传输控制协议": "TCP",
    "tcp协议": "TCP",
    "用户数据报协议": "UDP",
    "udp协议": "UDP",
    "超文本传输协议": "HTTP",
    "http协议": "HTTP",
    "安全超文本传输协议": "HTTPS",
    "https协议": "HTTPS",
    "域名系统": "DNS",
    "dns协议": "DNS",
    "内容分发网络": "CDN",
    "安全外壳协议": "SSH",
    "ssh协议": "SSH",
    "安全文件传输协议": "SFTP",
    "sftp协议": "SFTP",
}

_RELATION_TYPE_ALIASES = {
    "uses": "uses_method",
    "use": "uses_method",
    "used_by": "used_in",
    "has": "has_part",
    "contains": "has_part",
    "part": "part_of",
    "is_part_of": "part_of",
    "include": "has_part",
    "includes": "has_part",
    "support": "supports",
    "supported_by": "supports",
    "secure": "secures",
    "security": "secures",
    "cause": "causes",
    "caused_by": "causes",
    "solve": "solves",
    "mitigate": "mitigates",
    "mitigation": "mitigates",
    "related": "related_to",
    "relates_to": "related_to",
}


def normalize_entity_surface(name: Any) -> str:
    text = str(name or "").strip()
    text = re.sub(r"\s+", " ", text)
    return text.strip(" \t\r\n\"'“”‘’`，,。.;；:：")


def canonicalize_entity_name(name: Any) -> tuple[str, list[str]]:
    """Return a conservative canonical display name and aliases.

    This intentionally avoids aggressive course-specific rewriting. It mainly
    merges common forms such as `TCP协议`, `传输控制协议`, and `TCP`.
    """

    surface = normalize_entity_surface(name)
    if not surface:
        return "", []

    aliases = [surface]
    exact_key = surface.lower()
    if exact_key in _EXACT_ENTITY_ALIASES:
        canonical = _EXACT_ENTITY_ALIASES[exact_key]
        return canonical, _dedupe_aliases([surface, canonical])

    acronym_in_parens = re.fullmatch(r"(.{2,80})[（(]\s*([A-Za-z][A-Za-z0-9+.#-]{1,20})\s*[）)]", surface)
    if acronym_in_parens:
        canonical = acronym_in_parens.group(2).upper()
        return canonical, _dedupe_aliases([surface, acronym_in_parens.group(1).strip(), canonical])

    leading_acronym = re.fullmatch(r"([A-Za-z][A-Za-z0-9+.#-]{1,20})[（(].{2,80}[）)]", surface)
    if leading_acronym:
        canonical = leading_acronym.group(1).upper()
        return canonical, _dedupe_aliases([surface, canonical])

    ascii_with_cn_suffix = re.fullmatch(
        r"([A-Za-z][A-Za-z0-9+.#-]{1,20})(?:协议|算法|机制|技术|系统|模型|方法|结构|字段|报文|攻击|防御)?",
        surface,
    )
    if ascii_with_cn_suffix:
        canonical = ascii_with_cn_suffix.group(1).upper()
        if canonical != surface:
            aliases.append(canonical)
        return canonical, _dedupe_aliases(aliases)

    return surface, _dedupe_aliases(aliases)


def canonical_entity_key(name: Any) -> str:
    canonical, _aliases = canonicalize_entity_name(name)
    return canonical.lower()


def merge_aliases(*values: Any, limit: int = 12) -> list[str]:
    aliases: list[str] = []
    for value in values:
        if isinstance(value, (list, tuple, set)):
            aliases.extend(str(item) for item in value if item)
        elif value:
            aliases.append(str(value))
    return _dedupe_aliases(aliases)[:limit]


def normalize_relation_type(value: Any) -> str:
    text = str(value or "related_to").strip().lower()
    text = re.sub(r"[^a-z0-9_\-]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_-")
    if not text:
        return "related_to"
    return _RELATION_TYPE_ALIASES.get(text, text)


def _dedupe_aliases(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = normalize_entity_surface(value)
        if not normalized:
            continue
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(normalized)
    return result
