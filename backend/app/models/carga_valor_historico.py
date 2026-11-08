import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional
from sqlalchemy import String, DateTime, Numeric, Index
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class CargaValorHistorico(Base):
    """Uma linha toda vez que o valor de uma carga muda (e na 1ª vez que ela é
    vista com valor). Permite ver a evolução do frete enquanto a carga fica no
    pool. O valor da própria carga (cargas.valor) não é alterado por isso."""

    __tablename__ = "carga_valor_historico"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    load_id: Mapped[str] = mapped_column(String(100), nullable=False)
    fonte: Mapped[str] = mapped_column(String(50), nullable=False)
    origem: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    destino: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    valor: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    registrado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = (
        Index("ix_carga_valor_hist_load", "load_id", "fonte", "registrado_em"),
        Index("ix_carga_valor_hist_registrado", "registrado_em"),
    )
