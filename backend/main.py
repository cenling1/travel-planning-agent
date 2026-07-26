from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import accounts, admin, chat, conversations, documents, health, memories
from .auth import AuthService
from .config import get_settings, validate_security_settings
from .database import SessionLocal, init_db
from .middleware import RequestGuardMiddleware


settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    validate_security_settings(settings)
    init_db()
    if settings.auth_enabled and settings.bootstrap_admin_username:
        with SessionLocal() as database:
            AuthService(database, settings).bootstrap_admin()
    yield


app = FastAPI(
    title=settings.app_name,
    version="2.0.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(
    RequestGuardMiddleware,
    rate_limit_per_minute=settings.rate_limit_per_minute,
    max_inflight_requests=settings.max_inflight_requests,
)

app.include_router(health.router)
app.include_router(accounts.router, prefix=settings.api_prefix)
app.include_router(admin.router, prefix=settings.api_prefix)
app.include_router(chat.router, prefix=settings.api_prefix)
app.include_router(conversations.router, prefix=settings.api_prefix)
app.include_router(documents.router, prefix=settings.api_prefix)
app.include_router(memories.router, prefix=settings.api_prefix)
