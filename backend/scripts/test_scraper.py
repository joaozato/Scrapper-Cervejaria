import asyncio
import os
import sys

from dotenv import load_dotenv
load_dotenv()

from app.services.scraper_portal import run_scraper
import logging

logging.basicConfig(level=logging.INFO)

# Run the scraper
if __name__ == "__main__":
    print("Iniciando modo de teste visual do Scraper...")
    asyncio.run(run_scraper())
