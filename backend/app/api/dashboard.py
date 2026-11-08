from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List, Optional

from app.database import get_db
from app.models.disponibilidade import Disponibilidade
from app.models.motorista import Motorista
from app.models.user import User
from app.schemas.disponibilidade import (
    DashboardPorRotaResponse,
    DashboardTotalResponse,
    DashboardDiasResponse,
    RankingMotoristaResponse,
    DisponibilidadeResponse,
)
from app.services.auth_service import get_current_user

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/total", response_model=DashboardTotalResponse)
@router.get("/total/", response_model=DashboardTotalResponse, include_in_schema=False)
async def get_total(
    dia: Optional[int] = Query(None, ge=1, le=31),
    mes: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    base_query = select(func.count(Disponibilidade.id))
    podem_query = select(func.count(Disponibilidade.id)).where(
        Disponibilidade.pode_carregar_direto == "OK"
    )

    if dia:
        base_query = base_query.where(Disponibilidade.dia_disponivel == dia)
        podem_query = podem_query.where(Disponibilidade.dia_disponivel == dia)

    if mes:
        base_query = base_query.where(Disponibilidade.mes == mes)
        podem_query = podem_query.where(Disponibilidade.mes == mes)

    total_result = await db.execute(base_query)
    total = total_result.scalar() or 0

    podem_result = await db.execute(podem_query)
    podem = podem_result.scalar() or 0

    return DashboardTotalResponse(
        total_disponiveis=total,
        total_podem_carregar=podem,
        total_nao_podem=total - podem,
    )


@router.get("/dias", response_model=List[DashboardDiasResponse])
@router.get("/dias/", response_model=List[DashboardDiasResponse], include_in_schema=False)
async def get_dias_com_disponibilidade(
    mes: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = (
        select(
            Disponibilidade.dia_disponivel,
            func.count(Disponibilidade.id).label("count"),
        )
        .group_by(Disponibilidade.dia_disponivel)
        .order_by(Disponibilidade.dia_disponivel)
    )

    if mes:
        query = query.where(Disponibilidade.mes == mes)

    result = await db.execute(query)
    return [
        DashboardDiasResponse(dia=row[0], count=row[1])
        for row in result.all()
    ]


@router.get("/por-rota", response_model=List[DashboardPorRotaResponse])
@router.get("/por-rota/", response_model=List[DashboardPorRotaResponse], include_in_schema=False)
async def get_disponibilidade_por_rota(
    dia: Optional[int] = Query(None, ge=1, le=31),
    mes: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Get unique origens with counts
    count_query = (
        select(
            Disponibilidade.origem,
            func.count(Disponibilidade.id).label("count"),
        )
        .group_by(Disponibilidade.origem)
        .order_by(func.count(Disponibilidade.id).desc())
    )

    detail_query = select(Disponibilidade).order_by(
        Disponibilidade.data_conversa.desc()
    )

    if dia:
        count_query = count_query.where(Disponibilidade.dia_disponivel == dia)
        detail_query = detail_query.where(Disponibilidade.dia_disponivel == dia)
    if mes:
        count_query = count_query.where(Disponibilidade.mes == mes)
        detail_query = detail_query.where(Disponibilidade.mes == mes)

    count_result = await db.execute(count_query)
    detail_result = await db.execute(detail_query)

    all_disps = detail_result.scalars().all()

    # Group by origem
    origens_data = {}
    for row in count_result.all():
        origens_data[row[0]] = {"origem": row[0], "count": row[1], "motoristas": []}

    for disp in all_disps:
        if disp.origem in origens_data:
            origens_data[disp.origem]["motoristas"].append(
                DisponibilidadeResponse.model_validate(disp)
            )

    return list(origens_data.values())


@router.get("/ranking", response_model=List[RankingMotoristaResponse])
@router.get("/ranking/", response_model=List[RankingMotoristaResponse], include_in_schema=False)
async def get_ranking(
    mes: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = (
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

    if mes:
        query = query.where(Disponibilidade.mes == mes)

    result = await db.execute(query)

    ranking = []
    for row in result.all():
        # Get latest status for this driver
        latest_query = (
            select(Disponibilidade)
            .where(Disponibilidade.motorista_id == row[0])
            .order_by(Disponibilidade.data_conversa.desc())
            .limit(1)
        )
        if mes:
            latest_query = latest_query.where(Disponibilidade.mes == mes)

        latest_result = await db.execute(latest_query)
        latest = latest_result.scalar_one_or_none()

        ranking.append(
            RankingMotoristaResponse(
                motorista_id=row[0],
                motorista_nome=row[1],
                total_dias=row[2],
                pode_carregar=latest.pode_carregar_direto if latest else "NOK",
                cadastro=latest.cadastro if latest else "NOK",
                gr=latest.gr if latest else "NOK",
            )
        )

    return ranking
