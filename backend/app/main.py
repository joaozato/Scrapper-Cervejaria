import os
import sys
import asyncio

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.config import settings
from app.rate_limit import limiter
from app.api import auth, motoristas, disponibilidades, dashboard, websocket, sheets_sync, cargas, monitor, audit, matches, relatorios_carga, erp_integration, insights, integrations, assistente_ia, estatisticas

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("cargo")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup/shutdown."""
    logger.info("🚀 CARGO Disponibilidade API starting up...")

    # Database migrations and initialization
    from app.services.startup import run_startup_migrations
    await run_startup_migrations()

    # Start Google Sheets sync background task
    sync_task = None
    if settings.SHEETS_SYNC_ENABLED:
        from app.services.sheets_sync import start_sheets_sync
        sync_task = asyncio.create_task(start_sheets_sync())
        logger.info("📊 Google Sheets sync background task started")

    # Start Portal Scraper background task
    scraper_task = None
    if settings.PORTAL_SCRAPER_ENABLED and settings.PORTAL_USER and settings.PORTAL_PASS:
        from app.services.scraper_portal import start_scraper_scheduler
        scraper_task = asyncio.create_task(start_scraper_scheduler())
        logger.info("🤖 Portal Scraper background task started")

    yield

    # Cancel sync task on shutdown
    if sync_task:
        sync_task.cancel()
        try:
            await sync_task
        except asyncio.CancelledError:
            pass
            
    if scraper_task:
        scraper_task.cancel()
        try:
            await scraper_task
        except asyncio.CancelledError:
            pass
            
    logger.info("🛑 CARGO Disponibilidade API shutting down...")


app = FastAPI(
    title="CARGO Disponibilidade API",
    description="API para controle de disponibilidade de caminhoneiros - a transportadora",
    version="1.0.0",
    lifespan=lifespan,
)

# Rate limiting: default_limits (app/rate_limit.py) apply a global baseline
# (200/min por IP) contra flood em qualquer rota; endpoints sensíveis (ex.:
# login) declaram seu próprio @limiter.limit(...) mais apertado.
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(auth.router)
app.include_router(motoristas.router)
app.include_router(disponibilidades.router)
app.include_router(dashboard.router)
app.include_router(websocket.router)
app.include_router(sheets_sync.router)
app.include_router(cargas.router)
app.include_router(monitor.router, prefix="/api/scraper/monitor", tags=["monitor"])
app.include_router(audit.router)
app.include_router(matches.router)
app.include_router(relatorios_carga.router)
app.include_router(erp_integration.router)
app.include_router(insights.router)
app.include_router(assistente_ia.router)
app.include_router(estatisticas.router)
app.include_router(integrations.router)


@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "service": "CARGO Disponibilidade API"}


# Serve static frontend files if STATIC_DIR exists (Production / Monolithic mode)
if os.path.exists(settings.STATIC_DIR):
    assets_dir = os.path.join(settings.STATIC_DIR, "assets")
    if os.path.exists(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(request: Request, full_path: str):
        # Do not catch API or websocket endpoints
        if (
            full_path.startswith("api")
            or full_path.startswith("ws")
            or full_path == "docs"
            or full_path == "redoc"
            or full_path == "openapi.json"
        ):
            raise HTTPException(status_code=404, detail="Not Found")

        # Check if requested path is an existing static file (e.g. favicon.ico, images)
        file_path = os.path.join(settings.STATIC_DIR, full_path)
        if os.path.isfile(file_path):
            return FileResponse(file_path)

        # Fallback to index.html for React Router (SPA routing)
        index_path = os.path.join(settings.STATIC_DIR, "index.html")
        if os.path.exists(index_path):
            return FileResponse(index_path)

        raise HTTPException(status_code=404, detail="Not Found")
