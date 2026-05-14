from __future__ import annotations

from typing import Any


GRAPH_SCHEMA_VERSION = 1


COMMON_ENTITY_TYPES = [
    "course_concept",
    "prerequisite",
    "learning_objective",
    "formula",
    "theorem",
    "algorithm",
    "example",
    "exercise",
    "misconception",
    "experiment_step",
    "tool",
    "dataset",
    "assessment_point",
    "method",
    "problem",
    "phenomenon",
    "system_component",
    "person",
    "organization",
    "location",
    "event",
    "Other",
]


COMMON_RELATION_TYPES = [
    "prerequisite_of",
    "part_of",
    "explains",
    "uses_method",
    "uses_formula",
    "applies_algorithm",
    "example_of",
    "tests",
    "causes",
    "solves",
    "depends_on",
    "has_property",
    "contrasts_with",
    "equivalent_to",
    "related_to",
]


DOMAIN_SCHEMAS: dict[str, dict[str, Any]] = {
    "general": {
        "label": "通用课程",
        "keywords": [],
        "entity_types": [],
        "relation_types": [],
    },
    "computer_network": {
        "label": "计算机网络",
        "keywords": [
            "计算机网络",
            "网络",
            "tcp",
            "udp",
            "http",
            "https",
            "dns",
            "ip",
            "路由",
            "交换",
            "协议",
            "报文",
            "拥塞",
            "流量控制",
        ],
        "entity_types": [
            "protocol",
            "packet_format",
            "field",
            "state",
            "protocol_property",
            "transmission_mode",
            "network_layer",
            "network_device",
            "network_service",
        ],
        "relation_types": [
            "has_field",
            "has_state",
            "extends",
            "secures",
            "encapsulates",
            "communicates_with",
            "supports",
            "leads_to",
            "manages",
        ],
    },
    "cybersecurity": {
        "label": "网络安全",
        "keywords": [
            "网络安全",
            "信息安全",
            "漏洞",
            "攻击",
            "防火墙",
            "入侵检测",
            "vpn",
            "ddos",
            "xss",
            "sql注入",
            "加密",
            "认证",
            "取证",
        ],
        "entity_types": [
            "attack_type",
            "vulnerability",
            "defense_method",
            "security_protocol",
            "security_property",
            "security_tool",
            "access_control_model",
            "malware_type",
            "risk",
            "asset",
        ],
        "relation_types": [
            "exploits",
            "mitigates",
            "protects",
            "detects",
            "prevents",
            "targets",
            "requires",
            "authenticates",
            "encrypts",
        ],
    },
    "data_structure": {
        "label": "数据结构",
        "keywords": [
            "数据结构",
            "算法",
            "数组",
            "链表",
            "栈",
            "队列",
            "树",
            "图",
            "排序",
            "查找",
            "复杂度",
            "哈希",
        ],
        "entity_types": [
            "data_structure",
            "operation",
            "complexity",
            "algorithm_strategy",
            "edge_case",
            "invariant",
            "implementation_detail",
        ],
        "relation_types": [
            "implements",
            "has_operation",
            "has_complexity",
            "optimizes",
            "traverses",
            "maintains_invariant",
        ],
    },
    "computer_organization": {
        "label": "计算机组成原理",
        "keywords": [
            "计算机组成",
            "组成原理",
            "cpu",
            "指令",
            "流水线",
            "cache",
            "缓存",
            "存储器",
            "总线",
            "alu",
            "控制器",
            "寄存器",
        ],
        "entity_types": [
            "hardware_component",
            "instruction",
            "register",
            "memory_hierarchy",
            "pipeline_stage",
            "performance_metric",
            "addressing_mode",
        ],
        "relation_types": [
            "executes",
            "stores",
            "fetches",
            "decodes",
            "controls",
            "connects_to",
            "improves_performance",
        ],
    },
    "operating_system": {
        "label": "操作系统",
        "keywords": [
            "操作系统",
            "进程",
            "线程",
            "调度",
            "死锁",
            "内存管理",
            "虚拟内存",
            "文件系统",
            "同步",
            "互斥",
        ],
        "entity_types": [
            "os_concept",
            "process_state",
            "scheduling_algorithm",
            "synchronization_primitive",
            "memory_mechanism",
            "file_system_component",
            "resource",
        ],
        "relation_types": [
            "schedules",
            "synchronizes",
            "allocates",
            "releases",
            "blocks",
            "wakes",
            "maps_to",
        ],
    },
    "database": {
        "label": "数据库",
        "keywords": [
            "数据库",
            "sql",
            "关系模型",
            "事务",
            "索引",
            "范式",
            "查询优化",
            "并发控制",
            "日志",
            "恢复",
        ],
        "entity_types": [
            "database_concept",
            "relational_model",
            "sql_statement",
            "transaction_property",
            "index_structure",
            "normal_form",
            "query_operator",
            "concurrency_control_method",
        ],
        "relation_types": [
            "queries",
            "indexes",
            "normalizes",
            "joins",
            "locks",
            "commits",
            "rolls_back",
            "optimizes",
        ],
    },
}


def build_graph_schema(
    *,
    name: str | None = None,
    description: str | None = None,
    requested_domain: str | None = None,
) -> dict[str, Any]:
    domain = _normalize_domain(requested_domain) or infer_course_domain(name=name, description=description)
    template = DOMAIN_SCHEMAS.get(domain) or DOMAIN_SCHEMAS["general"]
    return {
        "version": GRAPH_SCHEMA_VERSION,
        "source": "auto" if not requested_domain else "manual",
        "domain": domain,
        "label": template.get("label") or "通用课程",
        "entity_types": _dedupe(COMMON_ENTITY_TYPES + list(template.get("entity_types") or [])),
        "relation_types": _dedupe(COMMON_RELATION_TYPES + list(template.get("relation_types") or [])),
    }


def resolve_graph_schema(
    raw: Any,
    *,
    name: str | None = None,
    description: str | None = None,
) -> dict[str, Any]:
    if isinstance(raw, dict):
        domain = _normalize_domain(raw.get("domain"))
        template = DOMAIN_SCHEMAS.get(domain or "") or {}
        entity_types = _dedupe(
            COMMON_ENTITY_TYPES
            + list(template.get("entity_types") or [])
            + _coerce_string_list(raw.get("entity_types"))
        )
        relation_types = _dedupe(
            COMMON_RELATION_TYPES
            + list(template.get("relation_types") or [])
            + _coerce_string_list(raw.get("relation_types"))
        )
        return {
            "version": int(raw.get("version") or GRAPH_SCHEMA_VERSION),
            "source": str(raw.get("source") or "manual"),
            "domain": domain or infer_course_domain(name=name, description=description),
            "label": str(raw.get("label") or template.get("label") or "通用课程"),
            "entity_types": entity_types,
            "relation_types": relation_types,
        }
    return build_graph_schema(name=name, description=description)


def infer_course_domain(*, name: str | None = None, description: str | None = None) -> str:
    text = f"{name or ''} {description or ''}".strip().lower()
    if not text:
        return "general"
    scores: dict[str, int] = {}
    for domain, template in DOMAIN_SCHEMAS.items():
        if domain == "general":
            continue
        score = 0
        label = str(template.get("label") or "").lower()
        if label and label in text:
            score += 10
        for keyword in template.get("keywords") or []:
            keyword_text = str(keyword).lower()
            if keyword_text and keyword_text in text:
                score += max(1, len(keyword_text) // 4)
        if score:
            scores[domain] = score
    if not scores:
        return "general"
    return max(scores.items(), key=lambda item: item[1])[0]


def graph_schema_signature(schema: Any) -> dict[str, Any]:
    resolved = resolve_graph_schema(schema)
    return {
        "version": resolved.get("version"),
        "domain": resolved.get("domain"),
        "entity_types": resolved.get("entity_types") or [],
        "relation_types": resolved.get("relation_types") or [],
    }


def _normalize_domain(value: Any) -> str | None:
    text = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "network": "computer_network",
        "computer_networks": "computer_network",
        "cn": "computer_network",
        "security": "cybersecurity",
        "cyber_security": "cybersecurity",
        "ds": "data_structure",
        "data_structures": "data_structure",
        "coa": "computer_organization",
        "computer_architecture": "computer_organization",
        "os": "operating_system",
        "db": "database",
        "dbms": "database",
    }
    domain = aliases.get(text, text)
    return domain if domain in DOMAIN_SCHEMAS else None


def _coerce_string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        values = value.split(",")
    elif isinstance(value, (list, tuple, set)):
        values = value
    else:
        return []
    return [str(item).strip() for item in values if str(item or "").strip()]


def _dedupe(values: list[str]) -> list[str]:
    normalized: list[str] = []
    for value in values:
        item = str(value or "").strip()
        if item and item not in normalized:
            normalized.append(item)
    return normalized
