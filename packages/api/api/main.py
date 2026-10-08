import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api import __version__
from api.core import db
from api.core.model_assets import require_model_assets
from api.core.queue import build_queue
from api.core.settings import (
    ALLOWED_ORIGINS,
    API_HOST,
    API_PORT,
    COMPUTE_PRODUCER_PASSWORD,
    COMPUTE_PRODUCER_ROLE,
    LOG_LEVEL,
    api_pool_size,
)
from api.core.tasks import register_tasks
from api.routes import get_calculator, ops_router, router

# `basicConfig` logs to stderr, which container runtimes collect.
logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    get_calculator()
    min_size, max_size = api_pool_size()
    # A zero `min_size`, the default, keeps startup from waiting on PostgreSQL.
    pool = await db.open_pool(
        min_size=min_size,
        max_size=max_size,
        dsn=db.runtime_dsn(COMPUTE_PRODUCER_ROLE, COMPUTE_PRODUCER_PASSWORD),
    )
    register_tasks(build_queue(pool))
    logger.info("TSDHN API ready")
    try:
        yield
    finally:
        await db.close_pool()


def create_app() -> FastAPI:
    app = FastAPI(
        title="TSDHN API",
        version=__version__,
        docs_url="/api-docs",
        redoc_url=None,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type"],
    )

    app.include_router(ops_router)
    app.include_router(router)
    return app


app = create_app()


def start_app() -> None:
    require_model_assets()
    uvicorn.run(
        app,
        host=API_HOST,
        port=API_PORT,
        log_level=LOG_LEVEL.lower(),
    )


if __name__ == "__main__":
    start_app()
