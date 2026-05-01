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
    assert bundle["intent"] == "procedure"


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
    assert bundle["intent"] == "procedure"
    assert "步骤" in bundle["retrieval_focus_terms"]


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


def test_query_rewrite_detects_comparison_intent():
    bundle = build_query_rewrite_bundle(
        question="TCP 和 UDP 的区别是什么？",
        enabled=True,
        mode="hybrid",
        max_variants=3,
    )

    assert bundle["intent"] == "comparison"
    assert "区别" in bundle["retrieval_focus_terms"]
    assert any("适用场景" in query for query in bundle["queries"])


def test_query_rewrite_detects_formula_intent():
    bundle = build_query_rewrite_bundle(
        question="这个吞吐量公式怎么推导，变量单位分别是什么？",
        enabled=True,
        mode="hybrid",
        max_variants=3,
    )

    assert bundle["intent"] == "formula_calculation"
    assert "变量" in bundle["retrieval_focus_terms"]
    assert "单位" in bundle["retrieval_focus_terms"]


def test_query_rewrite_uses_word_boundaries_for_english_intent_terms():
    bundle = build_query_rewrite_bundle(
        question="Show me TCP slow start.",
        enabled=True,
        mode="hybrid",
        max_variants=3,
    )

    assert bundle["intent"] == "general_course_qa"


def test_query_rewrite_expands_tcp_connection_terms():
    bundle = build_query_rewrite_bundle(
        question="TCP 的四次握手作用是什么？",
        enabled=True,
        mode="hybrid",
        max_variants=4,
    )

    joined = " ".join(bundle["queries"])
    assert "三次握手" in joined
    assert "四次挥手" in joined
    assert "连接建立" in joined
    assert "连接释放" in joined


def test_query_rewrite_expands_tcp_message_boundary_terms():
    bundle = build_query_rewrite_bundle(
        question="解决 TCP 消息无边界的办法有哪些？",
        enabled=True,
        mode="hybrid",
        max_variants=4,
    )

    joined = " ".join(bundle["queries"])
    assert "无消息边界" in joined
    assert "粘包" in joined
    assert "长度字段" in joined
