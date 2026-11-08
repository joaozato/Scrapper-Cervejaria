import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import String, Integer, DateTime, Index
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class CargaRanking(Base):
    """Carga vista nos rankings (1º, 2º ou 3º lugar) do Carga Prioritária na leitura do
    início da hora. Uma linha por (leitura, posição, carga). Uma leitura sem
    nenhuma carga não grava linhas — quem diz que ela rodou é o log do scraper."""
    __tablename__ = "carga_rankings"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    # Início da hora (UTC) a que a leitura se refere: o ranking do round que fechou na hora anterior
    round_hora: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    posicao: Mapped[int] = mapped_column(Integer, nullable=False)
    load_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    origem: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    destino: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    lido_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = (
        Index("ix_carga_ranking_round_hora", "round_hora"),
        Index("ix_carga_ranking_load_id", "load_id"),
    )


class CargaRankingLeitura(Base):
    """Uma linha por leitura dos rankings que de fato abriu a tela (mesmo com os 3
    rankings vazios). É ela que permite dizer "aceita mas fora do ranking": sem
    ela, uma leitura vazia seria indistinguível de uma leitura que não rodou."""
    __tablename__ = "carga_ranking_leituras"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    round_hora: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    total_cargas: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    lido_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = (Index("ix_carga_ranking_leitura_round_hora", "round_hora"),)
