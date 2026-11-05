from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.middleware import SecurityHeadersMiddleware
from app.routers import public, webhooks


def create_app() -> FastAPI:
    settings = get_settings()
    docs = not settings.is_production
    app = FastAPI(
        title="ComTho Shop API",
        docs_url="/api/docs" if docs else None,
        redoc_url=None,
        openapi_url="/api/openapi.json" if docs else None,
    )

    app.add_middleware(SecurityHeadersMiddleware)
    # Added last = outermost, so CORS preflights are answered first.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.public_origins,
        allow_credentials=False,  # no cookies; orders use a Bearer access token
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type"],
        max_age=600,
    )

    v1 = APIRouter(prefix="/api/v1")

    @v1.get("/health")
    def health():
        return {"ok": True}

    v1.include_router(public.router)
    v1.include_router(webhooks.router)
    app.include_router(v1)
    return app


app = create_app()
