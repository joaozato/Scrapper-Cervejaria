from fastapi import APIRouter, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
from app.services.scraper_state import scraper_state, update_status
from app.services.scraper_portal import run_scraper
import os

router = APIRouter()

# Helper path to static
STATIC_PATH = os.path.join(os.path.dirname(__file__), "..", "static", "live_view.jpg")

@router.get("/status")
async def get_monitor_status():
    return JSONResponse(content=scraper_state)

@router.get("/stream")
async def get_monitor_stream():
    if os.path.exists(STATIC_PATH):
        return FileResponse(
            STATIC_PATH, 
            media_type="image/jpeg",
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0"
            }
        )
    return JSONResponse(status_code=404, content={"message": "No live view available"})

import asyncio

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models.user import User
from app.services.auth_service import require_admin
from app.services.audit_service import log_action

@router.post("/run")
async def trigger_scraper(
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(require_admin)
):
    if scraper_state.get("is_running"):
        return JSONResponse(status_code=400, content={"message": "Scraper já está rodando."})
    
    scraper_state["cancel_requested"] = False
    update_status("Iniciando execução manual forçada...", is_running=True)
    
    await log_action(db, admin_user, "START_SCRAPER", "system", None, "Iniciou o scraper manualmente")
    await db.commit()
    
    async def run_async_task():
        try:
            await run_scraper()
        except Exception as e:
            update_status(f"Falha fatal ao iniciar Scraper: {str(e)}", is_running=False)
        
    background_tasks.add_task(run_async_task)
    return {"message": "Execução iniciada em background."}

from app.services.scraper_portal import run_report_scraper

@router.post("/run-report")
async def trigger_report_scraper(
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(require_admin)
):
    if scraper_state.get("is_running"):
        return JSONResponse(status_code=400, content={"message": "Scraper já está rodando."})

    await log_action(db, admin_user, "START_REPORT_SCRAPER", "system", None, "Iniciou o scraper de relatório manualmente")
    await db.commit()

    # Não seta is_running=True aqui: quem faz isso agora é o próprio
    # run_report_scraper (mesma trava usada pelos disparos agendados de hora
    # em hora), pra não fazer essa checagem sempre achar que já tem outro
    # rodando quando na verdade é só este mesmo disparo manual.
    async def run_async_task():
        try:
            await run_report_scraper(origem_captura="manual", executado_por_id=admin_user.id)
        except Exception as e:
            update_status(f"Falha ao iniciar Scraper de Relatório: {str(e)}", is_running=False)

    background_tasks.add_task(run_async_task)
    return {"message": "Busca de relatório iniciada em background."}

@router.post("/stop")
async def stop_scraper(admin_user: User = Depends(require_admin)):
    if not scraper_state.get("is_running"):
        return JSONResponse(status_code=400, content={"message": "Scraper já está inativo."})
    
    scraper_state["cancel_requested"] = True
    update_status("Parada solicitada pelo usuário. Encerrando...", is_running=True)
    return {"message": "Sinal de parada enviado ao Scraper."}
