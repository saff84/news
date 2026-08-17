from __future__ import annotations

import logging
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.router import api_router
from app.core.settings import settings


def create_app() -> FastAPI:
    logging.basicConfig(
        level=getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    app = FastAPI(title="News Intelligence Parser", version="0.1.0")

    origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    reports_dir = Path(settings.storage_dir) / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/reports", StaticFiles(directory=str(reports_dir), html=True), name="published_reports")

    indicator_media_dir = Path(settings.storage_dir) / "indicator_tg"
    indicator_media_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/indicator-media", StaticFiles(directory=str(indicator_media_dir)), name="indicator_media")

    competitor_summaries_dir = Path(settings.storage_dir) / "competitor_summaries"
    competitor_summaries_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/competitor-summaries", StaticFiles(directory=str(competitor_summaries_dir), html=True), name="competitor_summaries")

    app.include_router(api_router)
    return app


app = create_app()

