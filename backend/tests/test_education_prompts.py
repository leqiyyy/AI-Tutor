from app.integrations.rag.education_prompts import (
    _append_guidance_once,
    _matching_prompt_keys,
    build_course_graph_extraction_guidance,
)


def test_course_graph_extraction_guidance_targets_chinese_course_kg():
    guidance = build_course_graph_extraction_guidance(
        subject="计算机网络",
        language="简体中文",
        entity_types=["course_concept", "formula", "algorithm"],
    )

    assert "计算机网络" in guidance
    assert "简体中文" in guidance
    assert "course_concept, formula, algorithm" in guidance
    assert "Do not extract filenames" in guidance
    assert "Preserve the original output format exactly" in guidance


def test_prompt_key_matching_supports_version_specific_extraction_names():
    container = {
        "rag_response": "answer prompt",
        "entity_extraction": "extract prompt",
        "kg_relationship_extraction": "relationship prompt",
        "unrelated": "leave me alone",
    }

    keys = _matching_prompt_keys(
        container,
        keys=("entity_extraction",),
        key_fragments=("relationship",),
    )

    assert keys == ["entity_extraction", "kg_relationship_extraction"]


def test_append_guidance_once_uses_specific_guidance_marker():
    prompt = "Original prompt"
    first_guidance = "[AI Tutor education response guidance]\nanswer guidance"
    second_guidance = "[AI Tutor course knowledge graph extraction guidance]\ngraph guidance"

    patched = _append_guidance_once(prompt, first_guidance)
    patched = _append_guidance_once(patched, second_guidance)
    patched_again = _append_guidance_once(patched, second_guidance)

    assert patched.count("[AI Tutor education response guidance]") == 1
    assert patched.count("[AI Tutor course knowledge graph extraction guidance]") == 1
    assert patched_again == patched
