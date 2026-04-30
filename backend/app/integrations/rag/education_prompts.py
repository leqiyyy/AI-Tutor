from __future__ import annotations

import importlib
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)


DEFAULT_ENTITY_TYPES = [
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
]

DEFAULT_RELATION_TYPES = [
    "prerequisite_of",
    "part_of",
    "explains",
    "uses_formula",
    "applies_algorithm",
    "example_of",
    "tests",
    "causes",
    "contrasts_with",
    "equivalent_to",
    "related_to",
]

_APPLIED_SIGNATURE: tuple[Any, ...] | None = None


def parse_entity_types(raw: str | list[str] | tuple[str, ...] | None) -> list[str]:
    if raw is None:
        return list(DEFAULT_ENTITY_TYPES)
    if isinstance(raw, (list, tuple)):
        values = raw
    else:
        values = str(raw).split(",")
    normalized: list[str] = []
    for value in values:
        item = str(value or "").strip()
        if item and item not in normalized:
            normalized.append(item)
    return normalized or list(DEFAULT_ENTITY_TYPES)


def build_lightrag_addon_params(settings: Any) -> dict[str, Any]:
    if not bool(getattr(settings, "RAG_EDUCATION_PROMPTS_ENABLED", True)):
        return {}
    params: dict[str, Any] = {}
    language = str(getattr(settings, "RAG_EDUCATION_LANGUAGE", "简体中文") or "").strip()
    if language:
        params["language"] = language
    if bool(getattr(settings, "RAG_EDUCATION_ENTITY_TYPES_ENABLED", True)):
        params["entity_types"] = parse_entity_types(
            getattr(settings, "RAG_EDUCATION_ENTITY_TYPES_RAW", "")
        )
    return params


def build_query_user_prompt(settings: Any, role: str = "student") -> str | None:
    if not bool(getattr(settings, "RAG_EDUCATION_PROMPTS_ENABLED", True)):
        return None
    if not bool(getattr(settings, "RAG_EDUCATION_QUERY_PROMPT_ENABLED", True)):
        return None

    subject = str(getattr(settings, "RAG_EDUCATION_SUBJECT", "课程学习") or "课程学习").strip()
    role_key = str(role or "student").strip().lower()
    shared = (
        f"请以{subject}的智能助教身份回答。回答必须优先依据检索到的课程资料，"
        "不要编造资料中没有出现的事实；如果证据不足，请明确说明资料不足，并给出建议补充的资料方向。"
        "回答结构建议为：先给简明结论，再分步骤解释关键概念、推理过程和易错点；"
        "涉及公式、算法、实验步骤或代码时，应保留必要术语并解释其含义。"
        "请尽量标明依据来自课程资料、图片、表格、公式或教师审核内容中的哪一类证据。"
    )
    if role_key in {"teacher", "admin", "instructor"}:
        return (
            shared
            +
            "当前用户是教师。请额外关注教学设计价值：指出可用于课堂讲解的重点、"
            "学生可能困惑的位置、可补充的资料或练习建议，并避免用过度口语化表达。"
        )
    return (
        shared
        +
        "当前用户是学生。请使用循序渐进的讲解方式，优先帮助学生理解思路；"
        "如果问题疑似作业或测验题，请给出思路、关键步骤和检查方法，避免直接替学生完成全部答案。"
    )


def apply_framework_prompt_overrides(settings: Any) -> dict[str, Any]:
    """Patch selected RAG-Anything/LightRAG prompt templates at runtime.

    The override appends guidance instead of replacing templates, so upstream
    tuple delimiters, JSON fields, and continuation prompts keep their format.
    """

    global _APPLIED_SIGNATURE
    if not bool(getattr(settings, "RAG_EDUCATION_PROMPTS_ENABLED", True)):
        return {"enabled": False, "reason": "education_prompts_disabled"}
    if not bool(getattr(settings, "RAG_EDUCATION_FRAMEWORK_PROMPT_OVERRIDES_ENABLED", True)):
        return {"enabled": False, "reason": "framework_prompt_overrides_disabled"}

    signature = (
        getattr(settings, "RAG_EDUCATION_LANGUAGE", ""),
        getattr(settings, "RAG_EDUCATION_SUBJECT", ""),
        getattr(settings, "RAG_EDUCATION_ENTITY_TYPES_RAW", ""),
    )
    if _APPLIED_SIGNATURE == signature:
        return {"enabled": True, "already_applied": True}

    patched: dict[str, list[str]] = {"lightrag": [], "raganything": []}
    subject = str(getattr(settings, "RAG_EDUCATION_SUBJECT", "课程学习") or "课程学习").strip()
    entity_types = parse_entity_types(getattr(settings, "RAG_EDUCATION_ENTITY_TYPES_RAW", ""))

    lightrag_guidance = (
        "[AI Tutor education response guidance]\n"
        f"- Domain: {subject}.\n"
        "- Prefer course-grounded answers with concise conclusion, step-by-step explanation, citations/evidence cues, "
        "and explicit uncertainty when retrieved evidence is insufficient.\n"
        "- For students, emphasize reasoning and learning support rather than replacing their own work.\n"
        "- Preserve the original response format requirements above; do not remove references or structured fields."
    )
    raganything_guidance = (
        "[AI Tutor multimodal education guidance]\n"
        f"- Domain: {subject}.\n"
        "- When describing images, tables, formulas, charts, slides, or screenshots, extract visible text, title, "
        "axes, legends, variables, units, steps, and learning-relevant relationships.\n"
        "- Highlight concepts, prerequisites, formulas, examples, exercises, misconceptions, and experiment steps "
        "when they are visible or inferable from the multimodal content.\n"
        "- Preserve the original output format requirements above."
    )
    graph_extraction_guidance = build_course_graph_extraction_guidance(
        subject=subject,
        language=str(getattr(settings, "RAG_EDUCATION_LANGUAGE", "简体中文") or "简体中文").strip(),
        entity_types=entity_types,
    )

    patched["lightrag"] = _patch_prompt_module(
        module_name="lightrag.prompt",
        keys=("rag_response", "naive_rag_response", "mix_rag_response"),
        guidance=lightrag_guidance,
    )
    patched["lightrag_extraction"] = _patch_prompt_module(
        module_name="lightrag.prompt",
        keys=(
            "entity_extraction",
            "entity_continue_extraction",
            "entity_if_loop_extraction",
            "summarize_entity_descriptions",
        ),
        guidance=graph_extraction_guidance,
        key_fragments=("entity_extraction", "relationship", "relation_extraction"),
    )
    patched["raganything"] = _patch_prompt_module(
        module_name="raganything.prompt",
        keys=(
            "vision_prompt",
            "image_prompt",
            "table_prompt",
            "equation_prompt",
            "figure_prompt",
            "generic_prompt",
        ),
        guidance=raganything_guidance,
    )

    _APPLIED_SIGNATURE = signature
    logger.info("education_prompt_overrides_applied", patched=patched)
    return {"enabled": True, "patched": patched}


def build_course_graph_extraction_guidance(
    *,
    subject: str,
    language: str,
    entity_types: list[str],
) -> str:
    entity_type_text = ", ".join(entity_types or DEFAULT_ENTITY_TYPES)
    relation_type_text = ", ".join(DEFAULT_RELATION_TYPES)
    return (
        "[AI Tutor course knowledge graph extraction guidance]\n"
        f"- Domain: {subject or '课程学习'}; output language for names/descriptions/evidence: {language or '简体中文'}.\n"
        "- Build a high-quality course knowledge graph, not a file/material graph. Extract stable teaching concepts, "
        "learning objectives, formulas, theorems, algorithms, examples, exercises, misconceptions, tools, datasets, "
        "and assessment points that are explicitly supported by the source text.\n"
        f"- Prefer these entity types when the original template asks for entity types: {entity_type_text}.\n"
        f"- Prefer these relationship meanings when the original template asks for relationships: {relation_type_text}.\n"
        "- Entity names should be short canonical terms. For Chinese course material, use concise Simplified Chinese names "
        "unless the term is a standard English acronym or symbol. Merge obvious aliases instead of creating duplicates.\n"
        "- Do not extract filenames, file paths, parser chunk IDs, UUIDs, hashes, page numbers alone, dates alone, "
        "generic words, or upload/indexing artifacts as entities. Do not create relationships whose only evidence is "
        "co-occurrence in the same file name or metadata.\n"
        "- Keep evidence grounded: descriptions and relation rationales should be concise and traceable to the source. "
        "When evidence is weak, lower confidence or omit the entity/relation.\n"
        "- Preserve the original output format exactly, including delimiters, tuple labels, JSON keys, record separators, "
        "and continuation/loop semantics required above."
    )


def _patch_prompt_module(
    *,
    module_name: str,
    keys: tuple[str, ...],
    guidance: str,
    key_fragments: tuple[str, ...] = (),
) -> list[str]:
    try:
        module = importlib.import_module(module_name)
    except Exception as exc:  # pragma: no cover - depends on optional runtime packages
        logger.debug("education_prompt_module_unavailable", module=module_name, reason=str(exc))
        return []

    containers: list[Any] = []
    prompt_dict = getattr(module, "PROMPTS", None)
    if isinstance(prompt_dict, dict):
        containers.append(prompt_dict)

    registry = getattr(module, "PromptRegistry", None)
    if registry is not None:
        registry_prompts = getattr(registry, "PROMPTS", None) or getattr(registry, "_prompts", None)
        if isinstance(registry_prompts, dict):
            containers.append(registry_prompts)

    patched: list[str] = []
    for container in containers:
        target_keys = _matching_prompt_keys(container, keys=keys, key_fragments=key_fragments)
        for key in target_keys:
            value = container.get(key)
            if isinstance(value, str):
                new_value = _append_guidance_once(value, guidance)
                if new_value != value:
                    container[key] = new_value
                    patched.append(key)
    return sorted(set(patched))


def _matching_prompt_keys(
    container: dict[Any, Any],
    *,
    keys: tuple[str, ...],
    key_fragments: tuple[str, ...],
) -> list[Any]:
    targets: list[Any] = [key for key in keys if key in container]
    lowered_fragments = tuple(fragment.lower() for fragment in key_fragments)
    if lowered_fragments:
        for key in container:
            key_text = str(key).lower()
            if any(fragment in key_text for fragment in lowered_fragments) and key not in targets:
                targets.append(key)
    return targets


def _append_guidance_once(prompt: str, guidance: str) -> str:
    marker = guidance.split("\n", 1)[0]
    if marker in prompt:
        return prompt
    return f"{prompt.rstrip()}\n\n{guidance}"
