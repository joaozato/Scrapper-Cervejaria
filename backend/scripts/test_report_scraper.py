import asyncio
import os
import sys
import logging

# Adicionar o diretório raiz do backend ao sys.path para garantir que os imports funcionem
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from dotenv import load_dotenv
load_dotenv()

from app.services.scraper_portal import run_report_scraper

logging.basicConfig(level=logging.INFO)

if __name__ == "__main__":
    print("Iniciando modo de teste visual do Scraper de Relatório...")
    asyncio.run(run_report_scraper())
