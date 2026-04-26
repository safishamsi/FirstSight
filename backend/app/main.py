from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import os

import logfire
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routes import router
from .vision_runtime import vision_runtime

logfire.configure(send_to_logfire=bool(os.getenv("LOGFIRE_TOKEN")))


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    yield
    await vision_runtime.stop()


def create_app() -> FastAPI:
    app = FastAPI(
        title="droopdetection-backend",
        version="0.1.0",
        summary="Minimal backend scaffold for the smart-glasses realtime agent platform.",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)
    logfire.instrument_fastapi(app)
    return app


app = create_app()
