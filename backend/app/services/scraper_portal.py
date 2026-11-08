import os
import asyncio
import logging
from decimal import Decimal
from datetime import datetime, timezone, timedelta
from playwright.async_api import async_playwright
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import random
from playwright_stealth import Stealth

from app.database import AsyncSessionLocal as SessionLocal
from app.models.carga import Carga
from app.models.carga_aceite import CargaAceite
from app.config import settings
from app.services.scraper_state import update_status, scraper_state
from app.services.route_names import normalize_origem, normalize_destino
from app.services.valor_historico import registrar_valor
import re

logger = logging.getLogger("cargo.scraper")

STATIC_DIR = os.path.join(os.path.dirname(__file__), "..", "static")
os.makedirs(STATIC_DIR, exist_ok=True)
SCREENSHOT_PATH = os.path.join(STATIC_DIR, "live_view.jpg")

_ultimo_snap = 0.0


async def log_and_snap(page, msg: str, cards_read=None, total_cards=None):
    global _ultimo_snap
    logger.info(msg)
    update_status(msg, is_running=True, cards_read=cards_read, total_cards=total_cards)
    # Screenshot da tela ao vivo no máximo a cada 3s: tirar um por mensagem (3+ por card) custava segundos de CPU.
    agora = asyncio.get_event_loop().time()
    if page and agora - _ultimo_snap >= 3:
        _ultimo_snap = agora
        try:
            await page.screenshot(path=SCREENSHOT_PATH, quality=60, type='jpeg')
        except:
            pass

# A lista de cargas (Carga Prioritária / Pool) rola dentro de um contêiner próprio, e a roda do mouse só rola o que
# está debaixo do ponteiro: com o mouse parado no canto da tela nada rolava e o lazy load parava nos 30 primeiros
# cards. Tudo aqui é mouse real (move + wheel), sem executar JavaScript na página.
async def _mouse_sobre_a_lista(page, icons):
    caixa = await icons.first.bounding_box()
    if caixa:
        await page.mouse.move(caixa["x"] + caixa["width"] / 2, caixa["y"] + caixa["height"] / 2, steps=random.randint(8, 15))


async def rolar_ate_o_fim(page, icons, max_rodadas: int = 150) -> int:
    """Gira a roda do mouse sobre a lista até o lazy load parar de trazer cards (4 rodadas seguidas sem
    novos). Devolve o total de cards carregados."""
    await _mouse_sobre_a_lista(page, icons)
    total = await icons.count()
    estavel = 0
    for _ in range(max_rodadas):
        for _ in range(random.randint(3, 5)):
            await page.mouse.wheel(0, random.randint(700, 1000))
            await asyncio.sleep(random.uniform(0.08, 0.2))
        await asyncio.sleep(random.uniform(0.8, 1.3))
        novo = await icons.count()
        estavel = estavel + 1 if novo == total else 0
        total = novo
        if estavel >= 4:
            break
    return total


async def voltar_ao_topo(page, icons, total: int):
    await _mouse_sobre_a_lista(page, icons)
    for _ in range(max(6, total // 4)):
        await page.mouse.wheel(0, -1500)
        await asyncio.sleep(random.uniform(0.05, 0.15))
    await asyncio.sleep(0.5)


def _ler_card_pool(texto: str) -> dict:
    """Extrai do texto visível do card do Pool o que ele já mostra (sem abrir o modal)."""
    linhas = [l.strip().replace(chr(160), " ") for l in texto.split(chr(10)) if l.strip()]
    d = {"load_id": linhas[0] if linhas else "", "origem": "", "destino": "", "data_coleta": "", "tags": "", "peso": "", "valor": ""}
    for i, l in enumerate(linhas):
        prox = linhas[i + 1] if i + 1 < len(linhas) else ""
        if l == "Origem": d["origem"] = prox
        elif l == "Destino": d["destino"] = prox
        elif l == "Carregamento": d["data_coleta"] = prox
        elif l.upper().endswith(" KG"): d["peso"] = l
        elif l.startswith("R$"): d["valor"] = l
        elif l in ('Produto Acabado', 'Retornável', 'Venda Direta', 'Insumos', 'Produto Revenda', 'Embalagens', 'Embalagem'):
            d["tags"] = f"{d['tags']}, {l}" if d["tags"] else l
    return d


PORTAL_URL = os.getenv("PORTAL_URL", "https://portal.example.com/login")
PORTAL_USER = settings.PORTAL_USER
PORTAL_PASS = settings.PORTAL_PASS

# Guarda o (dia, round) do Carga Prioritária já processado nesta execução do processo, para blindar
# contra execução manual + automática caindo no mesmo round (o que somaria a mesma carga em dobro).
_ultimo_round_smart_processado = None

# Flags do Chromium headless. As 4 primeiras já existiam (stealth/sandbox no
# container). As de baixo desligam subsistemas do Chrome que não fazem falta
# num scraper headless (GPU compositing, telemetria, extensões, autoupdate de
# safebrowsing etc.) — reduz o pico de RAM de cada execução sem tocar em
# renderização/screenshot, que é o que o app realmente usa.
CHROMIUM_LAUNCH_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--start-maximized",
    "--no-sandbox",
    "--disable-dev-shm-usage",
    "--disable-gpu",
    "--disable-extensions",
    "--disable-background-networking",
    "--disable-background-timer-throttling",
    "--disable-backgrounding-occluded-windows",
    "--disable-renderer-backgrounding",
    "--disable-breakpad",
    "--disable-component-extensions-with-background-pages",
    "--disable-default-apps",
    "--disable-sync",
    "--metrics-recording-only",
    "--mute-audio",
    "--no-first-run",
    "--safebrowsing-disable-auto-update",
]


async def registrar_aceite(db, carga: Carga, passe: str):
    """Grava (uma vez por carga) o momento em que a aceitação foi detectada; nas
    detecções seguintes só mantém a quantidade em dia."""
    from sqlalchemy import select
    await db.flush()  # garante carga.id em cargas recém-criadas
    evento = (await db.execute(select(CargaAceite).where(CargaAceite.carga_id == carga.id))).scalar_one_or_none()
    if evento:
        evento.quantidade = carga.quantidade or 1
        return
    db.add(CargaAceite(
        carga_id=carga.id, load_id=carga.load_id, fonte=carga.fonte, origem=carga.origem,
        destino=carga.destino, data_carregamento=carga.data_carregamento, tipo_carga=carga.tipo_carga,
        quantidade=carga.quantidade or 1, valor=carga.valor, passe=passe,
    ))


async def run_scraper(apenas_pool: bool = False, apenas_aceites: bool = False):
    """apenas_aceites: passe extra (antes de a janela do Carga Prioritária fechar) que só
    procura cargas que passaram a "Aceita" desde o passe completo — não soma
    quantidade nem cria cargas novas."""
    global _ultimo_round_smart_processado
    if not PORTAL_USER or not PORTAL_PASS:
        msg = "Credenciais do Portal não configuradas. Scraper cancelado."
        logger.warning(msg)
        update_status(msg, is_running=False)
        return

    if scraper_state.get("is_running"):
        # Guarda contra sobreposição: o passe do Pool a cada 10min e o passe
        # cheio de hora em hora rodam como jobs separados no scheduler, e não
        # podem abrir dois browsers simultâneos contra o mesmo login do
        # Portal.
        if apenas_pool:
            # Passe de 10min nunca tem prioridade - nem sobre outro passe de
            # 10min, nem sobre o completo. Só pula e tenta de novo no próximo.
            logger.info("Scraper já em execução, pulando este disparo do Pool (10min).")
            return
        if scraper_state.get("modo_atual") == "pool":
            # O passe completo (Carga Prioritária + Pool) tem prioridade sobre o de
            # 10min: pede pro passe de 10min encerrar (mesmo sinal do botão de
            # parada de emergência) e espera até ~30s ele ceder antes de seguir.
            logger.info("Passe completo bateu durante o passe de 10min do Pool - pedindo pra ele encerrar e assumindo.")
            scraper_state["cancel_requested"] = True
            for _ in range(60):
                if not scraper_state.get("is_running"):
                    break
                await asyncio.sleep(0.5)
            if scraper_state.get("is_running"):
                logger.error("Passe de 10min do Pool não encerrou a tempo - pulando este disparo do passe completo.")
                return
        else:
            logger.info("Scraper já em execução, pulando este disparo agendado.")
            return

    scraper_state["modo_atual"] = "pool" if apenas_pool else ("aceites" if apenas_aceites else "full")
    logger.info(f"Iniciando scraper do Portal (apenas_pool={apenas_pool}, apenas_aceites={apenas_aceites})...")
    scraper_state["cancel_requested"] = False
    
    async with async_playwright() as p:
        # O Railway não tem tela, então rodamos headless.
        is_headless = True
        await log_and_snap(None, f"Iniciando browser headless={is_headless}")
        
        browser = await p.chromium.launch(
            headless=is_headless,
            args=CHROMIUM_LAUNCH_ARGS
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
            locale="pt-BR",
            timezone_id="America/Sao_Paulo"
        )
        page = await context.new_page()
        # Aplica a camada de stealth para enganar detectores de bots
        await Stealth().apply_stealth_async(page)

        try:
            # Login
            await page.goto(PORTAL_URL)
            
            # Clicar em "Partner" (exatamente o botão visualizado no screenshot)
            await log_and_snap(page, "Aguardando e clicando no botão Partner...")
            partner_selector = 'div[data-testid="ClbCard"]:has-text("Parceiro"), div.welcome-card:has-text("Parceiro"), div.welcome-card:has-text("Partner")'
            try:
                await page.wait_for_selector(partner_selector, timeout=15000)
                await page.click(partner_selector)
            except Exception as e:
                logger.error("Erro ao achar o botão Partner. Tirando screenshot e baixando HTML.")
                await page.screenshot(path="debug_partner.png", full_page=True)
                with open("debug_partner.html", "w", encoding="utf-8") as f:
                    f.write(await page.content())
                raise e
            
            # Aguarda a tela de login carregar após clicar em Partner
            await asyncio.sleep(random.uniform(2.1, 4.5))
            
            await log_and_snap(page, "Preenchendo credenciais...")
            try:
                # O Keycloak pode variar os IDs
                username_sel = 'input#username, input[type="email"], input[name="username"], input[name="email"]'
                password_sel = 'input#password, input[type="password"], input[name="password"]'
                submit_sel = 'input#kc-login, button[type="submit"], input[type="submit"], input[value="Entrar"]'
                
                await page.wait_for_selector(username_sel, timeout=15000)
                await page.locator(username_sel).click()
                await page.locator(username_sel).type(PORTAL_USER, delay=150)
                await asyncio.sleep(random.uniform(0.5, 1.5))
                await page.locator(password_sel).click()
                await page.locator(password_sel).type(PORTAL_PASS, delay=150)
                await asyncio.sleep(random.uniform(0.7, 1.8))
                
                await log_and_snap(page, "Clicando em Sign in...")
                await page.click(submit_sel)
            except Exception as e:
                logger.error("Erro ao preencher login. Tirando screenshot e baixando HTML.")
                await page.screenshot(path="debug_login.png", full_page=True)
                with open("debug_login.html", "w", encoding="utf-8") as f:
                    f.write(await page.content())
                raise e
            
            await log_and_snap(page, "Aguardando login concluir e painel carregar...")
            
            tabs_to_process = [
                {"name": "Carga Prioritária", "selector": 'text=/Smart\\s*Cargas/i'},
                {"name": "Pool de Cargas", "selector": 'text=/Pool\\s*de\\s*Cargas/i'}
            ]
            if apenas_pool:
                # Passe rápido de 10 em 10 minutos: só Pool de Cargas, pra não
                # abrir o Carga Prioritária (que já tem sua própria cadência horária
                # e o guard de round_hora) fora de hora.
                tabs_to_process = [t for t in tabs_to_process if t["name"] == "Pool de Cargas"]
            elif apenas_aceites:
                tabs_to_process = [t for t in tabs_to_process if t["name"] == "Carga Prioritária"]

            from sqlalchemy import select, update
            async with SessionLocal() as db:
                for tab in tabs_to_process:
                    tab_name = tab["name"]
                    tab_sel = tab["selector"]

                    if tab_name == "Carga Prioritária":
                        hoje_utc = datetime.now(timezone.utc).date()
                        hora_atual = (datetime.now(timezone.utc) - timedelta(hours=3)).hour
                        round_atual = (hoje_utc, hora_atual)
                        if not apenas_aceites and _ultimo_round_smart_processado == round_atual:
                            await log_and_snap(page, f"Carga Prioritária já processado neste round ({hora_atual}h) hoje. Pulando para não contar a mesma carga em dobro.")
                            continue

                    try:
                        await page.wait_for_selector(tab_sel, timeout=30000)
                    except Exception as e:
                        await log_and_snap(page, f"Aviso: Não achei o botão {tab_name}.")
                        continue
                        
                    await log_and_snap(page, f"Clicando em {tab_name}...")
                    await asyncio.sleep(random.uniform(1.2, 3.1))
                    await page.click(tab_sel)
                    await asyncio.sleep(random.uniform(2.5, 5.0))
                    
                    # Espera os cards carregarem
                    try:
                        await page.wait_for_selector('i.clb-icon-info', timeout=15000)
                    except Exception as e:
                        await log_and_snap(page, f"Nenhuma carga disponível em {tab_name}.")
                        continue
                        
                    await log_and_snap(page, f"Mapeando página de {tab_name} (Simulando scroll humano para carregar tudo)...")
                    
                    info_icons_locator = page.locator('i.clb-icon-info')
                    
                    # Rola até o fim da lista (contêiner rolável) pra carregar TODOS os cards do lazy load
                    _t0 = asyncio.get_event_loop().time()
                    current_count = await rolar_ate_o_fim(page, info_icons_locator)
                    logger.info(f"[tempo] rolagem até o fim: {asyncio.get_event_loop().time() - _t0:.0f}s")
                    await log_and_snap(page, f"{current_count} cargas carregadas em {tab_name}.", cards_read=0, total_cards=current_count)

                    # Volta ao topo (roda do mouse) para começar a ler os cards na ordem certa
                    _t0 = asyncio.get_event_loop().time()
                    await voltar_ao_topo(page, info_icons_locator, current_count)
                    logger.info(f"[tempo] volta ao topo: {asyncio.get_event_loop().time() - _t0:.0f}s")

                    # Pool: o card já mostra load_id/origem/destino/data/peso/valor. Cargas que já estão no banco
                    # não precisam abrir o modal (só atualizam visualização/valor), o que corta o passe de minutos
                    # pra segundos e deixa ler as 100+ "sem tarifa" antes de expirarem.
                    resumo_cards, conhecidos = [], set()
                    if tab_name == "Pool de Cargas":
                        try:
                            cards_loc = page.locator('.card-loads')
                            resumo_cards = [_ler_card_pool(await cards_loc.nth(i).inner_text(timeout=5000))
                                            for i in range(await cards_loc.count())]
                            conhecidos = set((await db.execute(
                                select(Carga.load_id).where(Carga.fonte == "Pool de Cargas", Carga.load_id.is_not(None))
                            )).scalars().all())
                        except Exception as e:
                            logger.error(f"[Pool de Cargas] Pré-leitura dos cards falhou ({e}); lendo tudo pelo modal.")
                            resumo_cards, conhecidos = [], set()
                    logger.info(f"[tempo] pré-leitura dos cards: {asyncio.get_event_loop().time() - _t0:.0f}s ({len(resumo_cards)} cards)")
                    # Pausas encurtadas: Pool 30% (cargas conhecidas nem abrem o modal); Smart 40%, mas abrindo
                    # o modal de TODOS os cards (o card do Smart não traz o load_id, só o modal).
                    fator = 0.3 if tab_name == "Pool de Cargas" else 0.4

                    await log_and_snap(page, f"Lendo dados de todos os {current_count} cards em {tab_name} (somente leitura)...", total_cards=current_count)
                    cards_count = current_count
                    cargas_extraidas = []
                    
                    try:
                        for index in range(cards_count):
                            if scraper_state.get("cancel_requested"):
                                await log_and_snap(page, "Parada de emergência acionada. Abortando leitura...", cards_read=index, total_cards=cards_count)
                                break
                            
                            resumo = resumo_cards[index] if index < len(resumo_cards) else None
                            if resumo and resumo["load_id"] and resumo["data_coleta"] and resumo["load_id"] in conhecidos:
                                cargas_extraidas.append({
                                    "load_id": resumo["load_id"], "origem": resumo["origem"], "destino": resumo["destino"],
                                    "data_coleta": resumo["data_coleta"], "tipo_carga": "", "tipo_caminhao": "",
                                    "peso": resumo["peso"], "valor": resumo["valor"] if "R$" in resumo["valor"] else "",
                                    "pallets": "", "fonte": tab_name, "tags": resumo["tags"], "is_aceita": False,
                                })
                                continue

                            info_icon = page.locator('i.clb-icon-info').nth(index)
                            await log_and_snap(page, f"[{tab_name}] Lendo card {index+1} de {cards_count}...", cards_read=index, total_cards=cards_count)
                        
                            # Simular movimento humano
                            await info_icon.scroll_into_view_if_needed()
                            await info_icon.hover(timeout=5000)
                            await asyncio.sleep(random.uniform(0.5, 1.5) * fator)
                        
                            # Clicar EXATAMENTE no ícone de informação de forma 100% furtiva
                            try:
                                # Simula todo o movimento do mouse, hover e click físico via protocolo do navegador (isTrusted=true)
                                await info_icon.click(timeout=5000)
                            except:
                                # Se algo obstruir a visão do Playwright, force=True clica na coordenada exata do ícone sem injetar JS
                                await info_icon.click(force=True)
                            
                            await asyncio.sleep(random.uniform(2.5, 4.5) * fator)
                        
                            # Esperar pelo ícone de fechar (que sempre existe no modal, provando que ele abriu)
                            try:
                                await page.wait_for_selector('i.clb-icon-close', state='visible', timeout=15000)
                            except:
                                logger.error(f"Modal não abriu após clicar no card {index+1} em {tab_name}.")
                                raise Exception("Modal de detalhes não apareceu após o clique. Abortando card.")
                        
                            # Pegar o modal baseado na visibilidade
                            modal_element = page.locator('div.offer-details-modal:visible, div[role="dialog"]:visible, .modal-content:visible, .MuiDialog-paper:visible').first
                        
                            # Garantia: se não achou pelo seletor, pega o container ancestral do botão de fechar (no Pool de Cargas a classe muda)
                            if not await modal_element.is_visible():
                                modal_element = page.locator('.card-detail-header:visible').locator('..').first
                            
                            modal_text = await modal_element.inner_text()
                        
                            # Atualizar a TV para mostrar o modal aberto e os dados sendo extraídos
                            await log_and_snap(page, f"[{tab_name}] Modal do card {index+1} aberto! Extraindo dados...", cards_read=index, total_cards=cards_count)
                        
                            dados_carga = {
                                "load_id": "",
                                "origem": "",
                                "destino": "",
                                "data_coleta": "",
                                "tipo_carga": "",
                                "tipo_caminhao": "",
                                "peso": "",
                                "valor": "",
                                "pallets": "",
                                "fonte": tab_name,
                                "tags": "",
                                "is_aceita": False
                            }
                        
                            # Container do card na lista (não o modal) - usado tanto pra achar a tag
                            # "Aceita" (Carga Prioritária) quanto o bloco de valor que só existe no card
                            # do Pool de Cargas quando a carga tem tarifa definida (ver abaixo).
                            card_element = None
                            try:
                                card_element = info_icon.locator('xpath=ancestor::div[contains(@class, "card") or contains(@class, "ClbCard")]').first
                                if await card_element.count() == 0:
                                    card_element = info_icon.locator('xpath=../..')
                            except Exception:
                                card_element = None

                            if tab_name == "Carga Prioritária" and card_element is not None:
                                try:
                                    # Procura pela tag "Aceita" dentro desse card
                                    tag_labels = card_element.locator('.clb-tag--label')
                                    num_tags = await tag_labels.count()

                                    is_aceita = False
                                    for t_idx in range(num_tags):
                                        text = await tag_labels.nth(t_idx).inner_text()
                                        if "Aceita" in text:
                                            is_aceita = True
                                            break

                                    dados_carga["is_aceita"] = is_aceita
                                except Exception:
                                    pass
                        
                            for i, line in enumerate(modal_text.split('\n')):
                                line = line.strip().replace('\xa0', ' ')
                                if not line: continue
                            
                                if line.startswith('Load '):
                                    dados_carga["load_id"] = line.replace('Load ', '').strip()
                                elif line.startswith('Pedido ') and not dados_carga["load_id"]:
                                    dados_carga["load_id"] = line.replace('Pedido ', '').strip()
                                elif line.startswith('Freight Order ') and not dados_carga["load_id"]:
                                    dados_carga["load_id"] = line.replace('Freight Order ', '').strip()
                                
                                elif line in ('Origin', 'Origem'):
                                    dados_carga["origem"] = normalize_origem(modal_text.split('\n')[i+1].strip())
                                elif line in ('Destination', 'Destino'):
                                    dados_carga["destino"] = normalize_destino(modal_text.split('\n')[i+1].strip())
                                elif line in ('Date', 'Data', 'Carregamento', 'Loading'):
                                    dados_carga["data_coleta"] = modal_text.split('\n')[i+1].strip()
                                elif line in ('Charging', 'Carga'):
                                    dados_carga["tipo_carga"] = modal_text.split('\n')[i+1].strip()
                                elif line in ('Truck', 'Veículo', 'Caminhão'):
                                    dados_carga["tipo_caminhao"] = modal_text.split('\n')[i+1].strip()
                                elif 'KG' in line or 'kg' in line.lower():
                                    dados_carga["peso"] = line
                                elif 'R$' in line:
                                    dados_carga["valor"] = line
                                elif 'Plts' in line or 'plts' in line.lower():
                                    dados_carga["pallets"] = line
                                elif tab_name == "Pool de Cargas" and line in ('Produto Acabado', 'Retornável', 'Venda Direta', 'Insumos', 'Produto Revenda', 'Embalagens', 'Embalagem'):
                                    if dados_carga["tags"]:
                                        dados_carga["tags"] += f", {line}"
                                    else:
                                        dados_carga["tags"] = line

                            if not dados_carga["valor"] and card_element is not None:
                                # No Pool de Cargas o modal quase nunca traz valor (por isso nunca
                                # gravávamos preço nessas cargas) - mas quando a carga tem tarifa
                                # definida, ela aparece no CARD da lista (.load-card-body__price),
                                # visível só nesse caso (visibility:hidden quando não tem tarifa).
                                try:
                                    price_element = card_element.locator('.load-card-body__price').first
                                    if await price_element.count() > 0 and await price_element.is_visible():
                                        price_text = (await price_element.inner_text()).strip()
                                        if 'R$' in price_text:
                                            dados_carga["valor"] = price_text
                                except Exception:
                                    pass

                            cargas_extraidas.append(dados_carga)
                        
                            try:
                                close_icon = modal_element.locator('i.clb-icon-close').first
                                await asyncio.sleep(random.uniform(1.0, 3.0) * fator)
                                await close_icon.click(force=True, timeout=5000)
                                await modal_element.wait_for(state='hidden', timeout=5000)
                            except Exception as e:
                                logger.error(f"Falha CRÍTICA ao fechar modal da carga: {e}")
                                raise Exception("Não foi possível fechar o modal. Parando scraper para não bugar.")
                            
                            await asyncio.sleep(random.uniform(1.5, 3.5) * fator)
                    except Exception as e:
                        # Nao aborta o ciclo inteiro: mantem os cards ja lidos com sucesso
                        # (extraidos ate aqui) para serem salvos normalmente abaixo, e segue
                        # para a proxima aba em vez de perder tudo.
                        logger.error(f"[{tab_name}] Falha lendo um card, parando leitura desta aba mas mantendo os ja lidos: {e}")
                        await log_and_snap(page, f"[{tab_name}] Falha lendo um card, salvando os ja lidos e seguindo...")
                        
                    logger.info(f"Extração de {tab_name} concluída: {len(cargas_extraidas)} cards lidos na tela.")
                    
                    # Agrupar cargas
                    cargas_unicas = {}
                    for c in cargas_extraidas:
                        assinatura = (c["origem"], c["destino"], c["data_coleta"], c["load_id"])
                        if assinatura not in cargas_unicas:
                            cargas_unicas[assinatura] = c
                            cargas_unicas[assinatura]["quantidade"] = 1
                        else:
                            cargas_unicas[assinatura]["quantidade"] += 1
                            
                    novas_inseridas = 0
                    atualizadas = 0
                    
                    for assinatura, c in cargas_unicas.items():
                        peso_val = c.get("peso", "").replace("KG", "").replace("Kg", "").replace("kg", "").replace(".", "").replace(",", ".").strip()
                        try:
                            peso_kg = Decimal(peso_val) if peso_val else None
                        except:
                            peso_kg = None
                            
                        valor_val = c.get("valor", "").replace("R$", "").replace(".", "").replace(",", ".").strip()
                        try:
                            valor = Decimal(valor_val) if valor_val else None
                        except:
                            valor = None

                        hoje_utc = datetime.now(timezone.utc).date()
                        hora_atual = (datetime.now(timezone.utc) - timedelta(hours=3)).hour

                        pode_ter_duplicata_legada = False
                        if c["load_id"]:
                            # load_id agora é único por (load_id, fonte): a mesma carga pode existir
                            # como registro no Carga Prioritária e, separadamente, no Pool de Cargas.
                            query = select(Carga).where(
                                Carga.load_id == c["load_id"],
                                Carga.fonte == c["fonte"]
                            )
                        elif tab_name == "Carga Prioritária":
                            # No Carga Prioritária, a agregação é diária e busca SEM filtrar por round_hora:
                            # a mesma carga aparece de novo em rounds seguintes do mesmo dia enquanto
                            # ninguém confirma, e precisamos achar o registro de um round anterior para
                            # NÃO duplicar (ver bloco abaixo, que só soma se for o round atual).
                            from sqlalchemy import cast, Date
                            # order_by + first (em vez de scalar_one_or_none): dias com registros
                            # duplicados legados (criados round a round antes deste fix) tem mais de
                            # uma linha batendo no filtro, e queremos so a mais recente daqui pra frente.
                            query = select(Carga).where(
                                Carga.origem == c["origem"],
                                Carga.destino == c["destino"],
                                Carga.data_carregamento == c["data_coleta"],
                                Carga.fonte == c["fonte"],
                                cast(Carga.data_captura, Date) == hoje_utc
                            ).order_by(Carga.id.desc())
                            pode_ter_duplicata_legada = True
                        else:
                            # Pool de Cargas: busca o registro histórico para atualizar "última visualização"
                            query = select(Carga).where(
                                Carga.origem == c["origem"],
                                Carga.destino == c["destino"],
                                Carga.data_carregamento == c["data_coleta"],
                                Carga.fonte == c["fonte"]
                            )

                        result = await db.execute(query)
                        existente = result.scalars().first() if pode_ter_duplicata_legada else result.scalar_one_or_none()

                        passe = "extra" if apenas_aceites else "completo"
                        if apenas_aceites:
                            # Passe extra: só detecta aceitações novas, sem mexer em quantidade/valor.
                            if existente and c.get("is_aceita") and existente.status_portal != "Confirmada":
                                existente.status_portal = "Aceita"
                                await registrar_aceite(db, existente, passe)
                                atualizadas += 1
                            continue

                        if existente:
                            existente.ultima_visualizacao = datetime.now(timezone.utc)
                            await registrar_valor(db, existente.load_id, existente.fonte, existente.origem, existente.destino, valor)
                            if c["load_id"] and c["data_coleta"] and existente.data_carregamento != c["data_coleta"]:
                                # Match por load_id não filtra por data: se a carga foi reagendada no
                                # Portal (mesmo load_id, nova data de carregamento), sincroniza aqui -
                                # senão o registro fica preso na data antiga indefinidamente.
                                existente.data_carregamento = c["data_coleta"]
                            if tab_name == "Carga Prioritária":
                                if existente.data_captura.date() == hoje_utc:
                                    if existente.round_hora == hora_atual:
                                        # Mesmo round: soma normalmente (cards duplicados dentro da
                                        # mesma leitura, ou execução manual + automática no mesmo round).
                                        existente.quantidade += c["quantidade"]
                                    else:
                                        # Já capturada em round anterior HOJE: mesma carga ainda não
                                        # confirmada reaparecendo no Carga Prioritária. Ignora para não
                                        # inflar contagem/duplicar - só volta a contar amanhã.
                                        pass
                                else:
                                    # Registro de dia anterior com o mesmo load_id: reseta a contagem
                                    # em vez de acumular indefinidamente (e evita tentar inserir duplicado).
                                    existente.quantidade = c["quantidade"]
                                    existente.data_captura = datetime.now(timezone.utc)
                                    existente.round_hora = hora_atual
                                if c.get("is_aceita") and existente.status_portal != "Confirmada":
                                    existente.status_portal = "Aceita"
                                    await registrar_aceite(db, existente, passe)
                                atualizadas += 1
                        else:
                            status = "Aguardando confirmação"
                            if tab_name == "Carga Prioritária":
                                status = "Aceita" if c.get("is_aceita") else "Aguardando aceite"

                            nova_carga = Carga(
                                origem=c["origem"],
                                destino=c["destino"],
                                data_carregamento=c["data_coleta"],
                                peso_kg=peso_kg,
                                valor=valor,
                                status_portal=status,
                                tipo_carga=c["tipo_carga"],
                                tipo_caminhao=c["tipo_caminhao"],
                                quantidade=c["quantidade"],
                                load_id=c["load_id"] or None,
                                fonte=c["fonte"],
                                tags=c["tags"] if c["tags"] else None,
                                ultima_visualizacao=datetime.now(timezone.utc),
                                round_hora=hora_atual
                            )
                            db.add(nova_carga)
                            if tab_name == "Carga Prioritária" and c.get("is_aceita"):
                                await registrar_aceite(db, nova_carga, passe)
                            await registrar_valor(db, nova_carga.load_id, nova_carga.fonte, nova_carga.origem, nova_carga.destino, valor)
                            novas_inseridas += 1
                            
                    await db.commit()
                    if tab_name == "Carga Prioritária" and not apenas_aceites:
                        _ultimo_round_smart_processado = round_atual
                    await log_and_snap(page, f"[{tab_name}] Salvo! {novas_inseridas} novas, {atualizadas} quantidades atualizadas.", cards_read=cards_count, total_cards=cards_count)

            update_status("Finalizado com sucesso.", is_running=False)
            
        except Exception as e:
            logger.error(f"Erro no scraper do Portal: {e}")
            update_status(f"Erro: {e}", is_running=False)
        finally:
            await browser.close()


async def run_report_scraper(origem_captura: str = "agendado", executado_por_id=None):
    if not PORTAL_USER or not PORTAL_PASS:
        logger.warning("Credenciais ausentes. Report scraper cancelado.")
        return

    if scraper_state.get("is_running"):
        # Mesma trava de sobreposição do passe completo/Pool (ver run_scraper):
        # o relatório abre seu próprio browser/login, então não pode rodar ao
        # mesmo tempo que outro passe já esteja logado no Portal. Como o
        # passe completo/Pool roda a cada 10min e cada execução leva alguns
        # minutos, NÃO existe minuto da hora livre o bastante pra garantir
        # que nunca vai bater um no outro — por isso, em vez de desistir na
        # hora, espera até 3min o outro passe liberar antes de pular de vez
        # (só pula se, mesmo depois de esperar, ainda estiver ocupado).
        if scraper_state.get("modo_atual") == "pool":
            # O Pool roda a cada 10min e, com centenas de cargas, pode passar de :05 e comer a vaga do
            # relatório todo dia. O relatório (1x por hora) tem prioridade sobre ele: mesmo sinal da parada
            # de emergência, e o Pool volta no próximo disparo.
            logger.info("Relatório bateu durante o passe do Pool - pedindo pro Pool encerrar e assumindo.")
            scraper_state["cancel_requested"] = True
            for _ in range(60):
                if not scraper_state.get("is_running"):
                    break
                await asyncio.sleep(0.5)
        else:
            # Passe completo / de aceites (Carga Prioritária): não se interrompe (perderia aceites), então espera
            # até 10min por uma vaga em vez de desistir, já que a janela do relatório é de 1h.
            logger.info("Scraper já em execução - relatório vai aguardar até 10min por uma vaga...")
            for _ in range(120):
                await asyncio.sleep(5)
                if not scraper_state.get("is_running"):
                    break
        if scraper_state.get("is_running"):
            logger.error("Ainda ocupado após esperar - pulando este disparo do relatório.")
            return

    scraper_state["modo_atual"] = "relatorio"
    scraper_state["cancel_requested"] = False
    logger.info("Iniciando scraper de relatórios...")
    update_status("Iniciando busca do Relatório...", is_running=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=CHROMIUM_LAUNCH_ARGS
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
            locale="pt-BR",
            timezone_id="America/Sao_Paulo",
            accept_downloads=True
        )
        page = await context.new_page()
        await Stealth().apply_stealth_async(page)

        try:
            # Login
            await page.goto(PORTAL_URL)
            await log_and_snap(page, "Aguardando e clicando no botão Partner...")
            partner_selector = 'div[data-testid="ClbCard"]:has-text("Parceiro"), div.welcome-card:has-text("Parceiro"), div.welcome-card:has-text("Partner")'
            await page.wait_for_selector(partner_selector, timeout=15000)
            await page.click(partner_selector)
            
            await asyncio.sleep(random.uniform(2.1, 4.5))
            
            username_sel = 'input#username, input[type="email"], input[name="username"], input[name="email"]'
            password_sel = 'input#password, input[type="password"], input[name="password"]'
            submit_sel = 'input#kc-login, button[type="submit"], input[type="submit"], input[value="Entrar"]'
            
            await log_and_snap(page, "Preenchendo credenciais...")
            await page.wait_for_selector(username_sel, timeout=15000)
            
            await page.locator(username_sel).click()
            await page.locator(username_sel).type(PORTAL_USER, delay=150)
            await asyncio.sleep(random.uniform(0.5, 1.5))
            
            await page.locator(password_sel).click()
            await page.locator(password_sel).type(PORTAL_PASS, delay=150)
            await asyncio.sleep(random.uniform(0.7, 1.8))
            await log_and_snap(page, "Clicando em Sign in...")
            await page.click(submit_sel)
            
            # Navigate to Reports
            await log_and_snap(page, "Aguardando login e acessando menu Relatórios...")
            await asyncio.sleep(random.uniform(3.0, 5.0))
            try:
                await page.locator('a[href*="/report"]').first.click(timeout=10000)
            except:
                await page.get_by_text(re.compile(r"Relat[óo]rios", re.IGNORECASE)).first.click()
                
            await asyncio.sleep(random.uniform(2.0, 4.0))
            
            # Click "relatório de cargas"
            await log_and_snap(page, "Procurando combobox 'relatório de cargas'...")
            
            # Click the Ant Design Select input
            select_input = page.locator('.ant-select-selection-search-input').first
            if await select_input.count() > 0:
                await select_input.click()
                await asyncio.sleep(1.0)
                # Find the option in the dropdown list
                option = page.locator('.ant-select-item-option-content, .ant-select-item').filter(has_text=re.compile(r"Relat[óo]rio de cargas", re.IGNORECASE)).first
                if await option.count() == 0:
                    option = page.get_by_text(re.compile(r"Relat[óo]rio de cargas", re.IGNORECASE)).last
                await option.click()
            else:
                # Fallback to old behavior if input not found
                rel_cargas_link = page.locator('text=/relatório\\s*de\\s*cargas/i').first
                await rel_cargas_link.click()
                
            await asyncio.sleep(random.uniform(2.0, 4.0))
            
            # Dates: hoje até hoje+5 dias - o relatório passa a trazer também as
            # cargas já programadas para os próximos dias, não só as de hoje.
            hoje_str = datetime.now(timezone.utc).strftime("%d/%m/%Y")
            fim_str = (datetime.now(timezone.utc) + timedelta(days=5)).strftime("%d/%m/%Y")

            # Preencher datas
            await log_and_snap(page, "Preenchendo datas no formulário do relatório...")

            date_inputs = page.locator('input[placeholder="00/00/0000"], .ant-picker-input input')
            if await date_inputs.count() >= 2:
                # Data início
                await date_inputs.nth(0).click()
                await asyncio.sleep(0.3)
                await page.keyboard.press("Control+A")
                await page.keyboard.press("Backspace")
                await date_inputs.nth(0).type(hoje_str, delay=150)
                await page.keyboard.press("Enter")
                await asyncio.sleep(0.5)

                # Data Fim
                await date_inputs.nth(1).click()
                await asyncio.sleep(0.3)
                await page.keyboard.press("Control+A")
                await page.keyboard.press("Backspace")
                await date_inputs.nth(1).type(fim_str, delay=150)
                await page.keyboard.press("Enter")
            else:
                # Fallback antigo se não achar o placeholder 00/00/0000
                try:
                    await page.get_by_label(re.compile(r"Data in[íi]cio", re.IGNORECASE)).click()
                    await page.keyboard.press("Control+A")
                    await page.keyboard.press("Backspace")
                    await page.keyboard.type(hoje_str, delay=150)
                    await page.keyboard.press("Enter")
                except:
                    await page.get_by_text(re.compile(r"Data in[íi]cio", re.IGNORECASE)).click()
                    await page.keyboard.press("Tab")
                    await page.keyboard.type(hoje_str, delay=150)
                    await page.keyboard.press("Enter")

                await asyncio.sleep(0.5)
                try:
                    await page.get_by_label(re.compile(r"Data Fim", re.IGNORECASE)).click()
                    await page.keyboard.press("Control+A")
                    await page.keyboard.press("Backspace")
                    await page.keyboard.type(fim_str, delay=150)
                    await page.keyboard.press("Enter")
                except:
                    await page.get_by_text(re.compile(r"Data Fim", re.IGNORECASE)).click()
                    await page.keyboard.press("Tab")
                    await page.keyboard.type(fim_str, delay=150)
                    await page.keyboard.press("Enter")

            await asyncio.sleep(1.0)
            await log_and_snap(page, "Verificando se a data foi preenchida corretamente antes de gerar...")
            await asyncio.sleep(2.0)
            
            # Click "gerar relatorio"
            await log_and_snap(page, "Gerando e baixando arquivo de relatório (isso pode demorar)...")
            async with page.expect_download(timeout=60000) as download_info:
                btn_gerar = page.locator('span.button-label:has-text("Gerar relatório"), button:has-text("Gerar relatório"), button:has-text("gerar relatorio")').first
                if await btn_gerar.count() == 0:
                    btn_gerar = page.get_by_text(re.compile(r"gerar relat[óo]rio", re.IGNORECASE)).first
                await btn_gerar.click()
            
            download = await download_info.value
            
            import tempfile
            temp_dir = tempfile.gettempdir()
            download_path = os.path.join(temp_dir, f"relatorio_cargas_{datetime.now().timestamp()}.csv")
            await download.save_as(download_path)
            await log_and_snap(page, f"Relatório baixado com sucesso. Processando...")

            # Guarda a captura do relatório (histórico + comparação de mudanças
            # entre relatórios do mesmo dia), em paralelo à lógica de confirmação
            # de cargas já existente abaixo.
            try:
                from app.services import relatorio_carga_service
                async with SessionLocal() as db_relatorio:
                    await relatorio_carga_service.processar_relatorio(
                        db_relatorio,
                        download_path,
                        origem_captura=origem_captura,
                        arquivo_nome=os.path.basename(download_path),
                        executado_por_id=executado_por_id,
                    )
            except Exception as e:
                logger.error(f"Falha ao salvar histórico do relatório de cargas: {e}")

            # Process CSV
            import csv
            from sqlalchemy import select
            
            # Descobrindo o delimitador
            with open(download_path, mode='r', encoding='utf-8-sig') as f:
                sample = f.read(1024)
                delimiter = ';' if sample.count(';') > sample.count(',') else ','
            
            async with SessionLocal() as db:
                with open(download_path, mode='r', encoding='utf-8-sig') as f:
                    reader = csv.DictReader(f, delimiter=delimiter)
                    
                    atualizadas = 0
                    for row in reader:
                        # Nomes de coluna exatos do "Relatório de cargas" do Portal. A
                        # extração antiga era por substring genérica ('origem' in k.lower()),
                        # que neste layout de relatório pegava a coluna errada (ex.: "Tipo
                        # de carga" = sempre "Spot" em vez de "Tipo de material" = "Lata"),
                        # descartando todas as linhas e zerando a contagem de confirmadas.
                        tipo = (row.get("Tipo de material") or "").strip()
                        codigo_origem = (row.get("Código da origem") or "").strip()
                        codigo_destino = (row.get("Código de destino") or "").strip()
                        data = (row.get("Data de carregamento") or "").strip().split(" ")[0]

                        if "arroz" not in tipo.lower() and "lata" not in tipo.lower():
                            continue

                        if not codigo_origem or not codigo_destino or not data:
                            continue

                        origem = normalize_origem(codigo_origem)
                        destino = normalize_destino(codigo_destino)

                        query = select(Carga).where(
                            Carga.origem == origem.strip(),
                            Carga.destino == destino.strip(),
                            Carga.data_carregamento == data.strip(),
                            Carga.fonte == "Carga Prioritária"
                        )
                        result = await db.execute(query)
                        cargas = result.scalars().all()
                        for c in cargas:
                            if c.status_portal != "Confirmada":
                                c.status_portal = "Confirmada"
                                atualizadas += 1
                
                await db.commit()
                msg = f"Relatório processado. {atualizadas} cargas confirmadas!"
                await log_and_snap(page, msg)
                await asyncio.sleep(5.0)
                update_status(msg, is_running=False)
                
        except Exception as e:
            msg = f"Erro no scraper de relatórios: {e}"
            logger.error(msg)
            await asyncio.sleep(5.0)
            update_status(msg, is_running=False)
        finally:
            await browser.close()


async def start_scraper_scheduler():
    scheduler = AsyncIOScheduler(timezone="America/Sao_Paulo")
    
    # Horário 1: 07h10 (Primeiro tiro da manhã) - passe completo (Carga Prioritária + Pool)
    scheduler.add_job(run_scraper, 'cron', hour=7, minute=10)

    # Horários 2 ao Fim: 08h às 22h, aos 40 minutos (08:40, 09:40, 10:40...) - passe completo
    scheduler.add_job(run_scraper, 'cron', hour='8-22', minute=40)

    # Pool de Cargas a cada 10min, preenchendo os minutos que o passe completo
    # não cobre - mesma janela de horário (07h-22h) já usada acima. Smart
    # Cargas continua só no passe completo de hora em hora (seu round_hora já
    # é por hora cheia, não faria sentido rodar de 10 em 10).
    scheduler.add_job(run_scraper, 'cron', hour=7, minute='0,20,30,40,50', kwargs={"apenas_pool": True})
    scheduler.add_job(run_scraper, 'cron', hour='8-22', minute='0,10,20,30,50', kwargs={"apenas_pool": True})
    
    # Scraper de Relatório: por enquanto 1x por hora, na mesma janela (07h-22h).
    # Minuto 5 fica livre nas duas grades acima (passe completo em 10/40, Pool
    # em 0/10/20/30/40/50) - roda no "vão" antes de qualquer uma delas. Se
    # mesmo assim pegar outro passe ainda em andamento, o guard no início de
    # run_report_scraper só pula esta rodada e tenta de novo na próxima hora.
    # Passe extra de aceites no Carga Prioritária, 5 min antes de a janela fechar (o passe
    # completo roda no :40 e perderia aceites feitos pelos operadores depois disso).
    scheduler.add_job(run_scraper, 'cron', hour='7-22', minute=55, kwargs={"apenas_aceites": True})

    scheduler.add_job(run_report_scraper, 'cron', hour='7-22', minute=5)

    # Leitura dos rankings (1º/2º/3º lugar) logo após a virada da hora: sessão e
    # estado próprios (scraper_ranking.ranking_state), não usa a trava
    # is_running dos passes acima, então pode rodar junto com o Pool das :00.
    from app.services.scraper_ranking import run_ranking_scraper
    scheduler.add_job(run_ranking_scraper, 'cron', hour='8-23', minute=1)

    scheduler.start()
    
    # Keep the task alive
    while True:
        await asyncio.sleep(3600)
