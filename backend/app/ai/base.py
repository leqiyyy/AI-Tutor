"""Abstract interfaces for all AI providers."""
from abc import ABC, abstractmethod
from typing import Any, Awaitable, Callable, Optional, List, AsyncIterator
from dataclasses import dataclass, field


@dataclass
class RAGResult:
    answer: str
    sources: List[dict] = field(default_factory=list)
    confidence: float = 1.0
    suggestions: List[str] = field(default_factory=list)
    meta: dict = field(default_factory=dict)


@dataclass
class LLMMessage:
    role: str  # system | user | assistant
    content: str


class LLMProvider(ABC):
    @abstractmethod
    async def chat(self, messages: List[LLMMessage], **kwargs) -> str:
        ...

    async def stream(self, messages: List[LLMMessage], **kwargs) -> AsyncIterator[str]:
        result = await self.chat(messages, **kwargs)
        yield result


class EmbeddingProvider(ABC):
    @abstractmethod
    async def embed(self, texts: List[str]) -> List[List[float]]:
        ...


class RAGEngine(ABC):
    @abstractmethod
    async def query(
        self,
        question: str,
        class_id: str,
        history: Optional[List[dict]] = None,
        attachments: Optional[List[dict]] = None,
        role: str = "student",
        progress_callback: Optional[Callable[[dict[str, Any]], Awaitable[None]]] = None,
    ) -> RAGResult:
        ...

    @abstractmethod
    async def ingest_material(
        self,
        class_id: str,
        material_id: str,
        file_path: str,
        mime_type: str,
    ) -> bool:
        ...

    @abstractmethod
    async def add_qa_pair(
        self,
        class_id: str,
        question: str,
        answer: str,
    ) -> bool:
        """Add a teacher-answered QA pair back into the knowledge base."""
        ...
