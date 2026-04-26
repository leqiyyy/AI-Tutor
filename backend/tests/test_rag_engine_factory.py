import importlib.util
import asyncio
from importlib.machinery import ModuleSpec

from app.integrations import rag as rag_module


def test_rag_engine_factory_raises_when_raganything_missing(monkeypatch):
    monkeypatch.setattr(rag_module, "_engine", None)
    monkeypatch.setattr(rag_module, "_engine_name", None)
    original_find_spec = importlib.util.find_spec
    monkeypatch.setattr(
        importlib.util,
        "find_spec",
        lambda name: None if name == "raganything" else original_find_spec(name),
    )

    try:
        rag_module.get_rag_engine(requested_engine="raganything")
    except RuntimeError as exc:
        assert "RAG-Anything" in str(exc)
        assert "only formal RAG engine" in str(exc)
    else:  # pragma: no cover - defensive assertion
        raise AssertionError("RAG-Anything must raise instead of falling back to Simple")


def test_rag_engine_factory_rejects_non_raganything_engine(monkeypatch):
    monkeypatch.setattr(rag_module, "_engine", None)
    monkeypatch.setattr(rag_module, "_engine_name", None)

    try:
        rag_module.get_rag_engine(requested_engine="simple")
    except RuntimeError as exc:
        assert "Only RAG-Anything is supported" in str(exc)
    else:  # pragma: no cover - defensive assertion
        raise AssertionError("non-RAG-Anything engines must be rejected")


def test_rag_engine_factory_reuses_cached_raganything_engine(monkeypatch):
    monkeypatch.setattr(rag_module, "_engine", None)
    monkeypatch.setattr(rag_module, "_engine_name", None)
    original_find_spec = importlib.util.find_spec
    monkeypatch.setattr(
        importlib.util,
        "find_spec",
        lambda name: ModuleSpec("raganything", loader=None) if name == "raganything" else original_find_spec(name),
    )

    first = rag_module.get_rag_engine(requested_engine="raganything")
    second = rag_module.get_rag_engine(requested_engine="raganything")
    assert first is second
    assert first.__class__.__name__ == "RAGAnythingAdapter"


def test_shutdown_rag_engine_closes_cached_adapter(monkeypatch):
    class DummyEngine:
        def __init__(self):
            self.closed = False

        async def aclose(self):
            self.closed = True

    engine = DummyEngine()
    monkeypatch.setattr(rag_module, "_engine", engine)
    monkeypatch.setattr(rag_module, "_engine_name", "raganything")

    asyncio.run(rag_module.shutdown_rag_engine())

    assert engine.closed is True
    assert rag_module._engine is None
    assert rag_module._engine_name is None
