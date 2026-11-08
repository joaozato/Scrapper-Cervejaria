import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.relatorio_carga import RelatorioCaptura, RelatorioCargaDiff
from app.models.user import User
from app.services.auth_service import require_admin

router = APIRouter(
    prefix="/api/integracoes/erp",
    tags=["integracoes-erp"],
)


@router.post("/export")
async def exportar_para_erp(
    relatorio_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(require_admin),
):
    """Envia as cargas confirmadas de uma captura de relatório para o ERP.

    Desligado por padrão (ERP_INTEGRATION_ENABLED=False): a rota fica pronta
    (payload já é montado a partir das cargas elegíveis), mas o envio real
    ainda não é implementado — evita abrir uma integração externa sem
    necessidade/validação ainda.
    """
    if not settings.ERP_INTEGRATION_ENABLED:
        raise HTTPException(status_code=403, detail="Integração com ERP ainda não habilitada")

    captura = await db.get(RelatorioCaptura, relatorio_id)
    if not captura:
        raise HTTPException(status_code=404, detail="Relatório não encontrado")

    itens_elegiveis = (
        (await db.execute(
            select(RelatorioCargaDiff).where(
                RelatorioCargaDiff.relatorio_atual_id == relatorio_id,
                RelatorioCargaDiff.elegivel_erp == True,  # noqa: E712
            )
        )).scalars().all()
    )

    # TODO: implementar o envio real ao ERP quando a integração for validada.
    raise HTTPException(status_code=501, detail="Envio ao ERP ainda não implementado")
