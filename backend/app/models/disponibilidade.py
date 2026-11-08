import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional
from sqlalchemy import (
    String, Integer, DateTime, ForeignKey, Numeric, Index
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Disponibilidade(Base):
    __tablename__ = "disponibilidades"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4
    )
    motorista_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("motoristas.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    mes: Mapped[str] = mapped_column(
        String(20), nullable=False
    )
    dia_disponivel: Mapped[int] = mapped_column(
        Integer, nullable=False
    )
    plts: Mapped[int] = mapped_column(
        Integer, nullable=False, default=25
    )
    origem: Mapped[str] = mapped_column(
        String(255), nullable=False
    )
    destino_preferencia: Mapped[str] = mapped_column(
        String(255), nullable=False
    )
    valor: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=0
    )
    cadastro: Mapped[str] = mapped_column(
        String(3), nullable=False, default="NOK"
    )
    tarifa_cargo: Mapped[str] = mapped_column(
        String(3), nullable=False, default="NOK"
    )
    gr: Mapped[str] = mapped_column(
        String(3), nullable=False, default="NOK"
    )
    pode_carregar_direto: Mapped[str] = mapped_column(
        String(3), nullable=False, default="NOK"
    )
    data_conversa: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    motorista = relationship(
        "Motorista", back_populates="disponibilidades", lazy="selectin"
    )
    user = relationship("User", lazy="selectin")

    __table_args__ = (
        Index("ix_disp_dia_mes", "dia_disponivel", "mes"),
        Index("ix_disp_data_conversa", "data_conversa"),
    )

    def compute_pode_carregar(self):
        """Derive pode_carregar_direto from cadastro and gr."""
        if self.cadastro == "OK" and self.gr == "OK":
            self.pode_carregar_direto = "OK"
        else:
            self.pode_carregar_direto = "NOK"
