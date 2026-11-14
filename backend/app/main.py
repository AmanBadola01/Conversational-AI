import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text

from backend.app.core.config import settings
from backend.app.core.database import init_db, SessionLocal, get_db
from backend.app.routers.personas import seed_default_personas
from backend.app.routers import (
    auth_router,
    conversations_router,
    messages_router,
    memory_router,
    personas_router
)

# Configure logging
logging.basicConfig(
    level=logging.INFO if not settings.DEBUG else logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("conversational_ai")

# Application Lifespan: Handles database initialization and default persona seeding on startup
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing database schema...")
    init_db()

    # Pre-seed default personas on initial startup
    db = SessionLocal()
    try:
        seed_default_personas(db)
    finally:
        db.close()

    logger.info("Conversational AI backend started successfully.")
    yield
    logger.info("Conversational AI backend shutting down.")

# FastAPI Application Factory: Instantiates app with metadata, lifespan, and CORS middleware
app = FastAPI(
    title="Conversational AI with Memory & Chains",
    description=(
        "Comprehensive backend API demonstrating multi-paradigm memory architectures "
        "(Buffer, Summary, Entity, Knowledge Graph), LangChain LCEL chains, "
        "Smart Middle-Truncation within a 4,000-token budget, and Dual-LLM orchestration."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# CORS Configuration: Enables cross-origin requests for the React frontend.
# Wildcard origins cannot be combined with credentials per the CORS spec.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Router Registration: auth plus the 4 core API routers
app.include_router(auth_router)
app.include_router(conversations_router)
app.include_router(messages_router)
app.include_router(memory_router)
app.include_router(personas_router)

# Root Endpoint: Returns high-level API metadata, documentation URLs, and supported memory strategies
@app.get("/", tags=["System"])
def root_endpoint():
    return {
        "title": "Conversational AI Platform API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
        "supported_memory_techniques": [
            "buffer",
            "summary",
            "entity",
            "kg",
            "hybrid"
        ],
        "models": {
            "primary_chat": settings.GEMINI_MODEL,
            "utility_extraction": settings.GROQ_MODEL
        },
        "token_budget": {
            "total_budget": settings.TOTAL_TOKEN_BUDGET,
            "system_prompt": settings.SYSTEM_PROMPT_BUDGET,
            "memory_context": settings.MEMORY_BUDGET,
            "recent_messages": settings.RECENT_MESSAGES_BUDGET,
            "generation_reservation": settings.GENERATION_BUDGET
        }
    }

# Health Check: Validates live database connectivity and reports operational status of core engines
@app.get("/health", tags=["System"], status_code=status.HTTP_200_OK)
def health_check(db: Session = Depends(get_db)):
    db_status = "healthy"
    try:
        db.execute(text("SELECT 1"))
    except Exception as e:
        logger.error(f"Health check database ping failed: {e}")
        db_status = f"unhealthy: {e}"

    return {
        "status": "online",
        "database": db_status,
        "environment": "development" if settings.DEBUG else "production",
        "primary_model": settings.GEMINI_MODEL,
        "utility_model": settings.GROQ_MODEL
    }


@app.middleware("http")
async def private_responses(request, call_next):
    from urllib.parse import urlsplit
    from fastapi.responses import JSONResponse
    origin = request.headers.get("origin")
    if request.method in {"POST", "PATCH", "PUT", "DELETE"} and origin and urlsplit(origin).netloc != request.url.netloc:
        return JSONResponse({"detail": "Cross-origin requests are not allowed."}, status_code=403)
    response = await call_next(request)
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "same-origin"
    return response
