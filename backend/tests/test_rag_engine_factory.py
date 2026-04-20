import importlib.util

from app.integrations import rag as rag_module


def test_rag_engine_factory_fallbacks_to_simple_when_raganything_missing(monkeypatch):
    monkeypatch.setattr(rag_module, "_engine", None)
    monkeypatch.setattr(rag_module, "_engine_name", None)
    original_find_spec = importlib.util.find_spec
    monkeypatch.setattr(
        importlib.util,
        "find_spec",
        lambda name: None if name == "raganything" else original_find_spec(name),
    )

    engine = rag_module.get_rag_engine(requested_engine="raganything")
    assert engine.__class__.__name__ == "SimpleRAGEngine"


def test_rag_engine_factory_reuses_cached_engine_by_requested_name(monkeypatch):
    monkeypatch.setattr(rag_module, "_engine", None)
    monkeypatch.setattr(rag_module, "_engine_name", None)

    first = rag_module.get_rag_engine(requested_engine="simple")
    second = rag_module.get_rag_engine(requested_engine="simple")
    assert first is second
