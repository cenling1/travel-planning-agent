from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class Citation(BaseModel):
    index: int
    source: str
    page: int | None = None
    chunk_id: str
    excerpt: str
    score: float = 0.0


class ToolResult(BaseModel):
    name: str
    success: bool
    content: str
    latency_ms: int = 0


class TravelRequest(BaseModel):
    query: str = Field(min_length=1, max_length=4000)
    client_id: str = Field(default="local", min_length=1, max_length=64)
    conversation_id: str | None = None


class TravelPlan(BaseModel):
    summary: str
    itinerary: list[dict[str, Any]] = Field(default_factory=list)
    budget: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


class TravelResponse(BaseModel):
    conversation_id: str
    answer: str
    citations: list[Citation] = Field(default_factory=list)
    tools: list[ToolResult] = Field(default_factory=list)
    scenario_type: Literal["simple", "complex", "multi_destination"] = "simple"
    retrieved_chunks: int = 0


class ConversationCreate(BaseModel):
    client_id: str = Field(default="local", min_length=1, max_length=64)
    title: str = Field(default="新旅行规划", min_length=1, max_length=200)


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    role: str
    content: str
    created_at: datetime


class ConversationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    client_id: str
    title: str
    summary: str
    created_at: datetime
    updated_at: datetime


class ConversationDetail(ConversationOut):
    messages: list[MessageOut] = Field(default_factory=list)


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    filename: str
    file_type: str
    status: str
    visibility: str
    chunk_count: int
    error_message: str | None
    created_at: datetime
    updated_at: datetime


class DocumentUploadResponse(BaseModel):
    documents: list[DocumentOut]


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    top_k: int = Field(default=5, ge=1, le=20)


class SearchResponse(BaseModel):
    query: str
    citations: list[Citation]
    embedding_provider: str


class HealthResponse(BaseModel):
    status: str
    database: str
    embedding_provider: str
