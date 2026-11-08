import schedule
import time
import subprocess
import logging
from datetime import datetime
import os

# Força o fuso horário para São Paulo, especialmente importante para Railway
os.environ['TZ'] = 'America/Sao_Paulo'
if hasattr(time, 'tzset'):
    time.tzset()

# Configuração de Logs
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("cargo.scheduler")

def run_scraper():
    logger.info("==========================================")
    logger.info(f"Iniciando execução agendada do scraper - {datetime.now().strftime('%H:%M:%S')}")
    logger.info("==========================================")
    try:
        # Usa o interpretador python atual para rodar o test_scraper.py
        import sys
        result = subprocess.run([sys.executable, "test_scraper.py"], capture_output=True, text=True)
        if result.returncode == 0:
            logger.info("Scraper executado e concluído. Aguardando a próxima janela.")
        else:
            logger.error(f"Scraper retornou erro ou aviso.\nLog: {result.stderr[-500:]}") # Mostra os últimos 500 caracteres do erro
    except Exception as e:
        logger.error(f"Erro inesperado ao executar o scraper: {e}")

# Lista de horários exatos para rodar (com delay de 10 minutos após o Portal)
horarios = ["07:10"]

# Gera os horários das 08h até 22h, rodando sempre aos 40 minutos (ex: 08:40, 09:40, 10:40)
for hora in range(8, 23):
    hora_str = str(hora).zfill(2)
    horarios.append(f"{hora_str}:40")

# Agendando todas as execuções no relógio interno
for t in horarios:
    schedule.every().day.at(t).do(run_scraper)

logger.info("==================================================================")
logger.info("SISTEMA DE AGENDAMENTO ATIVADO COM SUCESSO (PORTAL CARGO)")
logger.info("==================================================================")
logger.info("O robô acordará sozinho nos seguintes horários todos os dias:")
logger.info(", ".join(horarios))
logger.info("==================================================================")

if __name__ == "__main__":
    while True:
        schedule.run_pending()
        time.sleep(30) # Dorme por 30 segundos entre as verificações para economizar CPU
