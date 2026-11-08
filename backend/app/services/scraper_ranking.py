"""Scraper SÓ DE LEITURA dos rankings (1º, 2º e 3º lugar) do Carga Prioritária.

Roda no início de cada hora, em sessão própria, com estado próprio
(`ranking_state`): não usa o `scraper_state` nem a trava `is_running` do scraper
principal, então não briga com os passes do Pool/Carga Prioritária/relatório e eles
não o pulam. Não clica em "Confirmar" nem em nada que altere a carga.

Cada carga encontrada num ranking é gravada em carga_rankings; o cruzamento com
os aceites do round anterior (carga_aceites) é feito na hora da consulta, em
ranking_service.
"""
import asyncio
import logging
import random
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from playwright.async_api import async_playwright
from playwright_stealth import Stealth

from app.database import AsyncSessionLocal as SessionLocal
from app.models.carga_ranking import CargaRanking, CargaRankingLeitura
from app.services.route_names import normalize_origem, normalize_destino

logger = logging.getLogger("cargo.ranking")

BR_TZ = ZoneInfo("America/Sao_Paulo")

ranking_state = {
    "status": "Inativo. Aguardando próxima leitura.",
    "last_update": None,
    "is_running": False,
    "ultima_leitura": None,
}

# Se os 3 rankings vierem vazios (o Portal pode demorar a popular a virada de
# hora), tenta de novo algumas vezes antes de desistir.
TENTATIVAS_LEITURA = 4
INTERVALO_TENTATIVAS_SEGUNDOS = 45

POSICOES = (1, 2, 3)


def _status(msg: str, is_running: bool = None):
    logger.info(f"[Ranking] {msg}")
    ranking_state["status"] = msg
    ranking_state["last_update"] = datetime.now().isoformat()
    if is_running is not None:
        ranking_state["is_running"] = is_running


async def _login(page) -> bool:
    from app.services.scraper_portal import PORTAL_URL, PORTAL_USER, PORTAL_PASS

    await page.goto(PORTAL_URL)
    partner_selector = 'div[data-testid="ClbCard"]:has-text("Parceiro"), div.welcome-card:has-text("Parceiro"), div.welcome-card:has-text("Partner")'
    await page.wait_for_selector(partner_selector, timeout=15000)
    await page.click(partner_selector)
    await asyncio.sleep(random.uniform(0.5, 1.0))

    username_sel = 'input#username, input[type="email"], input[name="username"], input[name="email"]'
    password_sel = 'input#password, input[type="password"], input[name="password"]'
    submit_sel = 'input#kc-login, button[type="submit"], input[type="submit"], input[value="Entrar"]'
    await page.wait_for_selector(username_sel, timeout=15000)
    await page.locator(username_sel).click()
    await page.locator(username_sel).type(PORTAL_USER, delay=40)
    await page.locator(password_sel).click()
    await page.locator(password_sel).type(PORTAL_PASS, delay=40)
    await page.click(submit_sel)
    await asyncio.sleep(random.uniform(1.5, 2.5))

    tab_sel = 'text=/Prioritária\\s*Cargas/i'
    try:
        await page.wait_for_selector(tab_sel, timeout=30000)
        await page.click(tab_sel)
    except Exception as e:
        logger.error(f"[Ranking] aba Carga Prioritária não encontrada em 30s: {e}")
        return False
    await asyncio.sleep(random.uniform(1.0, 1.8))
    return True


async def _ler_modal(page, info_icon) -> str:
    """Abre o modal de detalhes do card e devolve o load_id ('' se não achar)."""
    await info_icon.scroll_into_view_if_needed()
    try:
        await info_icon.click(timeout=3000)
    except Exception:
        await info_icon.click(force=True)
    await page.wait_for_selector('i.clb-icon-close', state='visible', timeout=10000)
    modal = page.locator(
        'div.offer-details-modal:visible, div[role="dialog"]:visible, .modal-content:visible, .MuiDialog-paper:visible'
    ).first
    texto = await modal.inner_text()
    load_id = ""
    for linha in texto.split('\n'):
        linha = linha.strip().replace('\xa0', ' ')
        if linha.startswith('Load '):
            load_id = linha.replace('Load ', '').strip()
        elif linha.startswith('Pedido ') and not load_id:
            load_id = linha.replace('Pedido ', '').strip()
        elif linha.startswith('Freight Order ') and not load_id:
            load_id = linha.replace('Freight Order ', '').strip()
    try:
        await page.locator('i.clb-icon-close:visible').first.click(timeout=3000)
    except Exception:
        await page.keyboard.press("Escape")
    await asyncio.sleep(random.uniform(0.3, 0.6))
    return load_id


async def _ler_posicao(page, posicao: int) -> list[dict]:
    """Expande a seção da colocação e lê os cards dela."""
    secao = page.locator('.position-section').filter(has=page.locator(f'.position-badge.position-{posicao}')).first
    if await secao.count() == 0:
        logger.warning(f"[Ranking] seção da {posicao}ª colocação não encontrada")
        return []

    header = secao.locator('button.position-section-header').first
    if (await header.get_attribute('aria-expanded')) != 'true':
        await header.scroll_into_view_if_needed()
        await header.click(timeout=10000)
        await asyncio.sleep(random.uniform(0.8, 1.4))

    cards = secao.locator('.offer-card')
    total = await cards.count()
    achadas = []
    for i in range(total):
        card = cards.nth(i)
        try:
            origem = await card.locator('.card-loads-body__origin .card-loads-body__routeDetailLabel-data').first.inner_text(timeout=2000)
            destino = await card.locator('.card-loads-body__destination .card-loads-body__routeDetailLabel-data').first.inner_text(timeout=2000)
        except Exception:
            origem, destino = "", ""
        load_id = ""
        try:
            load_id = await _ler_modal(page, card.locator('i.clb-icon-info').first)
        except Exception as e:
            logger.warning(f"[Ranking] {posicao}ª colocação, card {i + 1}: modal não abriu ({e})")
        achadas.append({
            "posicao": posicao,
            "load_id": load_id or None,
            "origem": normalize_origem(origem.strip()),
            "destino": normalize_destino(destino.strip()),
        })

    # Recolhe a seção depois de ler: com ela aberta, o conteúdo (.offer-details)
    # cobre o cabeçalho da seguinte e intercepta o clique do mouse.
    try:
        await header.scroll_into_view_if_needed()
        await header.click(timeout=10000)
        await asyncio.sleep(random.uniform(0.5, 1.0))
    except Exception as e:
        logger.warning(f"[Ranking] não consegui recolher a {posicao}ª colocação: {e}")
    return achadas


def _inicio_da_hora(ref: datetime) -> datetime:
    return ref.astimezone(BR_TZ).replace(minute=0, second=0, microsecond=0).astimezone(timezone.utc)


async def run_ranking_scraper():
    from app.services.scraper_portal import PORTAL_USER, PORTAL_PASS, CHROMIUM_LAUNCH_ARGS

    if not PORTAL_USER or not PORTAL_PASS:
        _status("Credenciais do Portal não configuradas. Leitura cancelada.", is_running=False)
        return
    if ranking_state["is_running"]:
        logger.info("[Ranking] leitura anterior ainda em andamento, pulando este disparo.")
        return

    _status("Iniciando leitura dos rankings...", is_running=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=CHROMIUM_LAUNCH_ARGS)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
            locale="pt-BR",
            timezone_id="America/Sao_Paulo",
        )
        page = await context.new_page()
        await Stealth().apply_stealth_async(page)
        try:
            if not await _login(page):
                _status("Falha ao abrir o Carga Prioritária. Leitura encerrada.", is_running=False)
                return

            lidas: list[dict] = []
            tela_lida = False
            for tentativa in range(1, TENTATIVAS_LEITURA + 1):
                _status(f"Lendo rankings (tentativa {tentativa}/{TENTATIVAS_LEITURA})...")
                try:
                    await page.wait_for_selector('.position-section', timeout=15000)
                except Exception:
                    logger.warning("[Ranking] seções de colocação não apareceram em 15s")
                lidas = []
                try:
                    for posicao in POSICOES:
                        lidas += await _ler_posicao(page, posicao)
                    # Só vale como leitura se os 3 rankings foram percorridos até o fim;
                    # leitura parcial acusaria "fora do ranking" sem prova.
                    tela_lida = True
                except Exception as e:
                    lidas = []
                    logger.error(f"[Ranking] erro lendo os rankings na tentativa {tentativa}: {e}")
                if lidas:
                    break
                if tentativa < TENTATIVAS_LEITURA:
                    await asyncio.sleep(INTERVALO_TENTATIVAS_SEGUNDOS)
                    await page.reload()
                    await asyncio.sleep(random.uniform(2.0, 3.0))

            agora = datetime.now(timezone.utc)
            round_hora = _inicio_da_hora(agora)
            if tela_lida:
                # Grava a leitura mesmo com os rankings vazios: é o que permite
                # apontar aceites que nem entraram no ranking.
                async with SessionLocal() as db:
                    db.add(CargaRankingLeitura(round_hora=round_hora, lido_em=agora, total_cargas=len(lidas)))
                    for c in lidas:
                        db.add(CargaRanking(round_hora=round_hora, lido_em=agora, **c))
                    await db.commit()
            else:
                _status("Tela de rankings não carregou; leitura descartada (não conta como 'fora do ranking').", is_running=False)
                return
            ranking_state["ultima_leitura"] = agora.isoformat()
            _status(f"Leitura concluída: {len(lidas)} carga(s) nos rankings.", is_running=False)
        except Exception as e:
            logger.exception(f"[Ranking] erro: {e}")
            _status(f"Erro na leitura dos rankings: {e}", is_running=False)
        finally:
            ranking_state["is_running"] = False
            await browser.close()
