"""FastAPI application entrypoint."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.routes import router
from app.core.config import settings

logger = logging.getLogger("securedoc")


def _configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


@asynccontextmanager
async def lifespan(_: FastAPI):
    _configure_logging()
    # Log only non-sensitive startup metadata.
    logger.info("SecureDoc AI starting (env=%s, version=%s)", settings.app_env, __version__)
    yield
    logger.info("SecureDoc AI shutting down")


app = FastAPI(title="SecureDoc AI", version=__version__, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/health", tags=["meta"])
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "securedoc-ai", "version": __version__}
