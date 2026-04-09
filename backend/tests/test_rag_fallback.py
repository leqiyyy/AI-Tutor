def test_rag_engine_fallback_when_raganything_not_available():
    import app.integrations.rag as rag_module

    rag_module._engine = None
    engine = rag_module.get_rag_engine()
    assert engine is not None
