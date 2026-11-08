import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional
from sqlalchemy import String, Integer, DateTime, Numeric, Index
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class CargaAceite(Base):
    """Momento em que o scraper viu a carga do Carga Prioritária como "Aceita" (por
    qualquer pessoa, não só pelo bot). Uma linha por carga: gravada na primeira
    detecção e só tem a quantidade atualizada depois."""
    __tablename__ = "carga_aceites"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    carga_id: Mapped[uuid.UUID] = mapped_column(nullable=False, unique=True)
    load_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    fonte: Mapped[str] = mapped_column(String(50), nullable=False)
    origem: Mapped[str] = mapped_column(String(255), nullable=False)
    destino: Mapped[str] = mapped_column(String(255), nullable=False)
    data_carregamento: Mapped[str] = mapped_column(String(20), nullable=False)
    tipo_carga: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    quantidade: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    valor: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    detectado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    # "completo" (passe das :40) ou "extra" (passe das :55, antes de a janela fechar)
    passe: Mapped[str] = mapped_column(String(20), default="completo", nullable=False)

    __table_args__ = (
        Index("ix_carga_aceite_detectado_em", "detectado_em"),
        Index("ix_carga_aceite_data_carregamento", "data_carregamento"),
    )
