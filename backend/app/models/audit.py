import uuid
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    user_name: Mapped[str] = mapped_column(
        String(255), nullable=True
    )
    action: Mapped[str] = mapped_column(
        String(100), nullable=False, index=True
    )
    target_type: Mapped[str] = mapped_column(
        String(100), nullable=True
    )
    target_id: Mapped[str] = mapped_column(
        String(255), nullable=True
    )
    details: Mapped[str] = mapped_column(
        Text, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True
    )

    # Optional relationship to user
    user = relationship("User", lazy="joined")
