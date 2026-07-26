"""FastAPI application factory."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from app.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="SAT Exam System",
        version="0.1.0",
        docs_url="/api/docs" if settings.debug else None,
        redoc_url="/api/redoc" if settings.debug else None,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Health check
    @app.get("/api/v1/health")
    async def health():
        return {"status": "ok", "version": "0.1.0"}

    # Root redirect to docs
    from fastapi.responses import RedirectResponse
    @app.get("/")
    async def root():
        return RedirectResponse(url="/api/docs")

    # Mount routers
    from app.auth.router import router as auth_router, admin_router
    from app.upload.router import router as upload_router
    from app.question.router import router as question_router
    from app.exam.router import router as exam_router
    from app.exam.attempt_router import router as attempt_router
    from app.result.router import router as result_router
    from app.practice.router import router as practice_router
    app.include_router(auth_router)
    app.include_router(admin_router)
    app.include_router(upload_router)
    app.include_router(question_router)
    app.include_router(exam_router)
    app.include_router(attempt_router)
    app.include_router(result_router)
    app.include_router(practice_router)

    # Mount uploads directory for serving images
    uploads_path = Path("uploads")
    uploads_path.mkdir(exist_ok=True)
    app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

    return app


app = create_app()
