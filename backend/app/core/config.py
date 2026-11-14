import os
from pathlib import Path
from dotenv import load_dotenv

# Automatically locate the backend root directory and load .env
BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(BASE_DIR / ".env")

def _clean_api_key(value: str) -> str:
    """Treat empty and placeholder keys from .env.example as unset."""
    cleaned = (value or "").strip()
    lowered = cleaned.lower()
    if not cleaned or lowered.startswith("your_") or lowered.endswith("_here"):
        return ""
    return cleaned


class Settings:
    """
    Central Configuration for the Application.
    Loads values from .env with production-grade sensible defaults.
    """
    PROJECT_NAME: str = "Conversational AI Platform"
    VERSION: str = "1.0.0"
    
    # Server configuration
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    DEBUG: bool = os.getenv("DEBUG", "True").lower() in ("true", "1", "t")
    
    # Database URL: Pure PostgreSQL
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", 
        "postgresql://postgres:postgres@localhost:5432/conversational_ai"
    )
    
    # Primary LLM: Google Gemini (Chat Streaming)
    GEMINI_API_KEY: str = _clean_api_key(os.getenv("SECRET_GEMINI_API_KEY") or os.getenv("GEMINI_API_KEY", ""))
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.0-flash").strip() or "gemini-2.0-flash"

    # Secondary Utility LLM: Groq (Extraction, Summaries, KG)
    GROQ_API_KEY: str = _clean_api_key(os.getenv("SECRET_GROQ_API_KEY") or os.getenv("GROQ_API_KEY", ""))
    GROQ_MODEL: str = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant").strip() or "llama-3.1-8b-instant"
    
    # Context Window Budget Allocation (Total: 4,000 tokens)
    TOTAL_TOKEN_BUDGET: int = 4000
    SYSTEM_PROMPT_BUDGET: int = 500       # Persona instructions
    MEMORY_BUDGET: int = 1000              # Summary + Entities + KG triples
    RECENT_MESSAGES_BUDGET: int = 1500     # Recent verbatim dialogue turns
    GENERATION_BUDGET: int = 1000          # Output buffer for response
    
    # Memory Thresholds
    DEFAULT_SUMMARY_INTERVAL: int = 5      # Condense every 5 messages
    AUTO_SWITCH_THRESHOLD: int = 15        # Auto-switch from Buffer to Hybrid after 15 msgs

settings = Settings()
