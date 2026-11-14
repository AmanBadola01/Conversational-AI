"""Serve the integrated UI and existing backend together on one origin."""
from pathlib import Path
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import os
# Preview deployment defaults; callers can override these without saving secrets.
os.environ.setdefault("GEMINI_MODEL", "gemini-3.1-flash-lite")
os.environ.setdefault("GROQ_MODEL", "openai/gpt-oss-20b")
os.environ.setdefault("DEBUG", "False")
from backend.app.main import app
from backend.app.core.config import settings

@app.get("/api/runtime", include_in_schema=False)
def runtime_status():
    return {"chat_configured": bool(settings.GEMINI_API_KEY), "utility_configured": bool(settings.GROQ_API_KEY), "primary_model": settings.GEMINI_MODEL, "utility_model": settings.GROQ_MODEL}
app.router.routes[:] = [r for r in app.router.routes if getattr(r, 'path', None) != '/']
@app.get('/', include_in_schema=False)
def integrated_preview():
    return FileResponse(Path(__file__).parent / 'frontend-preview/dist/integrated.html')

app.mount("/login", StaticFiles(directory=Path(__file__).parent / "login", html=True), name="login-preview")
