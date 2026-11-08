import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Boolean, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Motorista(Base):
    __tablename__ = "motoristas"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4
    )
    nome: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True
    )
    tipo: Mapped[str] = mapped_column(
        String(50), nullable=False, default="motorista"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True
    )
    rota_frequente: Mapped[str] = mapped_column(
        String(255), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    disponibilidades = relationship(
        "Disponibilidade", back_populates="motorista", lazy="selectin"
    )
