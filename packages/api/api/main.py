import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api import __version__
from api.routes import get_calculator, ops_router, router

logging.basicConfig(
    filename=os.environ.get("TSDHN_API_LOG", "tsunami_api.log"),
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    get_calculator()
    logger.info("TSDHN API ready")
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="TSDHN API",
        version=__version__,
        docs_url="/api-docs",
        redoc_url=None,
        lifespan=lifespan,
    )

    origins = [o for o in os.environ.get("ALLOWED_ORIGINS", "").split(",") if o]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type"],
    )

    app.include_router(ops_router)
    app.include_router(router)
    return app


app = create_app()


def start_app() -> None:
    # Containers set APP_HOST=0.0.0.0. Local runs stay on loopback by default.
    uvicorn.run(
        app,
        host=os.environ.get("APP_HOST", "127.0.0.1"),
        port=int(os.environ.get("APP_PORT", "8000")),
        log_level="info",
    )


if __name__ == "__main__":
    start_app()
