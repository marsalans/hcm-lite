from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from hcm_ai.agent.tracing import configure_tracing
from hcm_ai.config import get_settings
from hcm_ai.db import init_db
from hcm_ai.routers import ai, auth, dashboard
from hcm_ai.services.errors import NotFound, PermissionDenied

WEB_DIR = Path(__file__).parent / "web"

_CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
    "font-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; "
    "form-action 'self'; frame-ancestors 'none'"
)
_DOC_PATHS = ("/docs", "/redoc", "/openapi.json")  # Swagger UI needs a CDN; no CSP there
_API_PREFIXES = ("/ai", "/dashboard", "/auth")

Next = Callable[[Request], Awaitable[Response]]


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
    async def limit_body_size(request: Request, call_next: Next) -> Response:
        # Declared size only; chunked uploads must also be capped at the reverse proxy.
        declared = request.headers.get("content-length")
        if declared is not None:
            if not declared.isdigit():
                return JSONResponse({"detail": "Invalid Content-Length"}, status_code=400)
            if int(declared) > settings.max_body_bytes:
                return JSONResponse({"detail": "Request too large"}, status_code=413)
        return await call_next(request)

    @app.middleware("http")
    async def security_headers(request: Request, call_next: Next) -> Response:
        response = await call_next(request)
        path = request.url.path
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        if not path.startswith(_DOC_PATHS):
            response.headers["Content-Security-Policy"] = _CSP
            response.headers["X-Frame-Options"] = "DENY"
        # Never cache API data; keep UI files revalidated so edits show up immediately.
        no_store = path.startswith(_API_PREFIXES) or path == "/health"
        response.headers["Cache-Control"] = "no-store" if no_store else "no-cache"
        return response

    @app.exception_handler(PermissionDenied)
    async def _forbidden(_: Request, __: PermissionDenied) -> JSONResponse:
        return JSONResponse({"detail": "Forbidden"}, status_code=403)

    @app.exception_handler(NotFound)
    async def _not_found(_: Request, exc: NotFound) -> JSONResponse:
        return JSONResponse({"detail": str(exc) or "Not found"}, status_code=404)

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
    app.include_router(dashboard.router)
    app.include_router(auth.router)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    # Last, so the API routes above win. The UI is plain files: no build step.
    if WEB_DIR.is_dir():
        app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
    return app
