from __future__ import annotations

from fastapi import APIRouter

from app.api import admin, auth, competitors, diagnostics, health, indicators, indicators_import, monitoring, news, parsing_templates, regions, sources, templates

api_router = APIRouter(prefix="/api")
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(admin.router)
api_router.include_router(regions.router)
api_router.include_router(news.router)
api_router.include_router(templates.router)
api_router.include_router(monitoring.router)
api_router.include_router(competitors.router)
api_router.include_router(parsing_templates.router)
api_router.include_router(sources.router)
api_router.include_router(diagnostics.router)
api_router.include_router(indicators.router)
api_router.include_router(indicators_import.router)

