import re
import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import Date, String, and_, case, cast, distinct, false, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.carga import Carga
from app.schemas.carga import (
    CargaBulkDeleteRequest,
    CargaCreate,
    CargaDeleteRequest,
    CargaListResponse,
    CargaOpcoesResponse,
    CargaResponse,
    CargaResumoResponse,
    CargaUpdateObservacao,
)
from app.api.auth import get_current_user
from app.models.user import User
from app.services.audit_service import log_action

router = APIRouter(
    prefix="/api/cargas",
    tags=["cargas"],
    responses={404: {"description": "Not found"}},
)

MESES = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]


def _data_captura_local(column):
    """Data de data_captura (armazenada em UTC) convertida para o horário de
    São Paulo antes do cast para Date, para bater com a data exibida no
    frontend (que usa toLocaleDateString no timezone local do navegador)."""
    return cast(func.timezone(cast("America/Sao_Paulo", String), column), Date)


def _mes_key_and_label(data_carregamento: Optional[str]):
    """Replica a lógica do frontend para extrair 'Mes/Ano' de datas em formato YYYY-MM-DD ou DD/MM/YYYY."""
    if data_carregamento:
        m = re.match(r"^(\d{4})-(\d{2})", data_carregamento)
        if m:
            ano, mes = m.group(1), m.group(2)
            return (ano, mes), f"{MESES[int(mes) - 1]}/{ano}"
        m = re.match(r"(\d{2})/(\d{2})/(\d{4})", data_carregamento)
        if m:
            _, mes, ano = m.groups()
            return (ano, mes), f"{MESES[int(mes) - 1]}/{ano}"
    return (None, None), "Indefinido"


def _round_label(round_hora: Optional[int]) -> str:
    if round_hora is None:
        return "Desconhecido"
    return f"Round das {round_hora:02d}h"


async def _resolve_data_carregamento_values(
    db: AsyncSession, dia_carregamento: List[str], mes: List[str]
) -> Optional[List[str]]:
    """
    dia_carregamento/mes filtram por um valor derivado (label de mês) que não existe
    como coluna. Resolve para a lista de valores brutos de data_carregamento que
    satisfazem o filtro, usando o pequeno conjunto de valores distintos da tabela
    (nunca a tabela inteira).

    Os dois filtros se combinam por AND (interseção), não OR: um dia já é mais
    específico que um mês, então "mês X + dia Y" deve restringir ao dia Y (e não
    voltar a mostrar o mês X inteiro, que era o bug antigo). Dentro de cada
    filtro isolado (vários dias, ou vários meses) continua sendo OR/multi-select.
    """
    if not dia_carregamento and not mes:
        return None

    result = await db.execute(select(distinct(Carga.data_carregamento)))
    todos = [v for v in result.scalars().all() if v]

    valores = set(todos)
    if dia_carregamento:
        valores &= {v for v in todos if v in dia_carregamento}
    if mes:
        valores &= {v for v in todos if _mes_key_and_label(v)[1] in mes}
    return list(valores)


async def _resolve_data_captura_dates(
    db: AsyncSession, dia_captura: List[str], mes_captura: List[str]
):
    """
    Mesma ideia de _resolve_data_carregamento_values, mas para data_captura
    (quando a carga foi absorvida pelo sistema): dia_captura filtra por dia
    exato ("dd/mm/aaaa"), mes_captura por label de mês ("Mmm/aaaa"), resolvida
    contra o pequeno conjunto de dias distintos já usado em /opcoes — nunca a
    tabela inteira.

    Os dois filtros se combinam por AND (interseção), não OR: um dia já é mais
    específico que um mês, então "mês X + dia Y" deve restringir ao dia Y (e não
    voltar a mostrar o mês X inteiro, que era o bug antigo). Dentro de cada
    filtro isolado (vários dias, ou vários meses) continua sendo OR/multi-select.
    """
    if not dia_captura and not mes_captura:
        return None

    result = await db.execute(select(_data_captura_local(Carga.data_captura)).distinct())
    todos = [v for v in result.scalars().all() if v]

    valores = set(todos)
    if dia_captura:
        dias_desejados = set()
        for d in dia_captura:
            try:
                dias_desejados.add(datetime.strptime(d, "%d/%m/%Y").date())
            except ValueError:
                continue
        valores &= {v for v in todos if v in dias_desejados}
    if mes_captura:
        valores &= {v for v in todos if _mes_key_and_label(v.strftime("%Y-%m-%d"))[1] in mes_captura}
    return list(valores)


def _build_filters(
    *,
    origem: Optional[str],
    destino: Optional[str],
    busca: Optional[str],
    tipo_carga: List[str],
    fonte: List[str],
    round_hora: List[str],
    data_captura_dates: Optional[List],
    data_carregamento_values: Optional[List[str]],
):
    conditions = []

    if origem:
        conditions.append(Carga.origem.ilike(f"%{origem}%"))
    if destino:
        conditions.append(Carga.destino.ilike(f"%{destino}%"))
    if busca:
        like = f"%{busca}%"
        conditions.append(
            or_(
                Carga.origem.ilike(like),
                Carga.destino.ilike(like),
                Carga.tipo_caminhao.ilike(like),
                Carga.load_id.ilike(like),
            )
        )
    if tipo_carga:
        conditions.append(Carga.tipo_carga.in_(tipo_carga))
    if fonte:
        conditions.append(Carga.fonte.in_(fonte))

    if round_hora:
        round_values = []
        include_null = False
        for label in round_hora:
            if label == "Desconhecido":
                include_null = True
            else:
                m = re.search(r"(\d+)", label)
                if m:
                    round_values.append(int(m.group(1)))
        round_cond = []
        if round_values:
            round_cond.append(Carga.round_hora.in_(round_values))
        if include_null:
            round_cond.append(Carga.round_hora.is_(None))
        if round_cond:
            conditions.append(or_(*round_cond))

    if data_captura_dates is not None:
        if data_captura_dates:
            conditions.append(_data_captura_local(Carga.data_captura).in_(data_captura_dates))
        else:
            # Filtro de dia/mês de absorção selecionado mas sem correspondência: nenhum resultado.
            conditions.append(false())

    if data_carregamento_values is not None:
        if data_carregamento_values:
            conditions.append(Carga.data_carregamento.in_(data_carregamento_values))
        else:
            # Filtro de dia/mês selecionado mas sem correspondência nos dados: nenhum resultado.
            conditions.append(false())

    return conditions


async def _get_filter_conditions(
    db: AsyncSession,
    origem: Optional[str],
    destino: Optional[str],
    busca: Optional[str],
    tipo_carga: List[str],
    fonte: List[str],
    round_hora: List[str],
    dia_captura: List[str],
    mes_captura: List[str],
    dia_carregamento: List[str],
    mes: List[str],
):
    data_carregamento_values = await _resolve_data_carregamento_values(db, dia_carregamento, mes)
    data_captura_dates = await _resolve_data_captura_dates(db, dia_captura, mes_captura)
    return _build_filters(
        origem=origem,
        destino=destino,
        busca=busca,
        tipo_carga=tipo_carga,
        fonte=fonte,
        round_hora=round_hora,
        data_captura_dates=data_captura_dates,
        data_carregamento_values=data_carregamento_values,
    )


@router.get("", response_model=CargaListResponse)
async def get_cargas(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100000),
    origem: Optional[str] = None,
    destino: Optional[str] = None,
    busca: Optional[str] = None,
    tipo_carga: List[str] = Query(default=[]),
    fonte: List[str] = Query(default=[]),
    round_hora: List[str] = Query(default=[]),
    dia_captura: List[str] = Query(default=[]),
    mes_captura: List[str] = Query(default=[]),
    dia_carregamento: List[str] = Query(default=[]),
    mes: List[str] = Query(default=[]),
    db: AsyncSession = Depends(get_db),
):
    """
    Lista cargas paginadas, com filtros aplicados no banco (não mais trazendo
    a tabela inteira para o cliente a cada requisição).
    """
    conditions = await _get_filter_conditions(
        db, origem, destino, busca, tipo_carga, fonte, round_hora, dia_captura, mes_captura, dia_carregamento, mes
    )

    count_stmt = select(func.count()).select_from(Carga)
    stmt = select(Carga).order_by(Carga.data_captura.desc()).offset(skip).limit(limit)
    if conditions:
        count_stmt = count_stmt.where(and_(*conditions))
        stmt = stmt.where(and_(*conditions))

    total = (await db.execute(count_stmt)).scalar_one()
    result = await db.execute(stmt)
    cargas = result.scalars().all()

    return {"items": cargas, "total": total}


@router.get("/resumo", response_model=CargaResumoResponse)
async def get_resumo(
    origem: Optional[str] = None,
    destino: Optional[str] = None,
    busca: Optional[str] = None,
    tipo_carga: List[str] = Query(default=[]),
    fonte: List[str] = Query(default=[]),
    round_hora: List[str] = Query(default=[]),
    dia_captura: List[str] = Query(default=[]),
    mes_captura: List[str] = Query(default=[]),
    dia_carregamento: List[str] = Query(default=[]),
    mes: List[str] = Query(default=[]),
    db: AsyncSession = Depends(get_db),
):
    """
    KPIs e dados de gráfico calculados no banco para o conjunto filtrado
    inteiro (não apenas a página atual), sem transferir cada linha ao cliente.
    """
    conditions = await _get_filter_conditions(
        db, origem, destino, busca, tipo_carga, fonte, round_hora, dia_captura, mes_captura, dia_carregamento, mes
    )

    valor_case = case(
        (
            and_(Carga.valor > 0, Carga.valor < 1000, Carga.peso_kg > 0),
            Carga.valor * (Carga.peso_kg / 1000.0),
        ),
        else_=func.coalesce(Carga.valor, 0),
    )

    agg_stmt = select(
        func.coalesce(func.sum(Carga.quantidade), 0),
        func.coalesce(func.sum(func.coalesce(Carga.peso_kg, 0) * Carga.quantidade), 0),
        func.coalesce(func.sum(valor_case * Carga.quantidade), 0),
    )
    por_dia_stmt = select(Carga.data_carregamento, func.sum(Carga.quantidade)).group_by(Carga.data_carregamento)

    if conditions:
        agg_stmt = agg_stmt.where(and_(*conditions))
        por_dia_stmt = por_dia_stmt.where(and_(*conditions))

    total_cargas, peso_total, valor_total = (await db.execute(agg_stmt)).one()
    por_dia_rows = (await db.execute(por_dia_stmt)).all()

    por_dia = sorted(
        [{"dia": dia or "Indefinido", "quantidade": int(qtd)} for dia, qtd in por_dia_rows],
        key=lambda x: x["dia"],
    )

    mes_counts = {}
    for dia, qtd in por_dia_rows:
        key, label = _mes_key_and_label(dia)
        atual = mes_counts.get(label, (key, 0))
        mes_counts[label] = (key, atual[1] + int(qtd))

    por_mes = [
        {"mes": label, "quantidade": qtd}
        for label, (key, qtd) in sorted(mes_counts.items(), key=lambda item: (item[1][0] is None, item[1][0]))
    ]

    return {
        "total_cargas": int(total_cargas),
        "valor_total": float(valor_total),
        "peso_total": float(peso_total),
        "por_dia": por_dia,
        "por_mes": por_mes,
    }


@router.get("/opcoes", response_model=CargaOpcoesResponse)
async def get_opcoes(db: AsyncSession = Depends(get_db)):
    """
    Valores distintos para popular os dropdowns de filtro, calculados a partir
    da tabela inteira (independente dos filtros atualmente selecionados),
    sem nunca carregar as linhas completas de cargas.
    """
    tipos = (await db.execute(select(distinct(Carga.tipo_carga)).where(Carga.tipo_carga.isnot(None)))).scalars().all()
    fontes = (await db.execute(select(distinct(Carga.fonte)))).scalars().all()
    rounds_raw = (await db.execute(select(distinct(Carga.round_hora)))).scalars().all()
    dias_carregamento_raw = (await db.execute(select(distinct(Carga.data_carregamento)))).scalars().all()
    dias_captura_raw = (
        (await db.execute(select(_data_captura_local(Carga.data_captura)).distinct())).scalars().all()
    )

    meses_map = {}
    for d in dias_carregamento_raw:
        key, label = _mes_key_and_label(d)
        if label != "Indefinido":
            meses_map[key] = label

    meses_captura_map = {}
    for d in dias_captura_raw:
        if not d:
            continue
        key, label = _mes_key_and_label(d.strftime("%Y-%m-%d"))
        if label != "Indefinido":
            meses_captura_map[key] = label

    dias_captura_fmt = sorted({d.strftime("%d/%m/%Y"): d for d in dias_captura_raw if d}.items(), key=lambda kv: kv[1])

    return {
        "tipos_carga": sorted({t for t in tipos if t}),
        "dias_carregamento": sorted({d for d in dias_carregamento_raw if d}),
        "dias_captura": [k for k, _ in dias_captura_fmt],
        "meses_captura_disponiveis": [label for _, label in sorted(meses_captura_map.items())],
        "rounds": sorted({_round_label(r) for r in rounds_raw}),
        "fontes": sorted({f for f in fontes if f}),
        "meses_disponiveis": [label for _, label in sorted(meses_map.items())],
    }


@router.post("/sync", response_model=dict)
async def sync_cargas(cargas_in: List[CargaCreate], db: AsyncSession = Depends(get_db)):
    """
    Internal endpoint to sync scraped cargas.
    In a real scenario, you'd protect this with a secret token or specific user role.
    For simplicity, we'll allow the scraper to hit it.
    """
    # Simple approach: deactivate or delete old 'Aguardando aceite' ones and insert new ones
    # Or just insert all and the dashboard shows the latest ones based on data_captura

    # For now, we just insert them as they arrive from the scraper.
    # We could improve this by checking if the Carga already exists to update it.

    for c_in in cargas_in:
        new_carga = Carga(**c_in.model_dump())
        db.add(new_carga)

    await db.commit()
    return {"message": f"Successfully synced {len(cargas_in)} cargas"}


@router.patch("/{id}/outra-tp", response_model=CargaResponse)
async def mark_as_outra_tp(id: str, carga_update: CargaUpdateObservacao, db: AsyncSession = Depends(get_db)):
    """
    Mark a carga as 'Outra TP' and add the observation.
    """
    try:
        carga_id = uuid.UUID(id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid UUID")

    result = await db.execute(select(Carga).where(Carga.id == carga_id))
    carga = result.scalar_one_or_none()

    if not carga:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Carga not found")

    carga.status_portal = "Outra TP"
    if hasattr(carga_update, 'observacao'):
        carga.observacao = carga_update.observacao

    await db.commit()
    await db.refresh(carga)

    return carga


@router.delete("/{id}", response_model=dict)
async def delete_carga(
    id: str,
    payload: CargaDeleteRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Exclui definitivamente uma carga da listagem e de todos os dashboards
    (a exclusão é feita direto no banco). Exige justificativa e fica
    registrada na trilha de auditoria (/api/audit) com a rota e o motivo.
    """
    try:
        carga_id = uuid.UUID(id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid UUID")

    result = await db.execute(select(Carga).where(Carga.id == carga_id))
    carga = result.scalar_one_or_none()

    if not carga:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Carga not found")

    detalhes = (
        f"{carga.origem} → {carga.destino} | Load ID: {carga.load_id or '-'} | "
        f"Fonte: {carga.fonte} | Motivo: {payload.motivo}"
    )
    await log_action(db, current_user, "DELETE_CARGA", "carga", str(carga.id), detalhes)

    await db.delete(carga)
    await db.commit()

    return {"message": "Carga excluída com sucesso"}


@router.post("/bulk-delete", response_model=dict)
async def bulk_delete_cargas(
    payload: CargaBulkDeleteRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Exclui várias cargas de uma vez (mesma justificativa para todas).
    Limitado a 200 IDs por chamada — não existe endpoint para excluir a
    tabela inteira de uma vez, seleção precisa ser explícita item a item.
    """
    result = await db.execute(select(Carga).where(Carga.id.in_(payload.ids)))
    cargas = result.scalars().all()

    if not cargas:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Nenhuma carga encontrada para os IDs informados")

    for carga in cargas:
        detalhes = (
            f"{carga.origem} → {carga.destino} | Load ID: {carga.load_id or '-'} | "
            f"Fonte: {carga.fonte} | Motivo: {payload.motivo}"
        )
        await log_action(db, current_user, "DELETE_CARGA", "carga", str(carga.id), detalhes)
        await db.delete(carga)

    await db.commit()

    return {"message": f"{len(cargas)} carga(s) excluída(s) com sucesso"}
