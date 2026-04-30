from app.integrations.rag.query_rewrite import build_query_rewrite_bundle


def test_query_rewrite_disabled_keeps_original_query():
    bundle = build_query_rewrite_bundle(
        question="How does TCP slow start work?",
        enabled=False,
        mode="hybrid",
        max_variants=3,
    )
    assert bundle["enabled"] is False
    assert bundle["mode"] == "disabled"
    assert bundle["queries"] == ["How does TCP slow start work?"]
    assert bundle["variant_count"] == 1


def test_query_rewrite_hybrid_generates_multiple_variants():
    bundle = build_query_rewrite_bundle(
        question="Please explain how TCP slow start works in congestion control.",
        enabled=True,
        mode="hybrid",
        max_variants=3,
    )
    assert bundle["enabled"] is True
    assert bundle["mode"] == "hybrid"
    assert bundle["variant_count"] >= 2
    assert len(bundle["queries"]) <= 3
    assert len(set(bundle["queries"])) == len(bundle["queries"])


def test_query_rewrite_legacy_simple_alias_maps_to_hybrid():
    bundle = build_query_rewrite_bundle(
        question="Please explain how TCP slow start works in congestion control.",
        enabled=True,
        mode="simple",
        max_variants=3,
    )
    assert bundle["enabled"] is True
    assert bundle["mode"] == "hybrid"


def test_query_rewrite_expands_chinese_network_layer_aliases():
    bundle = build_query_rewrite_bundle(
        question="以简明的方式告诉我链路层的功能是什么",
        enabled=True,
        mode="hybrid",
        max_variants=3,
    )

    assert bundle["enabled"] is True
    assert any("数据链路层" in query for query in bundle["queries"])
    assert any("成帧" in query for query in bundle["queries"])


def test_query_rewrite_expands_protocol_layer_relationship_aliases():
    bundle = build_query_rewrite_bundle(
        question="链路层与协议层的关系是什么",
        enabled=True,
        mode="hybrid",
        max_variants=3,
    )

    assert bundle["enabled"] is True
    assert any("协议栈" in query for query in bundle["queries"])
    assert any("OSI模型" in query for query in bundle["queries"])
    assert any("TCP/IP模型" in query for query in bundle["queries"])
