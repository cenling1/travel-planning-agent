from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


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


class TripSummary(BaseModel):
    destination: str | None = None
    origin: str | None = None
    travel_date: str | None = None
    travel_days: int | None = None
    travelers: int | None = None
    budget: float | None = None
    preferences: list[str] = Field(default_factory=list)


class TravelResponse(BaseModel):
    conversation_id: str
    answer: str
    citations: list[Citation] = Field(default_factory=list)
    tools: list[ToolResult] = Field(default_factory=list)
    scenario_type: Literal["simple", "complex", "multi_destination"] = "simple"
    retrieved_chunks: int = 0
    trip_summary: TripSummary = Field(default_factory=TripSummary)


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


class MemoryCreate(BaseModel):
    memory_key: str = Field(min_length=1, max_length=120)
    content: str = Field(min_length=1, max_length=1000)
    memory_type: str = Field(default="preference", min_length=1, max_length=40)
    importance: float = Field(default=0.6, ge=0.0, le=1.0)


class MemoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    owner_id: str
    memory_key: str
    memory_type: str
    content: str
    importance: float
    is_active: bool
    created_at: datetime
    updated_at: datetime


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    email: str | None = Field(default=None, max_length=320)
    password: str = Field(min_length=10, max_length=128)

    @field_validator("username")
    @classmethod
    def validate_username(cls, value: str) -> str:
        value = value.strip().lower()
        if not value.replace("_", "").replace("-", "").isalnum():
            raise ValueError("用户名只能包含字母、数字、下划线和连字符")
        return value

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str | None) -> str | None:
        normalized = (value or "").strip().lower()
        if normalized and (
            "@" not in normalized or normalized.startswith("@") or normalized.endswith("@")
        ):
            raise ValueError("邮箱格式不正确")
        return normalized or None


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


class RefreshRequest(BaseModel):
    refresh_token: str | None = Field(default=None, min_length=1)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=10, max_length=128)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    username: str
    email: str | None
    role: str
    is_active: bool
    last_login_at: datetime | None
    created_at: datetime
    updated_at: datetime


class TokenPair(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserOut


class AdminUserUpdate(BaseModel):
    role: Literal["user", "admin"] | None = None
    is_active: bool | None = None


class AdminUserCreate(RegisterRequest):
    role: Literal["user", "admin"] = "user"


class AdminPasswordReset(BaseModel):
    new_password: str = Field(min_length=10, max_length=128)


class HealthResponse(BaseModel):
    status: str
    database: str
    embedding_provider: str
    auth_enabled: bool = False
    registration_enabled: bool = False
    max_upload_bytes: int
