import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import String, Integer, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class InsightsUso(Base):
    """Uma linha por chamada ao Gemini feita pelo modal de Insights, com os
    tokens consumidos (usageMetadata da API). Soma = uso total da API."""

    __tablename__ = "insights_uso"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    modelo: Mapped[str] = mapped_column(String(80), nullable=False)
    periodo_dias: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    tokens_entrada: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    tokens_saida: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    tokens_total: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
