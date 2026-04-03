from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings

# Live router binds active
from app.api.v1.endpoints import auth, settings as user_settings, pipeline, feed, library

app = FastAPI(
    title="ArXiv Intelligence Backend",
    version="1.0.0",
    description="Agent-based FastAPI pipeline executing LangGraph inference dynamically."
)

# Strict CORS parsing Next.js headers securely tracking credentials
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"], # React Local Dev boundaries
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class BaseAPIException(Exception):
    """Uniform Error formatting matching specification: { error: { code, message } }"""
    def __init__(self, status_code: int, code: str, message: str):
        self.status_code = status_code
        self.code = code
        self.message = message

@app.exception_handler(BaseAPIException)
async def custom_exception_handler(request: Request, exc: BaseAPIException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.code, "message": exc.message}},
    )

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    import traceback
    with open("uvicorn_error.log", "w") as f:
        f.write(traceback.format_exc())
    return JSONResponse(status_code=500, content={"error": str(exc)})

# Sub-router Endpoint Integrations
app.include_router(auth.router, prefix="/auth", tags=["Authentication"])
app.include_router(user_settings.router, prefix="/api/v1/settings", tags=["User Settings"])
app.include_router(feed.router, prefix="/api/v1/feed", tags=["Discovery Feed"])
app.include_router(library.router, prefix="/api/v1/library", tags=["Personal Library"])
app.include_router(pipeline.router, prefix="/api/v1/pipeline", tags=["Agent Pipelines"])

@app.get("/health", tags=["Environment"])
async def health_check():
    return {"status": "ok", "environment": settings.ENVIRONMENT, "vector_db": "pgvector_ready"}
