from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.user import User
from app.services import insights_service
from app.services.auth_service import get_current_user

router = APIRouter(prefix="/api/insights", tags=["insights"])


class PerguntaIn(BaseModel):
    pergunta: str = Field(..., min_length=3, max_length=500)
    dias: int = Field(7, ge=1, le=3650)
    insumos: list[str] = Field(default_factory=list)
    fonte: str = "pool"


class ResumoIn(BaseModel):
    dias: int = Field(7, ge=1, le=3650)
    insumos: list[str] = Field(default_factory=list)
    fonte: str = "pool"
    usar_ia: bool = True


@router.get("/insumos")
async def listar_insumos(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Insumos disponíveis para filtrar (Lata, Arroz, Malte...)."""
    return {"insumos": await insights_service.listar_insumos(db)}


@router.get("/cargas")
async def insights_cargas(
    dias: int = Query(7, ge=1, le=3650),
    insumos: str = Query("", description="Insumos separados por vírgula; vazio = todos"),
    fonte: str = Query("pool", description="pool | prioritaria | ambos"),
    narrativa: bool = Query(False, description="Pede também a análise em texto da LLM"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    metricas = await insights_service.calcular_com_anomalias(db, dias, insights_service.normalizar_insumos(insumos), insights_service.normalizar_fonte(fonte))
    com_dados = insights_service.tem_dados(metricas)
    # Sem dados no período não chama a LLM (não gasta token à toa).
    texto = await insights_service.gerar_narrativa(metricas, db) if narrativa and com_dados else None
    return {
        "tem_dados": com_dados,
        "uso_api": await insights_service.uso_total(db),
        "metricas": metricas,
        "destaques": insights_service.montar_destaques(metricas),
        "llm_disponivel": bool(settings.GEMINI_API_KEY),
        "narrativa": texto,
    }


@router.post("/perguntar")
async def perguntar(
    body: PerguntaIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Pergunta livre sobre os dados do período. Cada chamada consome tokens."""
    if not settings.GEMINI_API_KEY:
        raise HTTPException(status_code=503, detail="IA não configurada (GEMINI_API_KEY ausente).")
    metricas = await insights_service.calcular_metricas(db, body.dias, insumos=insights_service.normalizar_insumos(body.insumos), fonte=insights_service.normalizar_fonte(body.fonte))
    if not insights_service.tem_dados(metricas):
        return {"resposta": "Não há dados no período/insumo escolhido para responder. Tente um período maior.", "uso_api": await insights_service.uso_total(db)}
    resposta = await insights_service.responder_pergunta(metricas, body.pergunta.strip(), db)
    if not resposta:
        raise HTTPException(status_code=502, detail="A IA não respondeu agora. Tente novamente em instantes.")
    return {"resposta": resposta, "uso_api": await insights_service.uso_total(db)}


@router.post("/resumo")
async def resumo_para_enviar(
    body: ResumoIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Texto curto pronto pra mandar (WhatsApp/e-mail). Sem IA, devolve o modelo fixo."""
    metricas = await insights_service.calcular_com_anomalias(db, body.dias, insights_service.normalizar_insumos(body.insumos), insights_service.normalizar_fonte(body.fonte))
    if body.usar_ia and insights_service.tem_dados(metricas):
        resultado = await insights_service.gerar_resumo_envio(metricas, db)
    else:
        resultado = {"texto": insights_service.resumo_deterministico(metricas), "origem": "modelo"}
    resultado["uso_api"] = await insights_service.uso_total(db)
    return resultado
