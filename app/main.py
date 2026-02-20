"""MRUDA — FastAPI Application Entry Point.

Modular Real-time Unified Data Analyzer.
"""

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.database import init_db
from app.scheduler.jobs import start_scheduler, stop_scheduler
from app.api.analysis_routes import router as analysis_router
from app.api.meta_routes import router as meta_router
from app.api.ai_routes import router as ai_router
from app.core.logging import get_logger

logger = get_logger("main")

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"


IS_SERVERLESS = bool(
    os.environ.get("VERCEL") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME")
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle."""
    logger.info("🚀 MRUDA starting up...")
    try:
        init_db()
        logger.info("Database initialized")
    except Exception as e:
        logger.warning(f"Database init skipped (serverless?): {e}")
    if not IS_SERVERLESS:
        start_scheduler()
    yield
    if not IS_SERVERLESS:
        stop_scheduler()
    logger.info("MRUDA shut down")


app = FastAPI(
    title="MRUDA",
    description="Modular Real-time Unified Data Analyzer — Pull Meta ad data, run deterministic analysis, generate structured intelligence.",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(analysis_router)
app.include_router(meta_router)
app.include_router(ai_router)

# Static files (frontend)
app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


@app.get("/", include_in_schema=False)
async def root():
    """Serve the MRUDA Intelligence Surface."""
    return FileResponse(str(FRONTEND_DIR / "index.html"))


@app.get("/health", tags=["System"])
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "mruda",
        "version": "1.0.0",
    }
