import csv
import logging
import uuid
from datetime import date, datetime
from typing import Optional
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.relatorio_carga import RelatorioCaptura, RelatorioCargaItem, RelatorioCargaDiff

logger = logging.getLogger("cargo.relatorio_carga")

SAO_PAULO = ZoneInfo("America/Sao_Paulo")


def _col(row: dict, nome: str) -> str:
    """Busca o valor de uma coluna do CSV por nome exato (chaves variam de
    acordo com o encoding/BOM lido pelo csv.DictReader)."""
    return (row.get(nome) or "").strip()


def ler_csv_relatorio(caminho: str) -> list[dict]:
    with open(caminho, mode="r", encoding="utf-8-sig") as f:
        sample = f.read(1024)
        delimiter = ";" if sample.count(";") > sample.count(",") else ","

    with open(caminho, mode="r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter=delimiter)
        return [dict(row) for row in reader]


def _dia_da_captura() -> date:
    """Dia da captura (não da carga): o relatório agora traz uma janela de hoje
    até +5 dias, então várias 'Data de carregamento' diferentes aparecem no
    mesmo arquivo - o que agrupa/compara capturas tem que ser o dia em que o
    relatório foi baixado, não a data de alguma carga dentro dele."""
    return datetime.now(SAO_PAULO).date()


async def salvar_captura(
    db: AsyncSession,
    linhas: list[dict],
    origem_captura: str,
    arquivo_nome: Optional[str] = None,
    executado_por_id: Optional[uuid.UUID] = None,
) -> RelatorioCaptura:
    captura = RelatorioCaptura(
        data_referencia=_dia_da_captura(),
        origem_captura=origem_captura,
        status="sucesso",
        total_linhas_csv=len(linhas),
        total_itens_lata=0,
        arquivo_nome=arquivo_nome,
        executado_por_id=executado_por_id,
    )
    db.add(captura)
    await db.flush()

    total_lata = 0
    for row in linhas:
        tipo_material = _col(row, "Tipo de material")
        if tipo_material.lower() not in MATERIAIS_RELATORIO:
            continue

        pedido_insumos = _col(row, "Código de pedido de insumos")
        if not pedido_insumos:
            continue

        item = RelatorioCargaItem(
            relatorio_id=captura.id,
            pedido_insumos=pedido_insumos,
            carga_tms=_col(row, "Carga") or None,
            tipo_material=tipo_material or None,
            origem=_col(row, "Nome original") or None,
            destino=_col(row, "Nome do destino") or None,
            data_carregamento=_col(row, "Data de carregamento") or None,
            status_smartcargas=_col(row, "Status SmartCargas") or None,
            aceita=_col(row, "Aceita") or None,
            confirmado=_col(row, "Confirmado") or None,
            reprogramacao=_col(row, "Reprogramação") or None,
            data_original=_col(row, "Data original") or None,
            dados_raw=row,
        )
        db.add(item)
        total_lata += 1

    captura.total_itens_lata = total_lata
    await db.commit()
    await db.refresh(captura)
    return captura


# O relatório guarda Lata e Arroz (comparativo de aceites), mas só Lata segue pro ERP.
MATERIAIS_RELATORIO = ("lata", "arroz")


def _elegivel_erp(status_smartcargas: Optional[str], tipo_material: Optional[str] = None) -> bool:
    return (
        bool(status_smartcargas) and "confirmad" in status_smartcargas.lower()
        and (tipo_material or "").strip().lower() == "lata"
    )


async def comparar_com_anterior(db: AsyncSession, captura_atual: RelatorioCaptura) -> dict:
    result = await db.execute(
        select(RelatorioCaptura)
        .where(
            RelatorioCaptura.data_referencia == captura_atual.data_referencia,
            RelatorioCaptura.id != captura_atual.id,
            RelatorioCaptura.capturado_em < captura_atual.capturado_em,
        )
        .order_by(RelatorioCaptura.capturado_em.desc())
        .limit(1)
    )
    captura_anterior = result.scalar_one_or_none()

    itens_atuais = (
        (await db.execute(
            select(RelatorioCargaItem).where(RelatorioCargaItem.relatorio_id == captura_atual.id)
        )).scalars().all()
    )

    if not captura_anterior:
        return {
            "relatorio_atual_id": captura_atual.id,
            "relatorio_anterior_id": None,
            "novos": [],
            "sumidos": [],
            "status_alterado": [],
        }

    itens_anteriores = (
        (await db.execute(
            select(RelatorioCargaItem).where(RelatorioCargaItem.relatorio_id == captura_anterior.id)
        )).scalars().all()
    )

    mapa_atual = {i.pedido_insumos: i for i in itens_atuais}
    mapa_anterior = {i.pedido_insumos: i for i in itens_anteriores}

    diffs: list[RelatorioCargaDiff] = []

    for chave, item_atual in mapa_atual.items():
        item_anterior = mapa_anterior.get(chave)
        if item_anterior is None:
            diffs.append(RelatorioCargaDiff(
                relatorio_atual_id=captura_atual.id,
                relatorio_anterior_id=captura_anterior.id,
                pedido_insumos=chave,
                tipo_mudanca="novo",
                status_anterior=None,
                status_atual=item_atual.status_smartcargas,
                origem=item_atual.origem,
                destino=item_atual.destino,
                data_carregamento=item_atual.data_carregamento,
                elegivel_erp=_elegivel_erp(item_atual.status_smartcargas, item_atual.tipo_material),
            ))
        elif (item_anterior.status_smartcargas or "") != (item_atual.status_smartcargas or ""):
            diffs.append(RelatorioCargaDiff(
                relatorio_atual_id=captura_atual.id,
                relatorio_anterior_id=captura_anterior.id,
                pedido_insumos=chave,
                tipo_mudanca="status_alterado",
                status_anterior=item_anterior.status_smartcargas,
                status_atual=item_atual.status_smartcargas,
                origem=item_atual.origem,
                destino=item_atual.destino,
                data_carregamento=item_atual.data_carregamento,
                elegivel_erp=_elegivel_erp(item_atual.status_smartcargas, item_atual.tipo_material),
            ))

    for chave, item_anterior in mapa_anterior.items():
        if chave not in mapa_atual:
            # Sumiu do relatório mais recente. Não é marcado como cancelamento
            # automático: o relatório não traz uma coluna de status explícita
            # para "cancelada", só sinalizamos para revisão manual.
            diffs.append(RelatorioCargaDiff(
                relatorio_atual_id=captura_atual.id,
                relatorio_anterior_id=captura_anterior.id,
                pedido_insumos=chave,
                tipo_mudanca="sumiu",
                status_anterior=item_anterior.status_smartcargas,
                status_atual=None,
                origem=item_anterior.origem,
                destino=item_anterior.destino,
                data_carregamento=item_anterior.data_carregamento,
                elegivel_erp=False,
            ))

    for d in diffs:
        db.add(d)
    await db.commit()

    return {
        "relatorio_atual_id": captura_atual.id,
        "relatorio_anterior_id": captura_anterior.id,
        "novos": [d for d in diffs if d.tipo_mudanca == "novo"],
        "sumidos": [d for d in diffs if d.tipo_mudanca == "sumiu"],
        "status_alterado": [d for d in diffs if d.tipo_mudanca == "status_alterado"],
    }


async def processar_relatorio(
    db: AsyncSession,
    caminho_csv: str,
    origem_captura: str,
    arquivo_nome: Optional[str] = None,
    executado_por_id: Optional[uuid.UUID] = None,
) -> dict:
    try:
        linhas = ler_csv_relatorio(caminho_csv)
        captura = await salvar_captura(
            db, linhas, origem_captura, arquivo_nome=arquivo_nome, executado_por_id=executado_por_id
        )
        comparacao = await comparar_com_anterior(db, captura)
        logger.info(
            "Relatório processado: %s itens Lata, %s novos, %s sumidos, %s status alterado",
            captura.total_itens_lata, len(comparacao["novos"]), len(comparacao["sumidos"]),
            len(comparacao["status_alterado"]),
        )
        return {"captura": captura, "comparacao": comparacao}
    except Exception as e:
        logger.error(f"Falha ao processar relatório de cargas: {e}")
        raise
