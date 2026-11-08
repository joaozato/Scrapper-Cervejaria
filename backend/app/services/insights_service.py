"""Insights sobre as cargas (permanência no pool, valores, reajustes, reprogramações...).

As métricas são calculadas em Python a partir do banco (exatas e baratas). A
LLM (opcional) só recebe esses agregados e escreve texto — nunca calcula nada e
nunca toma decisão de aceite/confirmação.

Este arquivo é o MESMO na dev e na main: o aceite do Assistente (ScraperAceite) só
existe na dev, então tudo que depende dele é opcional.
"""
import asyncio
import json
import logging
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.carga import Carga
from app.models.carga_valor_historico import CargaValorHistorico
from app.models.insights_uso import InsightsUso
from app.models.relatorio_carga import RelatorioCaptura, RelatorioCargaDiff, RelatorioCargaItem

try:
    from app.models.scraper_aceite import ScraperAceite
except ImportError:  # main: o aceite do Assistente não existe
    ScraperAceite = None

logger = logging.getLogger("cargo.insights")

BR_TZ = ZoneInfo("America/Sao_Paulo")
MODELOS_RESERVA = ["gemini-3.5-flash-lite", "gemini-3.1-flash-lite", "gemini-3-flash-preview"]
# (rótulo, limite superior em minutos) — usado no gráfico de distribuição.
FAIXAS_PERMANENCIA = [
    ("< 10 min", 10), ("10-30 min", 30), ("30-60 min", 60),
    ("1-2 h", 120), ("2-6 h", 360), ("> 6 h", float("inf")),
]
DIAS_SEMANA = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]
# Cargas vistas há menos que isso podem simplesmente ainda estar no pool: só
# entram no cálculo de permanência as que não aparecem há mais que a margem
# (o passe do Pool roda a cada 10 min).
MARGEM_SAIDA_MIN = 30
MIN_AMOSTRA_ROTA = 2
PERIODO_MAX_COMPARAVEL = 400  # "Todo o histórico" não tem período anterior pra comparar
_NEGATIVOS = {"", "não", "nao", "n", "no", "false", "0", "-", "nenhuma", "sem reprogramação", "sem reprogramacao"}


def _aware(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _fmt_min(minutos: float) -> str:
    minutos = int(round(minutos))
    if minutos < 60:
        return f"{minutos} min"
    h, m = divmod(minutos, 60)
    return f"{h}h{m:02d}" if m else f"{h}h"


def _brl(v: float) -> str:
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _pct(novo: float, antigo: float) -> Optional[float]:
    return round(100 * (novo - antigo) / antigo, 1) if antigo else None


def _parse_data(s: Optional[str]):
    if not s:
        return None
    s = s.strip()[:10]
    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


FONTES = {"pool": ["Pool de Cargas"], "smart": ["Carga Prioritária"], "ambos": ["Pool de Cargas", "Carga Prioritária"]}


def normalizar_fonte(fonte) -> str:
    f = (fonte or "pool").strip().lower()
    return f if f in FONTES else "pool"


def normalizar_insumos(texto) -> Optional[list]:
    """'Lata, arroz' (ou lista) -> ['arroz', 'lata']; vazio -> None (todos os insumos)."""
    if not texto:
        return None
    partes = texto.split(",") if isinstance(texto, str) else texto
    out = sorted({p.strip().lower() for p in partes if p and p.strip()})
    return out or None


async def listar_insumos(db: AsyncSession) -> list:
    """Insumos conhecidos (Lata, Arroz, Malte...) vindos do pool, relatórios e aceites."""
    consultas = [
        select(func.lower(func.trim(Carga.tipo_carga))).where(Carga.fonte == "Pool de Cargas").distinct(),
        select(func.lower(func.trim(RelatorioCargaItem.tipo_material))).distinct(),
    ]
    if ScraperAceite is not None:
        consultas.append(select(func.lower(func.trim(ScraperAceite.insumo))).distinct())
    nomes = set()
    for q in consultas:
        nomes.update(n for n in (await db.execute(q)).scalars().all() if n)
    return sorted(nomes)


def _reprogramada(it) -> bool:
    r = (it.reprogramacao or "").strip().lower()
    if r not in _NEGATIVOS:
        return True
    do, dc = _parse_data(it.data_original), _parse_data(it.data_carregamento)
    return bool(do and dc and do != dc)


async def calcular_metricas(db: AsyncSession, dias: int = 7, fim: Optional[datetime] = None, completo: bool = True,
                            insumos: Optional[list] = None, fonte: str = "pool") -> dict:
    """Métricas da janela [fim-dias, fim] (fim = agora por padrão).
    completo=False (usado só pro período anterior, na detecção de anomalias)
    pula o que não entra na comparação (reajustes, reprogramações, aceites).
    insumos (minúsculos) restringe tudo aos insumos escolhidos; None = todos.
    fonte: pool | smart | ambos. O Carga Prioritária é agregado por dia (sem saída), então
    não entra em permanência; conta em volume, horários, valores e rotas."""
    agora = datetime.now(timezone.utc)
    ref = fim or agora
    inicio = ref - timedelta(days=dias)

    # ---- Permanência no Pool / saída / valores ---------------------------
    q_cargas = select(Carga).where(Carga.fonte.in_(FONTES[fonte]), Carga.data_captura >= inicio, Carga.data_captura <= ref)
    if insumos:
        q_cargas = q_cargas.where(func.lower(func.trim(Carga.tipo_carga)).in_(insumos))
    cargas = (await db.execute(q_cargas)).scalars().all()

    por_rota = defaultdict(list)
    valores_rota = defaultdict(list)
    entradas_rota = defaultdict(int)
    valores_todos = []
    valores_smart = []
    por_hora_entrada = defaultdict(int)
    por_dia_entrada = defaultdict(int)
    mapa_calor = [[0] * 24 for _ in range(7)]
    faixas = {nome: 0 for nome, _ in FAIXAS_PERMANENCIA}
    ainda_no_pool = 0
    saidas = 0
    confirmadas = 0
    cargas_smart = 0
    cargas_pool = 0
    for c in cargas:
        captura = _aware(c.data_captura)
        visto = _aware(c.ultima_visualizacao) or captura
        rota = f"{c.origem} → {c.destino}"
        entradas_rota[rota] += c.quantidade or 1
        if captura:
            captura_br = captura.astimezone(BR_TZ)
            q = c.quantidade or 1
            por_dia_entrada[captura_br.strftime('%Y-%m-%d')] += q
            # O Smart é uma linha agregada por dia (hora da captura não é a chegada real):
            # horário e dia da semana só consideram o Pool.
            if c.fonte != "Carga Prioritária":
                por_hora_entrada[captura_br.hour] += q
                mapa_calor[captura_br.weekday()][captura_br.hour] += q
        if c.valor is not None:
            if c.fonte == "Carga Prioritária":
                valores_smart.append(float(c.valor))
            else:
                valores_rota[rota].append(float(c.valor))
                valores_todos.append(float(c.valor))
        if c.status_portal == "Confirmada":
            confirmadas += 1
        if c.fonte == "Carga Prioritária":
            cargas_smart += c.quantidade or 1
            continue
        cargas_pool += 1
        if visto and (agora - visto) < timedelta(minutes=MARGEM_SAIDA_MIN):
            ainda_no_pool += 1
            continue
        saidas += 1
        if captura and visto:
            minutos = max((visto - captura).total_seconds() / 60, 0)
            por_rota[rota].append(minutos)
            for nome, limite in FAIXAS_PERMANENCIA:
                if minutos < limite:
                    faixas[nome] += 1
                    break

    rotas = []
    todos = []
    for rota in set(por_rota) | set(valores_rota) | set(entradas_rota):
        mins = por_rota.get(rota, [])
        vals = valores_rota.get(rota, [])
        todos.extend(mins)
        rotas.append({
            "rota": rota,
            "entradas": entradas_rota.get(rota, 0),
            "cargas": len(mins),
            "media_min": round(statistics.mean(mins), 1) if mins else None,
            "mediana_min": round(statistics.median(mins), 1) if mins else None,
            "max_min": round(max(mins), 1) if mins else None,
            "cargas_com_valor": len(vals),
            "valor_medio": round(statistics.mean(vals), 2) if vals else None,
            "valor_min": round(min(vals), 2) if vals else None,
            "valor_max": round(max(vals), 2) if vals else None,
        })
    rotas_perm = sorted((r for r in rotas if r["media_min"] is not None), key=lambda r: r["media_min"])
    rotas_amostra = [r for r in rotas_perm if r["cargas"] >= MIN_AMOSTRA_ROTA]

    permanencia = {
        "cargas_analisadas": len(todos),
        "media_min": round(statistics.mean(todos), 1) if todos else None,
        "mediana_min": round(statistics.median(todos), 1) if todos else None,
        "mais_rapidas": rotas_amostra[:5],
        "mais_lentas": list(reversed(rotas_amostra[-5:])),
    }

    rotas_valor = [r for r in rotas if r["valor_medio"] is not None and r["cargas_com_valor"] >= MIN_AMOSTRA_ROTA]
    rotas_valor.sort(key=lambda r: r["valor_medio"])
    valor = {
        "cargas_com_valor": len(valores_todos),
        "media": round(statistics.mean(valores_todos), 2) if valores_todos else None,
        "minimo": round(min(valores_todos), 2) if valores_todos else None,
        "maximo": round(max(valores_todos), 2) if valores_todos else None,
        "rotas_mais_caras": [
            {"rota": r["rota"], "valor_medio": r["valor_medio"], "cargas": r["cargas_com_valor"]}
            for r in reversed(rotas_valor[-5:])
        ],
        "rotas_mais_baratas": [
            {"rota": r["rota"], "valor_medio": r["valor_medio"], "cargas": r["cargas_com_valor"]}
            for r in rotas_valor[:5]
        ],
    }

    valor_smart = {
        "cargas_com_valor": len(valores_smart),
        "media": round(statistics.mean(valores_smart), 2) if valores_smart else None,
        "minimo": round(min(valores_smart), 2) if valores_smart else None,
        "maximo": round(max(valores_smart), 2) if valores_smart else None,
    }

    por_dia_semana = [{"dia": DIAS_SEMANA[i], "cargas": sum(mapa_calor[i])} for i in range(7)]

    # Os relatórios do Portal só importam Lata e Arroz: com outro insumo escolhido não há dado a mostrar.
    relatorios_aplicam = not insumos or bool({"lata", "arroz"} & set(insumos))

    # ---- Relatórios (diferenças entre capturas) --------------------------
    capturas = (await db.execute(
        select(RelatorioCaptura).where(RelatorioCaptura.capturado_em >= inicio, RelatorioCaptura.capturado_em <= ref)
    )).scalars().all() if relatorios_aplicam else []
    ids = [c.id for c in capturas]
    diffs = []
    if ids:
        q_diffs = select(RelatorioCargaDiff).where(RelatorioCargaDiff.relatorio_atual_id.in_(ids))
        if insumos:
            q_diffs = q_diffs.where(RelatorioCargaDiff.pedido_insumos.in_(
                select(RelatorioCargaItem.pedido_insumos).where(func.lower(func.trim(RelatorioCargaItem.tipo_material)).in_(insumos))
            ))
        diffs = (await db.execute(q_diffs)).scalars().all()
    sumidos_rota = defaultdict(int)
    contagem = defaultdict(int)
    for d in diffs:
        contagem[d.tipo_mudanca] += 1
        if d.tipo_mudanca == "sumiu":
            sumidos_rota[f"{d.origem} → {d.destino}"] += 1
    relatorios = {
        "aplicavel": relatorios_aplicam,
        "capturas": len(capturas),
        "novos": contagem["novo"],
        "sumidos": contagem["sumiu"],
        "status_alterado": contagem["status_alterado"],
        "rotas_com_mais_sumidos": sorted(
            ({"rota": k, "sumidos": v} for k, v in sumidos_rota.items()), key=lambda r: -r["sumidos"]
        )[:5],
    }

    horas = sorted(por_hora_entrada.items(), key=lambda kv: -kv[1])[:3]
    detalhe = {
        "entradas_por_hora": [{"hora": h, "cargas": por_hora_entrada.get(h, 0)} for h in range(24)],
        "entradas_por_dia": [{"dia": d, "cargas": n} for d, n in sorted(por_dia_entrada.items())],
        "faixas_permanencia": [{"faixa": nome, "cargas": faixas[nome]} for nome, _ in FAIXAS_PERMANENCIA],
        "mapa_calor": mapa_calor,
        "rotas": sorted(rotas, key=lambda r: -(r["entradas"] + r["cargas"] + r["cargas_com_valor"]))[:100],
    }

    resultado = {
        "detalhe": detalhe,
        "periodo_dias": dias,
        "insumos": insumos,
        "fonte": fonte,
        "gerado_em": agora.isoformat(),
        "pool": {
            "cargas_vistas": cargas_pool,
            "cargas_smart": cargas_smart,
            "saidas": saidas,
            "ainda_no_pool": ainda_no_pool,
            "confirmadas": confirmadas,
            "horas_de_pico_entrada": [{"hora": h, "cargas": n} for h, n in horas],
            "por_dia_semana": por_dia_semana,
            "permanencia": permanencia,
        },
        "valor": valor,
        "valor_smart": valor_smart,
        "relatorios": relatorios,
    }

    if not completo:
        return resultado

    resultado["reprogramacoes"], detalhe["reprogramadas"] = await _calcular_reprogramacoes(db, inicio, ref, insumos)
    resultado["reajustes"], detalhe["reajustes"] = await _calcular_reajustes(db, inicio, ref, insumos)
    if fonte != "pool":  # aceites só existem no Carga Prioritária
        from app.services import aceites_service
        resultado["aceites"] = await aceites_service.calcular_para_dias(db, dias, ref)

    # ---- Aceites do Assistente (só existe na dev) ---------------------------
    if ScraperAceite is not None:
        aceites = (await db.execute(
            select(ScraperAceite).where(
                ScraperAceite.data_aceite >= inicio, ScraperAceite.data_aceite <= ref,
                *([func.lower(func.trim(ScraperAceite.insumo)).in_(insumos)] if insumos else []),
            )
        )).scalars().all()
        ac_rota = defaultdict(lambda: {"aceitas": 0, "confirmadas": 0, "nao_confirmadas": 0})
        for a in aceites:
            r = ac_rota[f"{a.origem} → {a.destino}"]
            r["aceitas"] += 1
            if a.confirmado_em:
                r["confirmadas"] += 1
            if a.nao_confirmada_em:
                r["nao_confirmadas"] += 1
        resultado["assistente"] = {
            "aceitas": len(aceites),
            "confirmadas": sum(1 for a in aceites if a.confirmado_em),
            "nao_confirmadas": sum(1 for a in aceites if a.nao_confirmada_em),
            "por_rota": sorted(
                ({"rota": k, **v} for k, v in ac_rota.items()), key=lambda r: -r["aceitas"]
            )[:8],
        }
    return resultado


async def _calcular_reprogramacoes(db: AsyncSession, inicio: datetime, ref: datetime, insumos: Optional[list] = None):
    """Reprogramações vistas nos relatórios capturados no período (1 linha por
    pedido, a mais recente)."""
    q_itens = (
        select(RelatorioCargaItem, RelatorioCaptura.capturado_em)
        .join(RelatorioCaptura, RelatorioCaptura.id == RelatorioCargaItem.relatorio_id)
        .where(RelatorioCaptura.capturado_em >= inicio, RelatorioCaptura.capturado_em <= ref)
        .order_by(RelatorioCaptura.capturado_em)
    )
    if insumos:
        q_itens = q_itens.where(func.lower(func.trim(RelatorioCargaItem.tipo_material)).in_(insumos))
    linhas = (await db.execute(q_itens)).all()
    ultimo = {}
    for item, capturado_em in linhas:
        ultimo[item.pedido_insumos] = item  # mais recente sobrescreve
    itens = list(ultimo.values())
    reprog = [i for i in itens if _reprogramada(i)]

    atrasos = []
    por_rota = defaultdict(list)
    tipos = Counter()
    lista = []
    for i in reprog:
        do, dc = _parse_data(i.data_original), _parse_data(i.data_carregamento)
        atraso = (dc - do).days if (do and dc) else None
        if atraso is not None:
            atrasos.append(atraso)
        por_rota[f"{i.origem} → {i.destino}"].append(atraso)
        if (i.reprogramacao or "").strip():
            tipos[i.reprogramacao.strip()] += 1
        lista.append({
            "pedido": i.pedido_insumos, "rota": f"{i.origem} → {i.destino}",
            "reprogramacao": i.reprogramacao, "data_original": i.data_original,
            "data_carregamento": i.data_carregamento, "atraso_dias": atraso,
        })
    agregado = {
        "itens_analisados": len(itens),
        "reprogramados": len(reprog),
        "percentual": round(100 * len(reprog) / len(itens), 1) if itens else None,
        "atraso_medio_dias": round(statistics.mean(atrasos), 1) if atrasos else None,
        "valores_do_campo": [{"valor": k, "itens": v} for k, v in tipos.most_common(5)],
        "por_rota": sorted(
            ({"rota": k, "reprogramadas": len(v),
              "atraso_medio_dias": round(statistics.mean([a for a in v if a is not None]), 1)
              if any(a is not None for a in v) else None}
             for k, v in por_rota.items()),
            key=lambda r: -r["reprogramadas"],
        )[:8],
    }
    return agregado, lista[:200]


async def _calcular_reajustes(db: AsyncSession, inicio: datetime, ref: datetime, insumos: Optional[list] = None):
    """Evolução do valor das cargas a partir de carga_valor_historico."""
    primeiro = (await db.execute(select(func.min(CargaValorHistorico.registrado_em)))).scalar()
    q_hist = (
        select(CargaValorHistorico)
        .where(CargaValorHistorico.registrado_em >= inicio, CargaValorHistorico.registrado_em <= ref)
        .order_by(CargaValorHistorico.registrado_em)
    )
    if insumos:
        # O histórico não guarda o insumo: filtra pelas cargas do insumo (mesmo load_id).
        q_hist = q_hist.where(CargaValorHistorico.load_id.in_(
            select(Carga.load_id).where(Carga.fonte == "Pool de Cargas", func.lower(func.trim(Carga.tipo_carga)).in_(insumos))
        ))
    linhas = (await db.execute(q_hist)).scalars().all()
    por_carga = defaultdict(list)
    for h in linhas:
        por_carga[(h.load_id, h.fonte)].append(h)

    mudancas = []
    for (load_id, _), hs in por_carga.items():
        if len(hs) < 2:
            continue
        de, para = float(hs[0].valor), float(hs[-1].valor)
        mudancas.append({
            "load_id": load_id,
            "rota": f"{hs[-1].origem} → {hs[-1].destino}",
            "de": de, "para": para, "delta": round(para - de, 2), "pct": _pct(para, de),
            "reajustes": len(hs) - 1,
            "horas_ate_ultimo": round((_aware(hs[-1].registrado_em) - _aware(hs[0].registrado_em)).total_seconds() / 3600, 1),
            "quando": _aware(hs[-1].registrado_em).isoformat(),
        })
    por_rota = defaultdict(list)
    for m in mudancas:
        por_rota[m["rota"]].append(m)
    pcts = [m["pct"] for m in mudancas if m["pct"] is not None]
    agregado = {
        "historico_desde": _aware(primeiro).isoformat() if primeiro else None,
        "cargas_acompanhadas": len(por_carga),
        "cargas_com_reajuste": len(mudancas),
        "subiram": sum(1 for m in mudancas if m["delta"] > 0),
        "desceram": sum(1 for m in mudancas if m["delta"] < 0),
        "variacao_media_pct": round(statistics.mean(pcts), 1) if pcts else None,
        "variacao_media_rs": round(statistics.mean([m["delta"] for m in mudancas]), 2) if mudancas else None,
        "horas_medias_ate_ultimo_reajuste": round(statistics.mean([m["horas_ate_ultimo"] for m in mudancas]), 1) if mudancas else None,
        "por_rota": sorted(
            ({"rota": k, "cargas": len(v),
              "variacao_media_rs": round(statistics.mean([m["delta"] for m in v]), 2),
              "variacao_media_pct": round(statistics.mean([m["pct"] for m in v if m["pct"] is not None]), 1)
              if any(m["pct"] is not None for m in v) else None}
             for k, v in por_rota.items()),
            key=lambda r: -abs(r["variacao_media_rs"]),
        )[:8],
    }
    return agregado, sorted(mudancas, key=lambda m: m["quando"], reverse=True)[:100]


async def calcular_com_anomalias(db: AsyncSession, dias: int = 7, insumos: Optional[list] = None, fonte: str = "pool") -> dict:
    """Métricas do período + alertas de anomalia comparando com o período anterior
    de mesmo tamanho (não existe pro 'Todo o histórico')."""
    atual = await calcular_metricas(db, dias, insumos=insumos, fonte=fonte)
    if dias > PERIODO_MAX_COMPARAVEL:
        atual["anomalias"] = []
        atual["comparativo"] = None
        return atual
    anterior = await calcular_metricas(db, dias, fim=datetime.now(timezone.utc) - timedelta(days=dias), completo=False, insumos=insumos, fonte=fonte)
    atual["anomalias"] = detectar_anomalias(atual, anterior)
    atual["comparativo"] = {
        "cargas_vistas_anterior": anterior["pool"]["cargas_vistas"],
        "media_min_anterior": anterior["pool"]["permanencia"]["media_min"],
        "valor_medio_anterior": anterior["valor"]["media"],
        "sumidos_anterior": anterior["relatorios"]["sumidos"],
    }
    return atual


def detectar_anomalias(atual: dict, anterior: dict) -> list:
    """Regras determinísticas (a LLM só comenta). Compara com o período anterior."""
    out = []
    pa, pb = atual["pool"], anterior["pool"]

    # Volume de cargas entrando no pool
    va, vb = pa["cargas_vistas"], pb["cargas_vistas"]
    if vb >= 5 and va >= 0:
        var = _pct(va, vb)
        if var is not None and abs(var) >= 30:
            out.append({
                "tipo": "alerta" if var < 0 else "destaque",
                "titulo": "Volume de cargas mudou",
                "texto": f"{va} cargas vistas contra {vb} no período anterior ({var:+.0f}%).",
                "peso": abs(var),
            })

    # Tempo médio no pool
    ma, mb = pa["permanencia"]["media_min"], pb["permanencia"]["media_min"]
    if ma and mb and abs(ma - mb) >= 10:
        var = _pct(ma, mb)
        if var is not None and abs(var) >= 50:
            out.append({
                "tipo": "alerta" if var > 0 else "destaque",
                "titulo": "Tempo no pool mudou",
                "texto": f"Média de {_fmt_min(ma)} contra {_fmt_min(mb)} no período anterior ({var:+.0f}%).",
                "peso": abs(var),
            })

    # Rotas individuais (tempo e valor)
    ant = {r["rota"]: r for r in anterior["detalhe"]["rotas"]}
    for r in atual["detalhe"]["rotas"]:
        b = ant.get(r["rota"])
        if not b:
            continue
        if r["cargas"] >= MIN_AMOSTRA_ROTA and b["cargas"] >= MIN_AMOSTRA_ROTA and r["media_min"] and b["media_min"]:
            if abs(r["media_min"] - b["media_min"]) >= 20 and (
                r["media_min"] >= 2 * b["media_min"] or r["media_min"] <= 0.5 * b["media_min"]
            ):
                lento = r["media_min"] > b["media_min"]
                out.append({
                    "tipo": "alerta" if lento else "destaque",
                    "titulo": "Rota ficou mais lenta" if lento else "Rota ficou mais rápida",
                    "texto": f"{r['rota']}: {_fmt_min(r['media_min'])} contra {_fmt_min(b['media_min'])} no período anterior.",
                    "peso": abs(_pct(r["media_min"], b["media_min"]) or 0),
                })
        if (r["cargas_com_valor"] >= MIN_AMOSTRA_ROTA and b["cargas_com_valor"] >= MIN_AMOSTRA_ROTA
                and r["valor_medio"] and b["valor_medio"]):
            var = _pct(r["valor_medio"], b["valor_medio"])
            if var is not None and abs(var) >= 10:
                out.append({
                    "tipo": "info",
                    "titulo": "Valor médio da rota mudou",
                    "texto": f"{r['rota']}: {_brl(r['valor_medio'])} contra {_brl(b['valor_medio'])} ({var:+.0f}%).",
                    "peso": abs(var) / 2,
                })

    # Cargas sumindo dos relatórios
    sa, sb = atual["relatorios"]["sumidos"], anterior["relatorios"]["sumidos"]
    if sa >= 3 and sa >= 2 * max(sb, 1):
        out.append({
            "tipo": "alerta",
            "titulo": "Mais cargas sumindo dos relatórios",
            "texto": f"{sa} sumiços contra {sb} no período anterior.",
            "peso": 40,
        })

    out.sort(key=lambda a: -a["peso"])
    for a in out:
        a.pop("peso", None)
    return out[:8]


def tem_dados(m: dict) -> bool:
    cargo = m.get("assistente", {}).get("aceitas", 0)
    return bool(m["pool"]["cargas_vistas"] or m["pool"].get("cargas_smart") or cargo or m["relatorios"]["capturas"]
                or m.get("reprogramacoes", {}).get("itens_analisados"))


def montar_destaques(m: dict) -> list:
    """Destaques determinísticos (valem mesmo sem LLM configurada)."""
    out = []
    pool = m["pool"]
    perm = pool["permanencia"]
    if perm["cargas_analisadas"]:
        out.append({
            "tipo": "info",
            "titulo": "Tempo médio no pool",
            "texto": f"{_fmt_min(perm['media_min'])} em média (mediana {_fmt_min(perm['mediana_min'])}) "
                     f"em {perm['cargas_analisadas']} cargas que já saíram nos últimos {m['periodo_dias']} dias.",
        })
    if perm["mais_rapidas"]:
        r = perm["mais_rapidas"][0]
        out.append({
            "tipo": "destaque",
            "titulo": "Rota que sai mais rápido",
            "texto": f"{r['rota']}: {_fmt_min(r['media_min'])} em média ({r['cargas']} cargas).",
        })
    if perm["mais_lentas"]:
        r = perm["mais_lentas"][0]
        out.append({
            "tipo": "alerta",
            "titulo": "Rota que mais fica parada",
            "texto": f"{r['rota']}: {_fmt_min(r['media_min'])} em média, pico de {_fmt_min(r['max_min'])} ({r['cargas']} cargas).",
        })
    if pool["horas_de_pico_entrada"]:
        hs = ", ".join(f"{h['hora']:02d}h ({h['cargas']})" for h in pool["horas_de_pico_entrada"])
        out.append({"tipo": "info", "titulo": "Horários em que mais cargas entram", "texto": hs})
    dias_sem = [d for d in pool["por_dia_semana"] if d["cargas"]]
    if dias_sem:
        top = max(dias_sem, key=lambda d: d["cargas"])
        baixo = min(dias_sem, key=lambda d: d["cargas"])
        out.append({
            "tipo": "info",
            "titulo": "Dia da semana",
            "texto": f"{top['dia']} é o dia com mais cargas entrando ({top['cargas']}); "
                     f"{baixo['dia']} é o com menos ({baixo['cargas']}).",
        })

    vs = m.get("valor_smart") or {}
    if vs.get("cargas_com_valor"):
        out.append({
            "tipo": "info",
            "titulo": "Valor das cargas do Carga Prioritária",
            "texto": f"Média de {_brl(vs['media'])} (de {_brl(vs['minimo'])} a {_brl(vs['maximo'])}) em {vs['cargas_com_valor']} registros com valor (separado do Pool).",
        })
    v = m["valor"]
    if v["cargas_com_valor"]:
        out.append({
            "tipo": "info",
            "titulo": "Valor das cargas",
            "texto": f"Média de {_brl(v['media'])} (de {_brl(v['minimo'])} a {_brl(v['maximo'])}) em {v['cargas_com_valor']} cargas com valor.",
        })
    if v["rotas_mais_caras"]:
        r = v["rotas_mais_caras"][0]
        out.append({"tipo": "destaque", "titulo": "Rota que mais paga",
                    "texto": f"{r['rota']}: {_brl(r['valor_medio'])} em média ({r['cargas']} cargas)."})
    if v["rotas_mais_baratas"]:
        r = v["rotas_mais_baratas"][0]
        out.append({"tipo": "info", "titulo": "Rota que menos paga",
                    "texto": f"{r['rota']}: {_brl(r['valor_medio'])} em média ({r['cargas']} cargas)."})

    rj = m.get("reajustes")
    if rj:
        if rj["cargas_com_reajuste"]:
            out.append({
                "tipo": "alerta" if rj["desceram"] > rj["subiram"] else "info",
                "titulo": "Reajustes de valor",
                "texto": f"{rj['cargas_com_reajuste']} de {rj['cargas_acompanhadas']} cargas mudaram de valor "
                         f"({rj['subiram']} subiram, {rj['desceram']} desceram); variação média de {rj['variacao_media_pct']}% "
                         f"({_brl(rj['variacao_media_rs'])}).",
            })
        else:
            desde = rj["historico_desde"]
            out.append({
                "tipo": "info",
                "titulo": "Reajustes de valor",
                "texto": ("Nenhuma carga mudou de valor no período. " if rj["cargas_acompanhadas"] else "")
                         + (f"O histórico de valores começou a ser gravado em {datetime.fromisoformat(desde).astimezone(BR_TZ):%d/%m/%Y}."
                            if desde else "O histórico de valores ainda não começou a ser gravado (aguarda os próximos passes do scraper)."),
            })

    rp = m.get("reprogramacoes")
    if rp and rp["itens_analisados"]:
        extra = f"; atraso médio de {rp['atraso_medio_dias']} dia(s)" if rp["atraso_medio_dias"] is not None else ""
        out.append({
            "tipo": "alerta" if (rp["percentual"] or 0) >= 20 else "info",
            "titulo": "Reprogramações",
            "texto": f"{rp['reprogramados']} de {rp['itens_analisados']} cargas dos relatórios foram reprogramadas ({rp['percentual']}%){extra}.",
        })

    g = m.get("assistente")
    if g and g["aceitas"]:
        taxa = round(100 * g["confirmadas"] / g["aceitas"])
        out.append({
            "tipo": "alerta" if taxa < 70 else "info",
            "titulo": "Assistente: aceitas x confirmadas",
            "texto": f"{g['confirmadas']} de {g['aceitas']} confirmadas ({taxa}%); {g['nao_confirmadas']} marcadas como não confirmadas.",
        })
    rel = m["relatorios"]
    if not rel.get("aplicavel", True):
        out.append({
            "tipo": "info",
            "titulo": "Relatórios do Portal",
            "texto": "Os relatórios só trazem cargas de Lata e Arroz; para este insumo não há dados de relatório (novas, sumidas, reprogramações).",
        })
    elif rel["capturas"]:
        out.append({
            "tipo": "info",
            "titulo": "Relatórios capturados",
            "texto": f"{rel['capturas']} capturas: {rel['novos']} cargas novas, {rel['sumidos']} sumiram, {rel['status_alterado']} mudaram de status.",
        })
    if rel["rotas_com_mais_sumidos"]:
        r = rel["rotas_com_mais_sumidos"][0]
        out.append({
            "tipo": "alerta",
            "titulo": "Rota com mais cargas sumindo do relatório",
            "texto": f"{r['rota']}: {r['sumidos']} sumiços.",
        })
    if not out:
        out.append({"tipo": "info", "titulo": "Sem dados", "texto": "Ainda não há dados suficientes no período."})
    return out


# ---------------------------------------------------------------------------
# Uso da API e chamadas à LLM
# ---------------------------------------------------------------------------

def _compactar(obj, limite=90):
    """Encurta os nomes de rota (endereços longos) pra economizar tokens."""
    if isinstance(obj, dict):
        return {k: (v[:limite] if k == "rota" and isinstance(v, str) else _compactar(v, limite)) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_compactar(i, limite) for i in obj]
    return obj


async def uso_total(db: AsyncSession) -> dict:
    r = (await db.execute(select(
        func.count(), func.coalesce(func.sum(InsightsUso.tokens_entrada), 0),
        func.coalesce(func.sum(InsightsUso.tokens_saida), 0),
        func.coalesce(func.sum(InsightsUso.tokens_total), 0), func.max(InsightsUso.criado_em),
    ))).one()

    agora_br = datetime.now(BR_TZ)
    inicio_mes = agora_br.replace(day=1, hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc)
    mes = (await db.execute(select(
        func.count(), func.coalesce(func.sum(InsightsUso.tokens_total), 0)
    ).where(InsightsUso.criado_em >= inicio_mes))).one()
    limite = settings.INSIGHTS_TOKENS_LIMITE_MES
    usado_mes = int(mes[1])
    return {
        "chamadas": r[0], "tokens_entrada": int(r[1]), "tokens_saida": int(r[2]),
        "tokens_total": int(r[3]), "ultima_chamada": r[4].isoformat() if r[4] else None,
        "mes": {
            "chamadas": mes[0],
            "tokens": usado_mes,
            "limite": limite,
            "percentual": round(100 * usado_mes / limite, 1) if limite else None,
        },
    }


def _contexto_enxuto(metricas: dict) -> dict:
    """O que vai pra LLM na análise geral: só agregados (sem o bloco 'detalhe')."""
    return {k: v for k, v in metricas.items() if k != "detalhe"}


def _contexto_pergunta(metricas: dict) -> dict:
    """Pra perguntas livres, inclui também a tabela de rotas (top 40) e o mapa
    por dia da semana, pra a IA conseguir responder perguntas específicas."""
    det = metricas.get("detalhe", {})
    # "entradas" = volume de cargas da rota no período (recorrência); "cargas" = só as que já saíram do pool.
    rotas = [
        {k: r[k] for k in ("rota", "entradas", "cargas", "media_min", "valor_medio", "cargas_com_valor")}
        for r in sorted(det.get("rotas", []), key=lambda r: -r["entradas"])[:40]
    ]
    ctx = _contexto_enxuto(metricas)
    ctx["rotas_detalhe"] = rotas
    ctx["faixas_permanencia"] = det.get("faixas_permanencia")
    return ctx


async def _chamar_gemini(prompt: str, db: AsyncSession, periodo_dias: Optional[int], max_tokens: int = 4096,
                         json_mode: bool = False) -> Optional[str]:
    """Chama o Gemini (com modelos de reserva em caso de 429/503/404) e grava o
    uso de tokens. None se não houver chave ou todos os modelos falharem."""
    if not settings.GEMINI_API_KEY:
        return None
    config = {"maxOutputTokens": max_tokens, "temperature": 0.0 if json_mode else 0.3}
    if json_mode:
        config["responseMimeType"] = "application/json"
    corpo = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": config,
    }
    headers = {"x-goog-api-key": settings.GEMINI_API_KEY, "content-type": "application/json"}
    modelos = [settings.INSIGHTS_LLM_MODEL] + [m for m in MODELOS_RESERVA if m != settings.INSIGHTS_LLM_MODEL]
    ultimo_erro = None
    for modelo, _ in ((m, t) for m in modelos for t in range(2)):
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent"
        try:
            async with httpx.AsyncClient(timeout=120) as client:
                resp = await client.post(url, headers=headers, json=corpo)
            if resp.status_code in (429, 503, 404):
                ultimo_erro = f"{modelo}: HTTP {resp.status_code}"
                if resp.status_code != 404:
                    await asyncio.sleep(2)
                continue
            resp.raise_for_status()
            j = resp.json()
            cand = j["candidates"][0]
            texto = "".join(p.get("text", "") for p in cand.get("content", {}).get("parts", [])).strip()
            u = j.get("usageMetadata", {})
            try:
                db.add(InsightsUso(
                    modelo=modelo,
                    periodo_dias=periodo_dias,
                    tokens_entrada=u.get("promptTokenCount", 0),
                    tokens_saida=u.get("candidatesTokenCount", 0) + u.get("thoughtsTokenCount", 0),
                    tokens_total=u.get("totalTokenCount", 0),
                ))
                await db.commit()
            except Exception as e:
                # Falha ao registrar o uso nunca pode derrubar a resposta.
                await db.rollback()
                logger.error(f"Não consegui registrar o uso de tokens: {e}")
            if not texto:
                logger.error(f"Gemini respondeu sem texto (finishReason={cand.get('finishReason')}, usage={u})")
            return texto or None
        except Exception as e:
            logger.error(f"Falha ao chamar a LLM ({type(e).__name__}): {e}")
            return None
    logger.error(f"Gemini indisponível em todos os modelos ({ultimo_erro})")
    return None


_REGRAS_PROMPT = (
    "Use SOMENTE os números fornecidos, não invente dados e não sugira aceitar/confirmar "
    "cargas automaticamente. Tempos estão em minutos, valores em reais."
)


def _escopo_insumos(metricas: dict) -> str:
    ins = metricas.get("insumos")
    txt = f" Os dados foram filtrados apenas para o(s) insumo(s): {', '.join(ins)}." if ins else ""
    fonte = metricas.get("fonte", "pool")
    if fonte != "pool":
        txt += f" Fonte das cargas: {fonte} (Carga Prioritária é contagem diária, sem tempo de permanência)."
    return txt


def _sobre_assistente(metricas: dict) -> str:
    return " e o desempenho do Assistente" if "assistente" in metricas else ""


async def gerar_narrativa(metricas: dict, db: AsyncSession) -> Optional[str]:
    """Análise geral em tópicos curtos. None se a LLM não estiver disponível."""
    prompt = (
        "Você analisa a operação de captação de cargas de lata/arroz de uma transportadora no Portal. "
        "Abaixo estão métricas já calculadas (JSON). Escreva em português, em até 7 tópicos curtos, "
        "os insights mais úteis para o operador: padrões de permanência no pool, valores/rotas que "
        f"merecem atenção, reajustes, reprogramações{_sobre_assistente(metricas)}. Comente os alertas de anomalia "
        f"(campo 'anomalias') primeiro, se houver.{_escopo_insumos(metricas)} {_REGRAS_PROMPT}\n\n"
        + json.dumps(_compactar(_contexto_enxuto(metricas)), ensure_ascii=False)
    )
    return await _chamar_gemini(prompt, db, metricas.get("periodo_dias"))


async def responder_pergunta(metricas: dict, pergunta: str, db: AsyncSession) -> Optional[str]:
    prompt = (
        "Você é um analista da operação de captação de cargas de lata/arroz de uma transportadora no Portal. "
        "Responda à pergunta do operador em português, de forma direta (até 8 linhas), usando APENAS os dados "
        "em JSON abaixo. Se os dados não bastarem para responder, diga claramente o que falta em vez de supor. "
        f"{_escopo_insumos(metricas).strip()} {_REGRAS_PROMPT}\n\nPERGUNTA: {pergunta}\n\nDADOS (período de {metricas.get('periodo_dias')} dias):\n"
        + json.dumps(_compactar(_contexto_pergunta(metricas), 70), ensure_ascii=False)
    )
    return await _chamar_gemini(prompt, db, metricas.get("periodo_dias"), max_tokens=2048)


def resumo_deterministico(metricas: dict) -> str:
    """Resumo pronto pra enviar, sem LLM (fallback e opção sem custo)."""
    pool = metricas["pool"]
    perm = pool["permanencia"]
    ins = metricas.get("insumos")
    sufixo = f" — {', '.join(i.upper() for i in ins)}" if ins else ""
    linhas = [f"*Resumo de cargas — {metricas['periodo_dias']} dia(s){sufixo}*"]
    linhas.append(f"• {pool['cargas_vistas']} cargas vistas no pool, {pool['saidas']} já saíram")
    if perm["media_min"]:
        linhas.append(f"• Tempo médio no pool: {_fmt_min(perm['media_min'])}")
    v = metricas["valor"]
    if v["media"]:
        linhas.append(f"• Valor médio: {_brl(v['media'])}")
    for a in (metricas.get("anomalias") or [])[:3]:
        linhas.append(f"⚠ {a['titulo']}: {a['texto']}")
    rp = metricas.get("reprogramacoes")
    if rp and rp["itens_analisados"]:
        linhas.append(f"• Reprogramadas: {rp['reprogramados']} de {rp['itens_analisados']} ({rp['percentual']}%)")
    return "\n".join(linhas)


async def gerar_resumo_envio(metricas: dict, db: AsyncSession) -> dict:
    """Texto curto no estilo WhatsApp. Usa a LLM e cai no resumo determinístico
    se ela não estiver disponível."""
    prompt = (
        "Escreva um resumo CURTO (no máximo 8 linhas) em português para enviar por WhatsApp ao gestor, "
        "com os pontos mais importantes da operação de cargas no período: anomalias primeiro (campo 'anomalias'), "
        "depois volume, tempo no pool, valores e reprogramações. Use *negrito* do WhatsApp nos títulos, "
        f"sem tabelas e sem markdown de cabeçalho.{_escopo_insumos(metricas)} {_REGRAS_PROMPT}\n\n"
        + json.dumps(_compactar(_contexto_enxuto(metricas)), ensure_ascii=False)
    )
    texto = await _chamar_gemini(prompt, db, metricas.get("periodo_dias"), max_tokens=1024)
    if texto:
        return {"texto": texto, "origem": "ia"}
    return {"texto": resumo_deterministico(metricas), "origem": "modelo"}
