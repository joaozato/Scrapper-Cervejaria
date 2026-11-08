from datetime import datetime

scraper_state = {
    "status": "Inativo. Aguardando próximo ciclo.",
    "last_update": None,
    "is_running": False,
    "cards_read": 0,
    "total_cards": 0,
    "cancel_requested": False,
    "modo_atual": None  # "full" (Carga Prioritária + Pool) ou "pool" (só Pool, passe de 10min)
}

def update_status(status_msg: str, is_running: bool = None, cards_read: int = None, total_cards: int = None):
    scraper_state["status"] = status_msg
    scraper_state["last_update"] = datetime.now().isoformat()
    if is_running is not None:
        scraper_state["is_running"] = is_running
    if cards_read is not None:
        scraper_state["cards_read"] = cards_read
    if total_cards is not None:
        scraper_state["total_cards"] = total_cards
