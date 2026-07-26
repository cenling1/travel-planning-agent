from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import UserMemory, utc_now


class MemoryRepository:
    def __init__(self, database: Session):
        self.database = database

    def list(self, owner_id: str, active_only: bool = True) -> list[UserMemory]:
        statement = (
            select(UserMemory)
            .where(UserMemory.owner_id == owner_id)
            .order_by(UserMemory.importance.desc(), UserMemory.updated_at.desc())
        )
        if active_only:
            statement = statement.where(UserMemory.is_active.is_(True))
        return list(self.database.scalars(statement))

    def get(self, owner_id: str, memory_id: str) -> UserMemory | None:
        statement = select(UserMemory).where(
            UserMemory.id == memory_id,
            UserMemory.owner_id == owner_id,
        )
        return self.database.scalar(statement)

    def upsert(
        self,
        *,
        owner_id: str,
        memory_key: str,
        content: str,
        memory_type: str = "preference",
        importance: float = 0.6,
        metadata: dict | None = None,
    ) -> UserMemory:
        statement = select(UserMemory).where(
            UserMemory.owner_id == owner_id,
            UserMemory.memory_key == memory_key,
        )
        memory = self.database.scalar(statement)
        if memory is None:
            memory = UserMemory(
                owner_id=owner_id,
                memory_key=memory_key,
                content=content,
                memory_type=memory_type,
                importance=importance,
                memory_metadata=metadata or {},
            )
            self.database.add(memory)
        else:
            memory.content = content
            memory.memory_type = memory_type
            memory.importance = importance
            memory.memory_metadata = metadata or memory.memory_metadata
            memory.is_active = True
            memory.updated_at = utc_now()
        self.database.commit()
        self.database.refresh(memory)
        return memory

    def mark_used(self, memories: list[UserMemory]) -> None:
        if not memories:
            return
        now = utc_now()
        for memory in memories:
            memory.last_used_at = now
        self.database.commit()

    def delete(self, memory: UserMemory) -> None:
        self.database.delete(memory)
        self.database.commit()
