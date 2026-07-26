from __future__ import annotations

import re

from sqlalchemy.orm import Session

from ..models import UserMemory
from ..repositories.memories import MemoryRepository


class MemoryService:
    def __init__(self, database: Session):
        self.repository = MemoryRepository(database)

    def list_memories(self, owner_id: str) -> list[UserMemory]:
        memories = self.repository.list(owner_id)
        self.repository.mark_used(memories)
        return memories

    def remember(
        self,
        *,
        owner_id: str,
        memory_key: str,
        content: str,
        memory_type: str = "preference",
        importance: float = 0.6,
    ) -> UserMemory:
        return self.repository.upsert(
            owner_id=owner_id,
            memory_key=self._normalize_key(memory_key),
            content=content.strip()[:1000],
            memory_type=memory_type.strip()[:40] or "preference",
            importance=max(0.0, min(1.0, importance)),
        )

    def forget(self, owner_id: str, memory_id: str) -> bool:
        memory = self.repository.get(owner_id, memory_id)
        if memory is None:
            return False
        self.repository.delete(memory)
        return True

    def capture_from_query(self, owner_id: str, query: str, extraction: dict) -> list[UserMemory]:
        candidates = self._extract_candidates(query, extraction)
        memories: list[UserMemory] = []
        for memory_key, content, memory_type, importance in candidates:
            memories.append(
                self.remember(
                    owner_id=owner_id,
                    memory_key=memory_key,
                    content=content,
                    memory_type=memory_type,
                    importance=importance,
                )
            )
        return memories

    def format_for_prompt(self, memories: list[UserMemory]) -> str:
        if not memories:
            return "无"
        return "\n".join(f"- {memory.content}" for memory in memories[:12])

    def _extract_candidates(self, query: str, extraction: dict) -> list[tuple[str, str, str, float]]:
        candidates: list[tuple[str, str, str, float]] = []
        preference_patterns = [
            (r"(?:我|我们)?(?:比较|很|特别)?喜欢([^，。！？\n]{2,80})", "positive_preference", 0.7),
            (r"(?:我|我们)?(?:不喜欢|讨厌|不想要|避免)([^，。！？\n]{2,80})", "negative_preference", 0.75),
            (r"(?:偏好|倾向于)([^，。！？\n]{2,80})", "positive_preference", 0.7),
        ]
        for pattern, memory_type, importance in preference_patterns:
            for match in re.finditer(pattern, query):
                value = match.group(1).strip()
                if value:
                    content = f"{'不喜欢' if memory_type == 'negative_preference' else '喜欢'}{value}"
                    candidates.append((content, content, memory_type, importance))

        origin = str(extraction.get("origin") or "").strip()
        if origin and any(word in query for word in ("常从", "经常从", "默认从", "一般从")):
            content = f"常用出发地是{origin}"
            candidates.append(("常用出发地", content, "travel_profile", 0.8))

        preferences = extraction.get("preferences") or []
        if isinstance(preferences, list):
            for item in preferences:
                value = str(item).strip()
                if value:
                    content = f"旅行偏好：{value}"
                    candidates.append((content, content, "positive_preference", 0.6))

        deduped: dict[str, tuple[str, str, str, float]] = {}
        for key, content, memory_type, importance in candidates:
            normalized_key = self._normalize_key(key)
            deduped[normalized_key] = (normalized_key, content, memory_type, importance)
        return list(deduped.values())

    def _normalize_key(self, value: str) -> str:
        compact = re.sub(r"\s+", "", value.strip())
        return compact[:120] or "memory"
