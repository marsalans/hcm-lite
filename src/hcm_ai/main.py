from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from hcm_ai.agent.tracing import configure_tracing
from hcm_ai.config import get_settings
from hcm_ai.db import init_db
from hcm_ai.routers import ai


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    init_db()
    configure_tracing(get_settings())
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    docs = settings.enable_docs
    app = FastAPI(
        title="HCM Lite - AI Assistant (M8)",
        lifespan=lifespan,
        docs_url="/docs" if docs else None,
        redoc_url="/redoc" if docs else None,
        openapi_url="/openapi.json" if docs else None,
    )

    @app.middleware("http")
    async def limit_body_size(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        # Declared size only; chunked uploads must also be capped at the reverse proxy.
        declared = request.headers.get("content-length")
        if declared is not None:
            if not declared.isdigit():
                return JSONResponse({"detail": "Invalid Content-Length"}, status_code=400)
            if int(declared) > settings.max_body_bytes:
                return JSONResponse({"detail": "Request too large"}, status_code=413)
        return await call_next(request)

    origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
    if origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_methods=["GET", "POST"],
            allow_headers=["Authorization", "Content-Type"],
            allow_credentials=False,
        )
    app.include_router(ai.router)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app
