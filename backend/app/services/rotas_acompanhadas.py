"""Lista de rotas (origem -> destino) acompanhadas de perto pela CARGO, com o histórico
completo e a recorrência de cada uma, no Smart Cargas e no Pool de Cargas.

A lista vem de app/data/rotas_acompanhadas.csv (formato da planilha oficial
dados_origem_destino.csv, substituível, com a coluna opcional "Código Portal").

Casamento: o destino é por código (a planilha usa "BRxx", o Portal "PBRxx": o "P"
inicial é ignorado). A origem casa por QUALQUER um de: código S4 da planilha, código
Portal, ou nome da cidade dentro do texto de origem da base ("BALL Extrema (MG)").
O código S4 nem sempre é o que o Portal usa (Extrema é 327858 lá), por isso a cidade
e o código Portal existem. Funciona para textos brutos ("[307331] BALL ...") e para
nomes já normalizados por route_names.
"""
import csv
import io
import os
import re
import unicodedata
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.carga import Carga
from app.models.carga_aceite import CargaAceite
from app.services.route_names import DESTINO_MAP, ORIGEM_MAP, _extract_code

BR_TZ = ZoneInfo("America/Sao_Paulo")
DIAS_SEMANA = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]
MARGEM_SAIDA_MIN = 30  # mesma regra do insights_service: sumiu do pool há mais que isso = saiu

CSV_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "rotas_acompanhadas.csv")


def carregar_rotas(caminho: str = CSV_PATH) -> list:
    """Lê a lista de rotas do CSV (colunas da planilha da CARGO: Origem S4, Origem Planta,
    Cidade Origem, UF Origem, Destino S4, Nome Destino, UF Destino; opcional: Código Portal).
    Para trocar a lista, substitua o arquivo; é relido a cada consulta. Devolve tuplas
    (origem S4, planta, cidade/UF origem, destino S4, nome/UF destino, código Portal, cidade)."""
    rotas = []
    with open(caminho, encoding="utf-8-sig", newline="") as f:
        for linha in csv.DictReader(f):
            linha = {(k or "").strip(): (v or "").strip() for k, v in linha.items()}
            if not linha.get("Origem S4") or not linha.get("Destino S4"):
                continue
            rotas.append((
                linha["Origem S4"], linha.get("Origem Planta", ""),
                f"{linha.get('Cidade Origem', '')}/{linha.get('UF Origem', '')}",
                linha["Destino S4"],
                f"{linha.get('Nome Destino', '')}/{linha.get('UF Destino', '')}",
                linha.get("Código Portal", ""),
                linha.get("Cidade Origem", ""),
            ))
    return rotas


def _norm(texto: str) -> str:
    """Minúsculas, sem acento e sem pontuação: 'BALL Três Rios (RJ)' -> 'ball tres rios rj'."""
    t = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode().lower()
    return " " + re.sub(r"[^a-z0-9]+", " ", t).strip() + " "


def _achar_rota(rotas: list, origem: str, destino: str):
    """Rota da lista que casa com a origem/destino de uma carga, ou None."""
    dest = _codigo(destino, DESTINO_MAP)
    cod_orig = _codigo(origem, ORIGEM_MAP)
    txt_orig = _norm(origem)
    for r in rotas:
        if _sem_p(r[3]) != dest:
            continue
        if cod_orig in (_sem_p(r[0]), _sem_p(r[5])):
            return r
        cidade = _norm(r[6]).strip()
        if cidade and f" {cidade} " in txt_orig:
            return r
    return None


def _sem_p(codigo: str) -> str:
    codigo = (codigo or "").upper()
    return codigo[1:] if codigo.startswith("PBR") else codigo


def _codigo(texto: str, mapa: dict) -> str:
    """Código normalizado (sem o 'P' de PBR) de um texto de origem/destino da base."""
    texto = (texto or "").strip()
    for cod, nome in mapa.items():
        if texto == nome:
            return _sem_p(cod)
    return _sem_p(_extract_code(texto))


def _rotulo(r: tuple) -> str:
    return f"{r[0]} {r[2]} ({r[1]}) → {r[3]} {r[4]}"


def _resumo_valores(valores: list) -> dict:
    if not valores:
        return {"valor_min": None, "valor_medio": None, "valor_max": None}
    return {
        "valor_min": round(min(valores), 2),
        "valor_medio": round(sum(valores) / len(valores), 2),
        "valor_max": round(max(valores), 2),
    }


async def calcular_rotas_acompanhadas(
    db: AsyncSession, dias: int, fim: Optional[datetime] = None, insumos: Optional[list] = None
) -> dict:
    """Histórico e recorrência das rotas acima na janela [fim-dias, fim]."""
    agora = datetime.now(timezone.utc)
    ref = fim or agora
    inicio = ref - timedelta(days=dias)

    ROTAS = carregar_rotas()

    q = select(Carga).where(Carga.data_captura >= inicio, Carga.data_captura <= ref)
    if insumos:
        q = q.where(func.lower(func.trim(Carga.tipo_carga)).in_(insumos))
    cargas = (await db.execute(q)).scalars().all()

    q_ac = select(CargaAceite).where(CargaAceite.detectado_em >= inicio, CargaAceite.detectado_em <= ref)
    if insumos:
        q_ac = q_ac.where(func.lower(func.trim(CargaAceite.tipo_carga)).in_(insumos))
    aceites = (await db.execute(q_ac)).scalars().all()

    def novo():
        return {"cargas": 0, "linhas": 0, "valores": [], "dias": set(), "saidas": 0,
                "por_dia_semana": defaultdict(int), "por_mes": defaultdict(lambda: {"cargas": 0, "valores": []}), "primeira": None, "ultima": None}

    acc = {r: {"Pool de Cargas": novo(), "Smart Cargas": novo()} for r in ROTAS}
    aceitas = {r: {"qtd": 0, "valor": 0.0} for r in ROTAS}

    for c in cargas:
        rota = _achar_rota(ROTAS, c.origem, c.destino)
        if rota is None or c.fonte not in acc[rota]:
            continue
        a = acc[rota][c.fonte]
        q_c = c.quantidade or 1
        a["cargas"] += q_c
        a["linhas"] += 1
        if c.valor is not None:
            a["valores"].append(float(c.valor))
        captura = c.data_captura if c.data_captura.tzinfo else c.data_captura.replace(tzinfo=timezone.utc)
        captura_br = captura.astimezone(BR_TZ)
        a["dias"].add(captura_br.date())
        a["por_dia_semana"][DIAS_SEMANA[captura_br.weekday()]] += q_c
        mes = a["por_mes"][captura_br.strftime("%Y-%m")]
        mes["cargas"] += q_c
        if c.valor is not None:
            mes["valores"].append(float(c.valor))
        if a["primeira"] is None or captura_br < a["primeira"]:
            a["primeira"] = captura_br
        if a["ultima"] is None or captura_br > a["ultima"]:
            a["ultima"] = captura_br
        if c.fonte == "Pool de Cargas":
            visto = c.ultima_visualizacao or captura
            visto = visto if visto.tzinfo else visto.replace(tzinfo=timezone.utc)
            if (agora - visto) >= timedelta(minutes=MARGEM_SAIDA_MIN):
                a["saidas"] += 1

    for ac in aceites:
        rota = _achar_rota(ROTAS, ac.origem, ac.destino)
        if rota is None:
            continue
        aceitas[rota]["qtd"] += ac.quantidade or 1
        if ac.valor is not None:
            aceitas[rota]["valor"] += float(ac.valor) * (ac.quantidade or 1)

    def fonte_dict(a: dict, pool: bool) -> dict:
        d = {
            "cargas": a["cargas"],
            "dias_com_carga": len(a["dias"]),
            **_resumo_valores(a["valores"]),
            "primeira_vez": a["primeira"].strftime("%d/%m/%Y") if a["primeira"] else None,
            "ultima_vez": a["ultima"].strftime("%d/%m/%Y") if a["ultima"] else None,
            "por_dia_semana": dict(a["por_dia_semana"]),
            "por_mes": {
                m: {"cargas": v["cargas"],
                    "valor_medio": round(sum(v["valores"]) / len(v["valores"]), 2) if v["valores"] else None}
                for m, v in sorted(a["por_mes"].items())
            },
        }
        if pool:
            d["saidas_do_pool"] = a["saidas"]
        return d

    rotas = []
    total_pool = total_smart = 0
    for r in ROTAS:
        pool = acc[r]["Pool de Cargas"]
        smart = acc[r]["Smart Cargas"]
        total_pool += pool["cargas"]
        total_smart += smart["cargas"]
        rotas.append({
            "rota": _rotulo(r),
            "pool": fonte_dict(pool, True),
            "smart": fonte_dict(smart, False),
            "aceitas": aceitas[r]["qtd"],
            "valor_aceito": round(aceitas[r]["valor"], 2),
        })

    return {
        "janela_dias": dias,
        "total_cargas_pool": total_pool,
        "total_cargas_smart": total_smart,
        "rotas": rotas,
    }


CSV_COLUNAS = [
    "Fonte", "Load ID", "Rota da lista", "Origem (base)", "Destino (base)", "Insumo", "Data carregamento",
    "Data captura", "Última visualização", "Quantidade", "Valor", "Status",
]


async def exportar_csv(db: AsyncSession, dias: int) -> str:
    """Uma linha por carga (Pool e Smart) que casa com as rotas da lista, na janela dos
    últimos `dias`. CSV com ';' e vírgula decimal, para abrir direto no Excel pt-BR."""
    rotas = carregar_rotas()
    inicio = datetime.now(timezone.utc) - timedelta(days=dias)
    cargas = (await db.execute(
        select(Carga).where(Carga.data_captura >= inicio).order_by(Carga.data_captura)
    )).scalars().all()

    def fmt_dt(dt):
        if dt is None:
            return ""
        dt = dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(BR_TZ).strftime("%d/%m/%Y %H:%M")

    saida = io.StringIO()
    w = csv.writer(saida, delimiter=";")
    w.writerow(CSV_COLUNAS)
    for c in cargas:
        rota = _achar_rota(rotas, c.origem, c.destino)
        if rota is None:
            continue
        w.writerow([
            c.fonte, c.load_id or "", _rotulo(rota), c.origem, c.destino, c.tipo_carga or "",
            c.data_carregamento, fmt_dt(c.data_captura), fmt_dt(c.ultima_visualizacao),
            c.quantidade or 1, str(c.valor).replace(".", ",") if c.valor is not None else "", c.status_portal,
        ])
    return "﻿" + saida.getvalue()


async def diagnostico_csv(db: AsyncSession, dias: int) -> str:
    """Cargas que NÃO casaram com nenhuma rota da lista mas têm destino de uma rota da lista:
    candidatas a ter a origem gravada com outro nome/código. Agrupado por origem/destino da base."""
    rotas = carregar_rotas()
    destinos_lista = {_sem_p(r[3]) for r in rotas}
    inicio = datetime.now(timezone.utc) - timedelta(days=dias)
    cargas = (await db.execute(select(Carga).where(Carga.data_captura >= inicio))).scalars().all()

    grupos = {}
    for c in cargas:
        if _achar_rota(rotas, c.origem, c.destino) is not None:
            continue
        dest = _codigo(c.destino, DESTINO_MAP)
        if dest not in destinos_lista:
            continue
        g = grupos.setdefault((c.origem, c.destino, c.fonte), {"cargas": 0, "primeira": None, "ultima": None, "dest": dest})
        g["cargas"] += c.quantidade or 1
        cap = c.data_captura if c.data_captura.tzinfo else c.data_captura.replace(tzinfo=timezone.utc)
        g["primeira"] = cap if g["primeira"] is None or cap < g["primeira"] else g["primeira"]
        g["ultima"] = cap if g["ultima"] is None or cap > g["ultima"] else g["ultima"]

    saida = io.StringIO()
    w = csv.writer(saida, delimiter=";")
    w.writerow(["Origem (base)", "Destino (base)", "Fonte", "Código origem lido", "Código destino lido",
                "Cargas", "Primeira vez", "Última vez", "Rotas da lista com esse destino"])
    for (origem, destino, fonte), g in sorted(grupos.items(), key=lambda kv: (kv[1]["dest"], -kv[1]["cargas"])):
        candidatas = "; ".join(_rotulo(r) for r in rotas if _sem_p(r[3]) == g["dest"])
        w.writerow([origem, destino, fonte, _codigo(origem, ORIGEM_MAP), g["dest"], g["cargas"],
                    g["primeira"].astimezone(BR_TZ).strftime("%d/%m/%Y"),
                    g["ultima"].astimezone(BR_TZ).strftime("%d/%m/%Y"), candidatas])
    return "﻿" + saida.getvalue()


def _num(v) -> str:
    return "" if v is None else f"{v:.2f}".replace(".", ",")


async def resumo_csv(db: AsyncSession, dias: int) -> str:
    """O mesmo resumo que o Assistente IA mostra, em CSV (';' e vírgula decimal), para enviar
    a terceiros: por rota e fonte, uma linha por mês e uma linha TOTAL, mais as aceitas."""
    dados = await calcular_rotas_acompanhadas(db, dias)
    saida = io.StringIO()
    w = csv.writer(saida, delimiter=";")
    w.writerow(["Rota", "Fonte", "Mês", "Cargas", "Valor médio", "Valor mín", "Valor máx",
                "Dias com carga", "Primeira vez", "Última vez", "Saídas do Pool"])
    for r in dados["rotas"]:
        for fonte, chave in (("Pool de Cargas", "pool"), ("Smart Cargas", "smart")):
            f = r[chave]
            if not f["cargas"]:
                w.writerow([r["rota"], fonte, "Sem cargas no período", 0, "", "", "", "", "", "", ""])
                continue
            for mes, m in f["por_mes"].items():
                w.writerow([r["rota"], fonte, mes, m["cargas"], _num(m["valor_medio"]), "", "", "", "", "", ""])
            w.writerow([r["rota"], fonte, "TOTAL", f["cargas"], _num(f["valor_medio"]), _num(f["valor_min"]),
                        _num(f["valor_max"]), f["dias_com_carga"], f["primeira_vez"], f["ultima_vez"],
                        f.get("saidas_do_pool", "")])
        if r["aceitas"]:
            w.writerow([r["rota"], "Aceitas pelo Assistente", "TOTAL", r["aceitas"],
                        _num(r["valor_aceito"] / r["aceitas"]), "", "", "", "", "", ""])
    return "﻿" + saida.getvalue()
