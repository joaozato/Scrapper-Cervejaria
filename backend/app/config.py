from pydantic_settings import BaseSettings
from typing import List
import os


class Settings(BaseSettings):
    # App Env
    ENVIRONMENT: str = "development"

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://cargo_admin:change_me@localhost:5433/cargo_disponibilidade"

    # Security
    SECRET_KEY: str = "change-me-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    COOKIE_SECURE: bool = False

    def model_post_init(self, __context):
        if self.ENVIRONMENT == "production":
            self.COOKIE_SECURE = True

    # CORS
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000"

    # Admin seed
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = "change_me"

    # Google Sheets sync — desligado (2026-08-05): não é mais usado, o foco
    # do produto saiu de disponibilidade de motoristas para captação/aceite/
    # confirmação de cargas. Código mantido (não removido) caso volte a ser
    # necessário; INTERVAL_SECONDS fica sem efeito enquanto ENABLED=False.
    GOOGLE_SHEET_ID: str = "YOUR_GOOGLE_SHEET_ID"
    GOOGLE_SHEET_GID: str = "0"
    SHEETS_SYNC_INTERVAL_SECONDS: int = 180
    SHEETS_SYNC_ENABLED: bool = False

    # Portal Scraper
    PORTAL_USER: str | None = None
    PORTAL_PASS: str | None = None
    PORTAL_SCRAPER_ENABLED: bool = True

    # Insights com IA (opcional): sem chave, o modal mostra só os destaques
    # calculados no backend. A LLM só escreve texto a partir dos agregados.
    GEMINI_API_KEY: str | None = None
    INSIGHTS_LLM_MODEL: str = "gemini-3.1-flash-lite"
    # Orçamento mensal de tokens (referência pra barra de uso do modal: o
    # Google não expõe a cota restante pela API).
    INSIGHTS_TOKENS_LIMITE_MES: int = 1_000_000

    # Integração ERP — endpoint já preparado, mas desligado até a integração
    # real ser validada (evita expor uma rota de envio de dados sem necessidade).
    ERP_INTEGRATION_ENABLED: bool = False

    # API de integração (leitura de cargas e relatórios para a IA interna da
    # empresa). None = endpoint desligado (404 em vez de aceitar sem chave).
    INTEGRATION_API_KEY: str | None = None

    # Frontend static files directory
    STATIC_DIR: str = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist")
    )

    @property
    def cors_origins_list(self) -> List[str]:
        if not self.CORS_ORIGINS:
            return []
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]

    @property
    def async_database_url(self) -> str:
        url = self.DATABASE_URL
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+asyncpg://", 1)
        elif url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        elif url.startswith("postgresql+psycopg://"):
            url = url.replace("postgresql+psycopg://", "postgresql+asyncpg://", 1)
        return url

    model_config = {
        "env_file": os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"),
        "env_file_encoding": "utf-8",
    }


settings = Settings()
