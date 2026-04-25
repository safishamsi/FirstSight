from fastapi import FastAPI

from .routes import router


def create_app() -> FastAPI:
    app = FastAPI(
        title="droopdetection-backend",
        version="0.1.0",
        summary="Minimal backend scaffold for the smart-glasses realtime agent platform.",
    )
    app.include_router(router)
    return app


app = create_app()

