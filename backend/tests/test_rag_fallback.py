def test_rag_engine_does_not_fallback_when_raganything_not_available(monkeypatch):
    import app.integrations.rag as rag_module

    rag_module._engine = None
    rag_module._engine_name = None
    monkeypatch.setattr(rag_module.importlib.util, "find_spec", lambda name: None if name == "raganything" else object())

    try:
        rag_module.get_rag_engine()
    except RuntimeError as exc:
        assert "could not be initialized" in str(exc)
    else:  # pragma: no cover - defensive assertion
        raise AssertionError("RAG-Anything must not fall back to Simple")
