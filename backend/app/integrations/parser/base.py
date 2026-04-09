from abc import ABC, abstractmethod


class BaseParserProvider(ABC):
    @abstractmethod
    def parse(self, file_path: str, mime_type: str, file_name: str) -> dict:
        """Return parsed text, chunks, content items, and extracted keywords."""
