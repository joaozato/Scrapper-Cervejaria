from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime
from typing import Optional


class MotoristaCreate(BaseModel):
    nome: str = Field(..., min_length=2, max_length=255)
    tipo: str = Field(default="motorista", pattern="^(motorista|proprietario)$")
    rota_frequente: Optional[str] = Field(None, max_length=255)


class MotoristaUpdate(BaseModel):
    nome: Optional[str] = Field(None, min_length=2, max_length=255)
    tipo: Optional[str] = Field(None, pattern="^(motorista|proprietario)$")
    is_active: Optional[bool] = None
    rota_frequente: Optional[str] = Field(None, max_length=255)


class MotoristaResponse(BaseModel):
    id: UUID
    nome: str
    tipo: str
    is_active: bool
    rota_frequente: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}
