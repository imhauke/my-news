from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.config import Settings, get_settings
from app.logging import configure_logging


def create_app(settings: Settings) -> FastAPI:
    # The interactive docs (/docs, /redoc) and the schema (/openapi.json) are generated from the
    # routes; API_DOCS=false turns all three off, e.g. in production.
    docs = settings.api_docs
    app = FastAPI(
        title="MyNews API",
        version="0.1.0",
        docs_url="/docs" if docs else None,
        redoc_url="/redoc" if docs else None,
        openapi_url="/openapi.json" if docs else None,
    )
    app.add_middleware(
        CORSMiddleware, allow_origins=settings.cors_origin_list, allow_methods=["GET", "POST"], allow_headers=["*"]
    )
    app.include_router(router)
    return app


settings = get_settings()
configure_logging(settings.log_level)
app = create_app(settings)
