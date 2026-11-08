from pydantic import BaseModel, Field, model_validator
from uuid import UUID
from datetime import datetime
from decimal import Decimal
from typing import Optional


class DisponibilidadeCreate(BaseModel):
    motorista_id: UUID
    mes: str = Field(..., max_length=20)
    dia_disponivel: int = Field(..., ge=1, le=31)
    plts: int = Field(default=25, ge=1)
    origem: str = Field(..., max_length=255)
    destino_preferencia: str = Field(..., max_length=255)
    valor: Decimal = Field(..., ge=0, decimal_places=2)
    cadastro: str = Field(default="NOK", pattern="^(OK|NOK)$")
    tarifa_cargo: str = Field(default="NOK", pattern="^(OK|NOK)$")
    gr: str = Field(default="NOK", pattern="^(OK|NOK)$")


class DisponibilidadeUpdate(BaseModel):
    motorista_id: Optional[UUID] = None
    mes: Optional[str] = Field(None, max_length=20)
    dia_disponivel: Optional[int] = Field(None, ge=1, le=31)
    plts: Optional[int] = Field(None, ge=1)
    origem: Optional[str] = Field(None, max_length=255)
    destino_preferencia: Optional[str] = Field(None, max_length=255)
    valor: Optional[Decimal] = Field(None, ge=0)
    cadastro: Optional[str] = Field(None, pattern="^(OK|NOK)$")
    tarifa_cargo: Optional[str] = Field(None, pattern="^(OK|NOK)$")
    gr: Optional[str] = Field(None, pattern="^(OK|NOK)$")
    data_conversa: Optional[datetime] = None


class MotoristaInfo(BaseModel):
    id: UUID
    nome: str
    tipo: str

    model_config = {"from_attributes": True}


class DisponibilidadeResponse(BaseModel):
    id: UUID
    motorista_id: UUID
    motorista: Optional[MotoristaInfo] = None
    mes: str
    dia_disponivel: int
    plts: int
    origem: str
    destino_preferencia: str
    valor: Decimal
    cadastro: str
    tarifa_cargo: str
    gr: str
    pode_carregar_direto: str
    data_conversa: datetime
    updated_by: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DashboardPorRotaResponse(BaseModel):
    origem: str
    count: int
    motoristas: list[DisponibilidadeResponse]


class DashboardTotalResponse(BaseModel):
    total_disponiveis: int
    total_podem_carregar: int
    total_nao_podem: int


class DashboardDiasResponse(BaseModel):
    dia: int
    count: int


class RankingMotoristaResponse(BaseModel):
    motorista_id: UUID
    motorista_nome: str
    total_dias: int
    pode_carregar: str
    cadastro: str
    gr: str
