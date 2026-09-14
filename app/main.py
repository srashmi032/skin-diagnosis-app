"""FastAPI application entrypoint.

Run locally:  uvicorn app.main:app --reload
Docs:         http://127.0.0.1:8000/docs
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import SessionLocal, init_db
from app.routers import ROUTERS
from app.services.seed import condition_count, seed_conditions

logger = logging.getLogger("skindx")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    init_db()  # dev convenience; production uses Alembic migrations
    with SessionLocal() as db:
        if condition_count(db) == 0:
            added = seed_conditions(db)
            logger.info("seeded %d skin conditions", added)
    logger.info("started %s (%s)", settings.app_name, settings.environment)
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Skin Diagnosis API",
        version="0.1.0",
        summary="Educational image-based skin assessment with safety triage.",
        description=(
            "Upload a photo, get an educational assessment of likely skin "
            "conditions plus a triage recommendation. **Not a medical diagnosis.**"
        ),
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if settings.debug else [],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    for router in ROUTERS:
        app.include_router(router)

    @app.get("/", tags=["health"])
    def root() -> dict:
        return {
            "name": "Skin Diagnosis API",
            "docs": "/docs",
            "disclaimer": settings.disclaimer_text,
        }

    return app


app = create_app()
