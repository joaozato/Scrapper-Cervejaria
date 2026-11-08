from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.user import User
from app.services import assistente_ia_service, insights_service
from app.services.auth_service import get_current_user

router = APIRouter(prefix="/api/assistente-ia", tags=["assistente-ia"])


class MensagemIn(BaseModel):
    papel: Literal["user", "ia"]
    texto: str = Field(..., max_length=2000)


class ChatIn(BaseModel):
    pergunta: str = Field(..., min_length=3, max_length=500)
    historico: list[MensagemIn] = Field(default_factory=list, max_length=12)


@router.post("/chat")
async def chat(
    body: ChatIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Chat restrito a cargas: perguntas fora do tema recebem uma recusa fixa."""
    if not settings.GEMINI_API_KEY:
        raise HTTPException(status_code=503, detail="IA não configurada (GEMINI_API_KEY ausente).")
    try:
        resultado = await assistente_ia_service.conversar(
            body.pergunta.strip(), [m.model_dump() for m in body.historico], db
        )
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    resultado["uso_api"] = await insights_service.uso_total(db)
    return resultado
