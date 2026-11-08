import uuid
from datetime import date, datetime, timezone
from typing import Optional
from sqlalchemy import String, DateTime, Date, Integer, Boolean, ForeignKey, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class RelatorioCaptura(Base):
    __tablename__ = "relatorio_capturas"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    data_referencia: Mapped[date] = mapped_column(Date, nullable=False)
    capturado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    origem_captura: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="sucesso")
    total_linhas_csv: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_itens_lata: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    arquivo_nome: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    executado_por_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    mensagem_erro: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    __table_args__ = (
        Index("ix_relatorio_captura_data_referencia", "data_referencia"),
    )


class RelatorioCargaItem(Base):
    __tablename__ = "relatorio_carga_itens"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    relatorio_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("relatorio_capturas.id"), nullable=False
    )
    pedido_insumos: Mapped[str] = mapped_column(String(100), nullable=False)
    carga_tms: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    tipo_material: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    origem: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    destino: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    data_carregamento: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    status_prioritaria: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    aceita: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    confirmado: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    reprogramacao: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    data_original: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    dados_raw: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    __table_args__ = (
        Index("ix_relatorio_item_relatorio_id", "relatorio_id"),
        Index("ix_relatorio_item_pedido_insumos", "pedido_insumos"),
    )


class RelatorioCargaDiff(Base):
    __tablename__ = "relatorio_carga_diffs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    relatorio_atual_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("relatorio_capturas.id"), nullable=False
    )
    relatorio_anterior_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("relatorio_capturas.id"), nullable=True
    )
    pedido_insumos: Mapped[str] = mapped_column(String(100), nullable=False)
    tipo_mudanca: Mapped[str] = mapped_column(String(20), nullable=False)
    status_anterior: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    status_atual: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    origem: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    destino: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    data_carregamento: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    elegivel_erp: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    __table_args__ = (
        Index("ix_relatorio_diff_relatorio_atual_id", "relatorio_atual_id"),
    )
