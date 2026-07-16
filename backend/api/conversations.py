from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from ..database import get_db
from ..repositories.conversations import ConversationRepository
from ..schemas import ConversationCreate, ConversationDetail, ConversationOut


router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.post("", response_model=ConversationOut, status_code=201)
def create_conversation(
    payload: ConversationCreate,
    database: Session = Depends(get_db),
) -> ConversationOut:
    return ConversationRepository(database).create(payload.client_id, payload.title)


@router.get("", response_model=list[ConversationOut])
def list_conversations(
    client_id: str = Query(default="local", min_length=1, max_length=64),
    database: Session = Depends(get_db),
) -> list[ConversationOut]:
    return ConversationRepository(database).list(client_id)


@router.get("/{conversation_id}", response_model=ConversationDetail)
def get_conversation(
    conversation_id: str,
    client_id: str = Query(default="local", min_length=1, max_length=64),
    database: Session = Depends(get_db),
) -> ConversationDetail:
    conversation = ConversationRepository(database).get_with_messages(
        conversation_id,
        client_id,
    )
    if conversation is None:
        raise HTTPException(status_code=404, detail="会话不存在")
    return conversation


@router.delete("/{conversation_id}", status_code=204)
def delete_conversation(
    conversation_id: str,
    client_id: str = Query(default="local", min_length=1, max_length=64),
    database: Session = Depends(get_db),
) -> Response:
    repository = ConversationRepository(database)
    conversation = repository.get(conversation_id, client_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="会话不存在")
    repository.delete(conversation)
    return Response(status_code=204)
