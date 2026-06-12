"""FastAPI application entrypoint.

Mounts the JSON API and the server-rendered dashboard. On startup it ensures
the schema exists and seeds demo data when DEMO_MODE is on and the DB is empty.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import func, select

from .api.routes import router as api_router
from .config import get_settings
from .db import SessionLocal, init_db
from .web.views import router as web_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    settings = get_settings()
    if settings.demo_mode:
        from . import models as m
        from .seed import seed

        session = SessionLocal()
        try:
            count = session.scalar(select(func.count()).select_from(m.FreightOffer))
            if not count:
                seed(session)
        finally:
            session.close()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
    app.include_router(api_router)
    app.include_router(web_router)
    return app


app = create_app()
