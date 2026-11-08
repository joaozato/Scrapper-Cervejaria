from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from uuid import UUID
from typing import List, Optional
from datetime import datetime, timezone

from app.database import get_db
from app.models.disponibilidade import Disponibilidade
from app.models.motorista import Motorista
from app.models.user import User
from app.schemas.disponibilidade import (
    DisponibilidadeCreate,
    DisponibilidadeUpdate,
    DisponibilidadeResponse,
)
from app.services.auth_service import get_current_user, require_admin
from app.services.agents import (
    notify_disponibilidade_change,
    notify_dashboard_refresh,
    notify_ranking_update,
)
from app.services.audit_service import log_action

router = APIRouter(prefix="/api/disponibilidades", tags=["disponibilidades"])


async def _build_dashboard_data(db: AsyncSession) -> dict:
    """Build aggregated dashboard data for broadcast."""
    # Total counts
    total_result = await db.execute(select(func.count(Disponibilidade.id)))
    total = total_result.scalar() or 0

    podem_result = await db.execute(
        select(func.count(Disponibilidade.id))
        .where(Disponibilidade.pode_carregar_direto == "OK")
    )
    podem = podem_result.scalar() or 0

    # Days with availability
    dias_result = await db.execute(
        select(
            Disponibilidade.dia_disponivel,
            func.count(Disponibilidade.id).label("count"),
        )
        .group_by(Disponibilidade.dia_disponivel)
        .order_by(Disponibilidade.dia_disponivel)
    )
    dias = [{"dia": row[0], "count": row[1]} for row in dias_result.all()]

    # Origem distribution
    origens_result = await db.execute(
        select(
            Disponibilidade.origem,
            func.count(Disponibilidade.id).label("count"),
        )
        .group_by(Disponibilidade.origem)
        .order_by(func.count(Disponibilidade.id).desc())
    )
    origens = [{"origem": row[0], "count": row[1]} for row in origens_result.all()]

    return {
        "total_disponiveis": total,
        "total_podem_carregar": podem,
        "total_nao_podem": total - podem,
        "dias": dias,
        "origens": origens,
    }


async def _build_ranking_data(db: AsyncSession) -> list:
    """Build ranking of drivers by number of available days."""
    result = await db.execute(
        select(
            Motorista.id,
            Motorista.nome,
            func.count(Disponibilidade.id).label("total_dias"),
        )
        .join(Disponibilidade, Motorista.id == Disponibilidade.motorista_id)
        .group_by(Motorista.id, Motorista.nome)
        .order_by(func.count(Disponibilidade.id).desc())
        .limit(20)
    )
    ranking = []
    for row in result.all():
        # Get latest cadastro/gr status for this driver
        latest = await db.execute(
            select(Disponibilidade)
            .where(Disponibilidade.motorista_id == row[0])
            .order_by(Disponibilidade.data_conversa.desc())
            .limit(1)
        )
        latest_disp = latest.scalar_one_or_none()
        ranking.append({
            "motorista_id": str(row[0]),
            "motorista_nome": row[1],
            "total_dias": row[2],
            "pode_carregar": latest_disp.pode_carregar_direto if latest_disp else "NOK",
            "cadastro": latest_disp.cadastro if latest_disp else "NOK",
            "gr": latest_disp.gr if latest_disp else "NOK",
        })
    return ranking


@router.get("", response_model=List[DisponibilidadeResponse])
@router.get("/", response_model=List[DisponibilidadeResponse], include_in_schema=False)
async def list_disponibilidades(
    mes: Optional[str] = Query(None),
    dia: Optional[int] = Query(None, ge=1, le=31),
    motorista_id: Optional[UUID] = Query(None),
    pode_carregar: Optional[str] = Query(None, pattern="^(OK|NOK)$"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(Disponibilidade).order_by(Disponibilidade.data_conversa.desc())

    if mes:
        query = query.where(Disponibilidade.mes == mes)
    if dia:
        query = query.where(Disponibilidade.dia_disponivel == dia)
    if motorista_id:
        query = query.where(Disponibilidade.motorista_id == motorista_id)
    if pode_carregar:
        query = query.where(Disponibilidade.pode_carregar_direto == pode_carregar)

    result = await db.execute(query)
    return [DisponibilidadeResponse.model_validate(d) for d in result.scalars().all()]


@router.get("/{disp_id}", response_model=DisponibilidadeResponse)
async def get_disponibilidade(
    disp_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Disponibilidade).where(Disponibilidade.id == disp_id)
    )
    disp = result.scalar_one_or_none()
    if not disp:
        raise HTTPException(status_code=404, detail="Disponibilidade não encontrada")
    return DisponibilidadeResponse.model_validate(disp)


@router.post("", response_model=DisponibilidadeResponse, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=DisponibilidadeResponse, status_code=status.HTTP_201_CREATED, include_in_schema=False)
async def create_disponibilidade(
    data: DisponibilidadeCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Verify motorista exists
    result = await db.execute(
        select(Motorista).where(Motorista.id == data.motorista_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Motorista não encontrado")

    disp = Disponibilidade(
        **data.model_dump(),
        data_conversa=datetime.now(timezone.utc),
        updated_by=current_user.id,
    )
    disp.compute_pode_carregar()

    db.add(disp)
    await log_action(db, current_user, "CREATE_DISP", "disponibilidade", str(disp.id), f"Adicionou disp p/ origem: {disp.origem}")
    await db.commit()
    await db.refresh(disp)

    # Agents: broadcast updates
    response_data = DisponibilidadeResponse.model_validate(disp).model_dump(mode="json")
    await notify_disponibilidade_change("create", response_data)

    dashboard_data = await _build_dashboard_data(db)
    await notify_dashboard_refresh(dashboard_data)

    ranking_data = await _build_ranking_data(db)
    await notify_ranking_update(ranking_data)

    return DisponibilidadeResponse.model_validate(disp)


@router.put("/{disp_id}", response_model=DisponibilidadeResponse)
async def update_disponibilidade(
    disp_id: UUID,
    data: DisponibilidadeUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Disponibilidade).where(Disponibilidade.id == disp_id)
    )
    disp = result.scalar_one_or_none()
    if not disp:
        raise HTTPException(status_code=404, detail="Disponibilidade não encontrada")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(disp, key, value)

    # Always update data_conversa and updated_by on any change unless explicitly provided
    if "data_conversa" not in update_data:
        disp.data_conversa = datetime.now(timezone.utc)
    disp.updated_by = current_user.id
    disp.updated_at = datetime.now(timezone.utc)

    # Recompute pode_carregar_direto
    disp.compute_pode_carregar()

    await log_action(db, current_user, "UPDATE_DISP", "disponibilidade", str(disp.id), f"Atualizou disp de {disp.origem}")
    await db.commit()
    await db.refresh(disp)

    # Agents: broadcast updates
    response_data = DisponibilidadeResponse.model_validate(disp).model_dump(mode="json")
    await notify_disponibilidade_change("update", response_data)

    dashboard_data = await _build_dashboard_data(db)
    await notify_dashboard_refresh(dashboard_data)

    ranking_data = await _build_ranking_data(db)
    await notify_ranking_update(ranking_data)

    return DisponibilidadeResponse.model_validate(disp)


@router.delete("/{disp_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_disponibilidade(
    disp_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    result = await db.execute(
        select(Disponibilidade).where(Disponibilidade.id == disp_id)
    )
    disp = result.scalar_one_or_none()
    if not disp:
        raise HTTPException(status_code=404, detail="Disponibilidade não encontrada")

    disp_data = DisponibilidadeResponse.model_validate(disp).model_dump(mode="json")
    await db.delete(disp)
    await log_action(db, current_user, "DELETE_DISP", "disponibilidade", str(disp.id), f"Deletou disp de {disp.origem}")
    await db.commit()

    # Agents: broadcast deletion
    await notify_disponibilidade_change("delete", disp_data)

    dashboard_data = await _build_dashboard_data(db)
    await notify_dashboard_refresh(dashboard_data)

    ranking_data = await _build_ranking_data(db)
    await notify_ranking_update(ranking_data)
