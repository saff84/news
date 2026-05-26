from __future__ import annotations

from fastapi import APIRouter

from app.api import admin, ai_config, auth, competitors, developers, diagnostics, health, indicators, indicators_import, max_parser, monitoring, news, news_filter, parsing_templates, regions, report_config, reports, sources, telegram_parser, templates, vk_parser

api_router = APIRouter(prefix="/api")
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(admin.router)
api_router.include_router(regions.router)
api_router.include_router(news.router)
api_router.include_router(templates.router)
api_router.include_router(monitoring.router)
api_router.include_router(competitors.router)
api_router.include_router(developers.router)
api_router.include_router(parsing_templates.router)
api_router.include_router(sources.router)
api_router.include_router(diagnostics.router)
api_router.include_router(telegram_parser.router)
api_router.include_router(max_parser.router)
api_router.include_router(vk_parser.router)
api_router.include_router(indicators.router)
api_router.include_router(indicators_import.router)
api_router.include_router(report_config.router)
api_router.include_router(ai_config.router)
api_router.include_router(news_filter.router)
api_router.include_router(reports.router)

