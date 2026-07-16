import asyncio
from hashlib import sha256
import math
import re

from langchain_community.embeddings import DashScopeEmbeddings

from ..config import Settings, get_settings


class EmbeddingService:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self._client = None
        if self.settings.dashscope_api_key:
            self._client = DashScopeEmbeddings(
                model=self.settings.embedding_model,
                dashscope_api_key=self.settings.dashscope_api_key,
            )

    @property
    def provider(self) -> str:
        return "dashscope" if self._client else "local-hash-fallback"

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if self._client:
            vectors = await asyncio.to_thread(self._client.embed_documents, texts)
            return [self._normalize_dimension(vector) for vector in vectors]
        return [self._hash_embedding(text) for text in texts]

    async def embed_query(self, text: str) -> list[float]:
        if self._client:
            vector = await asyncio.to_thread(self._client.embed_query, text)
            return self._normalize_dimension(vector)
        return self._hash_embedding(text)

    def _normalize_dimension(self, vector: list[float]) -> list[float]:
        dimension = self.settings.embedding_dimension
        normalized = [float(value) for value in vector[:dimension]]
        if len(normalized) < dimension:
            normalized.extend([0.0] * (dimension - len(normalized)))
        return normalized

    def _hash_embedding(self, text: str) -> list[float]:
        dimension = self.settings.embedding_dimension
        vector = [0.0] * dimension
        normalized_text = re.sub(r"\s+", "", text.lower())
        tokens = list(normalized_text)
        tokens.extend(
            normalized_text[index:index + 2]
            for index in range(max(0, len(normalized_text) - 1))
        )

        for token in tokens:
            digest = sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % dimension
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign

        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]
