import asyncio

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.services import auditoria_service, aceites_service, ranking_service, rotas_acompanhadas, scraper_ranking
from app.services.auth_service import get_current_user, require_admin

router = APIRouter(prefix="/api/estatisticas", tags=["estatisticas"])


@router.get("/aceites")
async def aceites_x_relatorio(
    dias: int = Query(7, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Aceitas detectadas no Smart Cargas x confirmadas no relatório, por dia e horário."""
    return await aceites_service.calcular_para_dias(db, dias)


@router.get("/ranking")
async def aceites_x_ranking(
    dias: int = Query(7, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Aceites do round anterior x o que apareceu no 1º/2º/3º lugar do Smart Cargas."""
    return await ranking_service.calcular_ranking(db, dias)


@router.get("/ranking/status")
async def status_ranking(user: User = Depends(get_current_user)):
    """Estado da leitura dos rankings (rodando agora, última mensagem, última leitura)."""
    return scraper_ranking.ranking_state


@router.post("/ranking/ler-agora")
async def ler_ranking_agora(user: User = Depends(get_current_user)):
    """Dispara a leitura dos rankings na hora (teste manual), sem esperar o início da hora."""
    if scraper_ranking.ranking_state["is_running"]:
        return {"ok": False, "status": "Já existe uma leitura em andamento."}
    asyncio.create_task(scraper_ranking.run_ranking_scraper())
    return {"ok": True, "status": "Leitura iniciada."}


@router.get("/rotas-acompanhadas/export")
async def exportar_rotas_acompanhadas(
    dias: int = Query(3650, ge=1, le=3650),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """CSV com cada carga (Pool e Smart) das rotas da lista de acompanhamento."""
    conteudo = await rotas_acompanhadas.exportar_csv(db, dias)
    return Response(
        content=conteudo.encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="cargas_rotas_acompanhadas.csv"'},
    )


@router.get("/rotas-acompanhadas/diagnostico")
async def diagnostico_rotas_acompanhadas(
    dias: int = Query(3650, ge=1, le=3650),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """CSV com as cargas que têm destino de uma rota da lista mas cuja origem não casou
    (possível código/nome de origem diferente do cadastrado na lista)."""
    conteudo = await rotas_acompanhadas.diagnostico_csv(db, dias)
    return Response(
        content=conteudo.encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="diagnostico_rotas_acompanhadas.csv"'},
    )


@router.get("/rotas-acompanhadas/resumo")
async def resumo_rotas_acompanhadas(
    dias: int = Query(3650, ge=1, le=3650),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """CSV-resumo (por rota, fonte e mês) das rotas da lista, o mesmo que o Assistente IA mostra."""
    conteudo = await rotas_acompanhadas.resumo_csv(db, dias)
    return Response(
        content=conteudo.encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="resumo_rotas_acompanhadas.csv"'},
    )


@router.get("/auditoria")
async def auditoria_dados(
    horas: int = Query(24, ge=1, le=720),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin),
):
    """Checagem somente leitura da consistência dos dados; `achados` vazio significa tudo certo."""
    achados = await auditoria_service.auditar(db, horas)
    return {"horas": horas, "ok": not achados, "achados": achados}
