"""Aceites vistos no Carga Prioritária x confirmadas no relatório do Portal.

O relatório é a verdade sobre o que foi repassado à CARGO: aqui "confirmada" é a
linha do relatório (Lata e Arroz, a mais recente por pedido) com Status
CargaPrioritaria "confirmad...". As aceitas vêm de carga_aceites (scraper, qualquer
operador). O dia é o de carregamento; o horário é o da detecção (Brasília).
"""
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.carga import Carga
from app.models.carga_aceite import CargaAceite
from app.models.relatorio_carga import RelatorioCaptura, RelatorioCargaItem
from app.services.route_names import normalize_destino, normalize_origem

BR_TZ = ZoneInfo("America/Sao_Paulo")


def _data(s: Optional[str]) -> Optional[date]:
    if not s:
        return None
    s = s.strip()[:10]
    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def _rota_do_item(i: RelatorioCargaItem) -> str:
    """Rota do relatório no mesmo padrão das cargas (códigos -> nomes do cliente)."""
    raw = i.dados_raw or {}
    origem = normalize_origem((raw.get("Código da origem") or "").strip()) or (i.origem or "")
    destino = normalize_destino((raw.get("Código de destino") or "").strip()) or (i.destino or "")
    return f"{origem} → {destino}"


async def calcular_aceites(db: AsyncSession, data_ini: date, data_fim: date) -> dict:
    """Aceitas x confirmadas para cargas com carregamento em [data_ini, data_fim]."""
    eventos = [
        e for e in (await db.execute(select(CargaAceite))).scalars().all()
        if (d := _data(e.data_carregamento)) and data_ini <= d <= data_fim
    ]

    # Última linha de cada pedido nas capturas recentes (a mais nova sobrescreve).
    corte = datetime.combine(data_ini, datetime.min.time(), tzinfo=timezone.utc) - timedelta(days=7)
    linhas = (await db.execute(
        select(RelatorioCargaItem)
        .join(RelatorioCaptura, RelatorioCaptura.id == RelatorioCargaItem.relatorio_id)
        .where(RelatorioCaptura.capturado_em >= corte)
        .order_by(RelatorioCaptura.capturado_em)
    )).scalars().all()
    ultimo = {i.pedido_insumos: i for i in linhas}
    itens = [i for i in ultimo.values() if (d := _data(i.data_carregamento)) and data_ini <= d <= data_fim]
    confirmados = [i for i in itens if i.status_prioritaria and "confirmad" in i.status_prioritaria.lower()]

    # Cargas que "vieram" no Carga Prioritária (uma linha por carga/dia, com quantidade).
    corte_cargas = datetime.combine(data_ini, datetime.min.time(), tzinfo=timezone.utc) - timedelta(days=14)
    vieram_por_rota = defaultdict(int)
    por_rota_dia = defaultdict(lambda: defaultdict(lambda: {"vieram": 0, "aceitas": 0, "confirmadas": 0}))
    for c in (await db.execute(
        select(Carga).where(Carga.fonte == "Carga Prioritária", Carga.data_captura >= corte_cargas)
    )).scalars().all():
        d = _data(c.data_carregamento)
        if d and data_ini <= d <= data_fim:
            rota_c = f"{c.origem} → {c.destino}"
            vieram_por_rota[rota_c] += c.quantidade or 1
            por_rota_dia[rota_c][d.isoformat()]["vieram"] += c.quantidade or 1
    confirmadas_por_rota = defaultdict(int)
    for i in confirmados:
        rota_i = _rota_do_item(i)
        confirmadas_por_rota[rota_i] += 1
        por_rota_dia[rota_i][_data(i.data_carregamento).isoformat()]["confirmadas"] += 1

    dias = defaultdict(lambda: {"aceitas": 0, "confirmadas_relatorio": 0, "valor_aceito": 0.0})
    horas = [{"hora": h, "aceitas": 0, "no_passe_extra": 0} for h in range(24)]
    rotas = defaultdict(lambda: {"aceitas": 0, "valor_aceito": 0.0})
    passes = {"completo": 0, "extra": 0, "historico": 0}
    for e in eventos:
        q = e.quantidade or 1
        v = float(e.valor or 0) * q
        dia = _data(e.data_carregamento).isoformat()
        dias[dia]["aceitas"] += q
        dias[dia]["valor_aceito"] += v
        det = e.detectado_em if e.detectado_em.tzinfo else e.detectado_em.replace(tzinfo=timezone.utc)
        if e.passe != "historico":  # horário dos históricos é aproximado: não entra no gráfico por hora
            h = horas[det.astimezone(BR_TZ).hour]
            h["aceitas"] += q
            if e.passe == "extra":
                h["no_passe_extra"] += q
        passes[e.passe if e.passe in passes else "completo"] += q
        r = rotas[f"{e.origem} → {e.destino}"]
        r["aceitas"] += q
        r["valor_aceito"] += v
        por_rota_dia[f"{e.origem} → {e.destino}"][dia]["aceitas"] += q
    for i in confirmados:
        dias[_data(i.data_carregamento).isoformat()]["confirmadas_relatorio"] += 1

    total_aceitas = sum(d["aceitas"] for d in dias.values())
    total_conf = len(confirmados)
    return {
        "periodo": {"de": data_ini.isoformat(), "ate": data_fim.isoformat(), "criterio": "data de carregamento"},
        "aceitas_detectadas": total_aceitas,
        "confirmadas_no_relatorio": total_conf,
        "taxa_confirmacao_pct": round(100 * total_conf / total_aceitas, 1) if total_aceitas else None,
        "valor_aceito": round(sum(d["valor_aceito"] for d in dias.values()), 2),
        "linhas_no_relatorio": len(itens),
        "detectadas_por_passe": passes,
        "por_dia": [
            {"dia": k, **{kk: (round(vv, 2) if isinstance(vv, float) else vv) for kk, vv in v.items()}}
            for k, v in sorted(dias.items())
        ],
        "por_hora_de_deteccao": [h for h in horas if h["aceitas"]],
        "por_rota": sorted(
            (
                {
                    "rota": k,
                    "vieram": vieram_por_rota.get(k, 0),
                    "aceitas": rotas[k]["aceitas"] if k in rotas else 0,
                    "confirmadas": confirmadas_por_rota.get(k, 0),
                    "valor_aceito": round(rotas[k]["valor_aceito"], 2) if k in rotas else 0.0,
                    "dias": [{"dia": d, **v} for d, v in sorted(por_rota_dia[k].items())],
                }
                for k in set(vieram_por_rota) | set(rotas) | set(confirmadas_por_rota)
            ),
            key=lambda r: (-r["vieram"], -r["aceitas"]),
        )[:40],
        "observacao": "O relatório (Lata e Arroz) é a verdade do que foi repassado à CARGO. Por rota: vieram = cargas vistas no Carga Prioritária, aceitas = detectadas como aceitas, confirmadas = linhas confirmadas no relatório.",
    }


async def calcular_para_dias(db: AsyncSession, dias: int, ref: Optional[datetime] = None) -> dict:
    """Janela de carregamento dos últimos `dias` dias até 5 dias à frente (o relatório cobre hoje..+5)."""
    hoje = (ref or datetime.now(timezone.utc)).astimezone(BR_TZ).date()
    return await calcular_aceites(db, hoje - timedelta(days=dias - 1), hoje + timedelta(days=5))
