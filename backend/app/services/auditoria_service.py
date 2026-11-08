"""Auditoria SOMENTE LEITURA da consistência dos dados (scrapers, aceites, rankings, cargas).
Devolve uma lista de achados em texto; lista vazia = tudo certo."""
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.carga import Carga
from app.models.carga_aceite import CargaAceite
from app.models.carga_ranking import CargaRanking, CargaRankingLeitura
from app.services.ranking_service import calcular_ranking


async def auditar(db: AsyncSession, horas: int = 24) -> list[str]:
    agora = datetime.now(timezone.utc)
    desde = agora - timedelta(hours=horas)
    achados: list[str] = []

    ultima = (await db.execute(select(func.max(Carga.data_captura)))).scalar()
    if not ultima or agora - ultima > timedelta(hours=2):
        achados.append(f"[scraper] última captura de cargas: {ultima} (>2h: scraper parado?)")

    lidos = {r.replace(minute=0, second=0, microsecond=0) for r in (await db.execute(
        select(CargaRankingLeitura.round_hora).where(CargaRankingLeitura.round_hora >= desde)
    )).scalars().all()}
    h = desde.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    faltando = []
    while h < agora - timedelta(minutes=30):
        if h not in lidos:
            faltando.append(h.isoformat(timespec="minutes"))
        h += timedelta(hours=1)
    if faltando:
        achados.append(f"[ranking] {len(faltando)} round(s) sem leitura: {', '.join(faltando[:12])}")

    sem_load_aceite = (await db.execute(select(func.count()).select_from(CargaAceite).where(
        CargaAceite.detectado_em >= desde, CargaAceite.load_id.is_(None)))).scalar()
    if sem_load_aceite:
        achados.append(f"[aceites] {sem_load_aceite} aceite(s) sem load_id")
    sem_load_rank = (await db.execute(select(func.count()).select_from(CargaRanking).where(
        CargaRanking.round_hora >= desde, CargaRanking.load_id.is_(None)))).scalar()
    if sem_load_rank:
        achados.append(f"[ranking] {sem_load_rank} linha(s) de ranking sem load_id (cruzamento cai na rota)")

    dup = (await db.execute(
        select(CargaAceite.load_id, func.count()).where(CargaAceite.load_id.is_not(None))
        .group_by(CargaAceite.load_id).having(func.count() > 1))).all()
    if dup:
        achados.append(f"[aceites] load_id repetido em aceites: {[d[0] for d in dup[:10]]}")

    ruins = (await db.execute(select(func.count()).select_from(Carga).where(
        Carga.quantidade <= 0))).scalar()
    if ruins:
        achados.append(f"[cargas] {ruins} carga(s) com quantidade <= 0")

    res = await calcular_ranking(db, max(1, horas // 24 or 1))
    t = res["totais"]
    if t["sem_aceite_nosso"]:
        achados.append(f"[cruzamento] {t['sem_aceite_nosso']} carga(s) no ranking sem aceite casado "
                       f"(de {t['aceitas']} aceites; {t['no_ranking']} no ranking, {t['fora']} fora)")
    return achados
