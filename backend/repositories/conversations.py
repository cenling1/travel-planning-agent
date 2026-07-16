from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..models import Conversation, Message, utc_now


class ConversationRepository:
    def __init__(self, database: Session):
        self.database = database

    def create(self, client_id: str, title: str = "新旅行规划") -> Conversation:
        conversation = Conversation(client_id=client_id, title=title)
        self.database.add(conversation)
        self.database.commit()
        self.database.refresh(conversation)
        return conversation

    def get(self, conversation_id: str, client_id: str | None = None) -> Conversation | None:
        statement = select(Conversation).where(Conversation.id == conversation_id)
        if client_id is not None:
            statement = statement.where(Conversation.client_id == client_id)
        return self.database.scalar(statement)

    def get_with_messages(
        self,
        conversation_id: str,
        client_id: str | None = None,
    ) -> Conversation | None:
        statement = (
            select(Conversation)
            .options(selectinload(Conversation.messages))
            .where(Conversation.id == conversation_id)
        )
        if client_id is not None:
            statement = statement.where(Conversation.client_id == client_id)
        return self.database.scalar(statement)

    def list(self, client_id: str) -> list[Conversation]:
        statement = (
            select(Conversation)
            .where(Conversation.client_id == client_id)
            .order_by(Conversation.updated_at.desc())
        )
        return list(self.database.scalars(statement))

    def add_message(self, conversation: Conversation, role: str, content: str) -> Message:
        message = Message(
            conversation_id=conversation.id,
            role=role,
            content=content,
        )
        self.database.add(message)
        conversation.updated_at = utc_now()
        if conversation.title == "新旅行规划" and role == "user":
            conversation.title = content.strip()[:40] or conversation.title
        self.database.commit()
        self.database.refresh(message)
        return message

    def recent_messages(self, conversation_id: str, limit: int = 12) -> list[Message]:
        statement = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.desc())
            .limit(limit)
        )
        return list(reversed(list(self.database.scalars(statement))))

    def delete(self, conversation: Conversation) -> None:
        self.database.delete(conversation)
        self.database.commit()
