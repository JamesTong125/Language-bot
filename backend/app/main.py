"""FastAPI application entry point."""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers import account, auth, debug, meta, profile, scenarios, sessions, stats, vocab


def create_app() -> FastAPI:
    settings = get_settings()
    logging.basicConfig(level=settings.log_level)

    app = FastAPI(title="Language learning bot API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.cors_origin],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Content-Type"],
    )

    app.include_router(meta.router)
    app.include_router(auth.router)
    app.include_router(profile.router)
    app.include_router(account.router)
    app.include_router(scenarios.router)
    app.include_router(sessions.router)
    app.include_router(vocab.router)
    app.include_router(stats.router)
    app.include_router(debug.router)
    return app


app = create_app()
