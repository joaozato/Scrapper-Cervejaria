"""Cruza os aceites do round anterior (carga_aceites, janela :30-:59) com o que o
scraper de ranking leu no início da hora seguinte (carga_rankings).

Por round (hora lida), cada aceite vira:
  - "ranking": apareceu no 1º/2º/3º lugar (com a posição);
  - "fora": não apareceu em nenhum dos 3 rankings.
E cada carga que está no ranking mas não bate com nenhum aceite nosso do round
vira "sem_aceite_nosso" (não foi pega por nós, segundo os aceites detectados).

Só entram rounds com leitura registrada (carga_ranking_leituras), inclusive as
de rankings vazios: aceite sem ranking nenhum é "fora". Round sem leitura (tela
não carregou, scraper não rodou) não entra, para não acusar "fora" sem prova.
"""
import unicodedata
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.carga_aceite import CargaAceite
from app.models.carga_ranking import CargaRanking, CargaRankingLeitura

BR_TZ = ZoneInfo("America/Sao_Paulo")
JANELA_ACEITE = timedelta(minutes=30)  # passes das :40 e :55 do round que fechou


def _chave_rota(origem: str | None, destino: str | None) -> tuple[str, str]:
    """Origem/destino sem endereço (só o trecho antes do ' - '), sem acento e em minúsculas.
    O ranking mostra o nome curto e o aceite o endereço completo; sem load_id é o que sobra para casar."""
    def norm(t: str | None) -> str:
        base = (t or "").split(" - ")[0]
        base = unicodedata.normalize("NFKD", base).encode("ascii", "ignore").decode()
        return " ".join(base.lower().split())
    return norm(origem), norm(destino)


async def calcular_ranking(db: AsyncSession, dias: int) -> dict:
    desde = datetime.now(timezone.utc) - timedelta(days=dias)
    leituras = (await db.execute(
        select(CargaRanking).where(CargaRanking.round_hora >= desde).order_by(CargaRanking.round_hora.desc())
    )).scalars().all()

    por_round: dict[datetime, list[CargaRanking]] = defaultdict(list)
    rounds_lidos = (await db.execute(
        select(CargaRankingLeitura.round_hora).where(CargaRankingLeitura.round_hora >= desde).distinct()
    )).scalars().all()
    for rh in rounds_lidos:
        por_round[rh]  # garante o round mesmo sem nenhuma carga lida
    for r in leituras:
        por_round[r.round_hora].append(r)

    rounds = []
    totais = {"aceitas": 0, "no_ranking": 0, "fora": 0, "sem_aceite_nosso": 0}
    por_posicao = {1: 0, 2: 0, 3: 0}

    for round_hora, no_ranking in sorted(por_round.items(), reverse=True):
        aceites = (await db.execute(
            select(CargaAceite).where(
                CargaAceite.detectado_em >= round_hora - JANELA_ACEITE,
                CargaAceite.detectado_em < round_hora,
            ).order_by(CargaAceite.detectado_em)
        )).scalars().all()

        posicao_por_load = {}
        for r in no_ranking:
            if r.load_id:
                posicao_por_load.setdefault(r.load_id, r.posicao)
        loads_aceitos = {a.load_id for a in aceites if a.load_id}

        # Casa por load_id; sem ele (ou se divergir), cai na rota origem→destino, uma carga do ranking por aceite.
        usados: set[int] = set()
        for a in aceites:
            for i, r in enumerate(no_ranking):
                if a.load_id and r.load_id == a.load_id:
                    usados.add(i)
        casado_por_rota: dict[int, tuple[int, int]] = {}
        for ia, a in enumerate(aceites):
            if a.load_id and a.load_id in posicao_por_load:
                continue
            chave = _chave_rota(a.origem, a.destino)
            for i, r in enumerate(no_ranking):
                if i not in usados and _chave_rota(r.origem, r.destino) == chave:
                    usados.add(i)
                    casado_por_rota[ia] = (r.posicao, i)
                    break

        itens = []
        for ia, a in enumerate(aceites):
            posicao = posicao_por_load.get(a.load_id) if a.load_id else None
            if not posicao and ia in casado_por_rota:
                posicao = casado_por_rota[ia][0]
            itens.append({
                "load_id": a.load_id, "origem": a.origem, "destino": a.destino,
                "data_carregamento": a.data_carregamento, "quantidade": a.quantidade,
                "status": "ranking" if posicao else "fora", "posicao": posicao,
            })
            totais["aceitas"] += 1
            if posicao:
                totais["no_ranking"] += 1
                por_posicao[posicao] += 1
            else:
                totais["fora"] += 1

        sem_aceite = [
            {"posicao": r.posicao, "load_id": r.load_id, "origem": r.origem, "destino": r.destino}
            for i, r in enumerate(no_ranking)
            if i not in usados and (not r.load_id or r.load_id not in loads_aceitos)
        ]
        totais["sem_aceite_nosso"] += len(sem_aceite)

        rounds.append({
            "round": round_hora.astimezone(BR_TZ).strftime("%Y-%m-%d %H:00"),
            "aceitas": itens,
            "sem_aceite_nosso": sem_aceite,
        })

    return {"dias": dias, "totais": totais, "por_posicao": por_posicao, "rounds": rounds}
