import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional
from sqlalchemy import (
    String, Integer, DateTime, Numeric, Index, UniqueConstraint
)
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class Carga(Base):
    __tablename__ = "cargas"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4
    )
    origem: Mapped[str] = mapped_column(
        String(255), nullable=False
    )
    destino: Mapped[str] = mapped_column(
        String(255), nullable=False
    )
    data_carregamento: Mapped[str] = mapped_column(
        String(20), nullable=False
    )
    peso_kg: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2), nullable=True
    )
    valor: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2), nullable=True
    )
    status_portal: Mapped[str] = mapped_column(
        String(50), nullable=False
    )
    tipo_carga: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True
    )
    tipo_caminhao: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True
    )
    quantidade: Mapped[int] = mapped_column(
        Integer, default=1, nullable=False
    )
    load_id: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True
    )
    fonte: Mapped[str] = mapped_column(
        String(50), default="Smart Cargas", nullable=False
    )
    data_captura: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    tags: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )
    ultima_visualizacao: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    round_hora: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True
    )
    observacao: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )
    
    __table_args__ = (
        Index("ix_carga_data_carregamento", "data_carregamento"),
        Index("ix_carga_data_captura", "data_captura"),
        UniqueConstraint("load_id", "fonte", name="uq_carga_load_id_fonte"),
    )
