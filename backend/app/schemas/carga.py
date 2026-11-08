import uuid
from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class CargaBase(BaseModel):
    origem: str
    destino: str
    data_carregamento: str
    peso_kg: Optional[Decimal] = None
    valor: Optional[Decimal] = None
    status_portal: str
    tipo_carga: Optional[str] = None
    tipo_caminhao: Optional[str] = None
    quantidade: int = 1
    load_id: Optional[str] = None
    fonte: str = "Carga Prioritária"
    tags: Optional[str] = None
    ultima_visualizacao: Optional[datetime] = None
    round_hora: Optional[int] = None
    observacao: Optional[str] = None


class CargaUpdateObservacao(BaseModel):
    observacao: str


class CargaDeleteRequest(BaseModel):
    motivo: str = Field(..., min_length=3, max_length=500)


class CargaBulkDeleteRequest(BaseModel):
    ids: List[uuid.UUID] = Field(..., min_length=1, max_length=200)
    motivo: str = Field(..., min_length=3, max_length=500)


class CargaCreate(CargaBase):
    pass


class CargaResponse(CargaBase):
    id: uuid.UUID
    data_captura: datetime

    model_config = ConfigDict(from_attributes=True)


class CargaListResponse(BaseModel):
    items: List[CargaResponse]
    total: int


class PorDiaItem(BaseModel):
    dia: str
    quantidade: int


class PorMesItem(BaseModel):
    mes: str
    quantidade: int


class CargaResumoResponse(BaseModel):
    total_cargas: int
    valor_total: float
    peso_total: float
    por_dia: List[PorDiaItem]
    por_mes: List[PorMesItem]


class CargaOpcoesResponse(BaseModel):
    tipos_carga: List[str]
    dias_carregamento: List[str]
    dias_captura: List[str]
    rounds: List[str]
    fontes: List[str]
    meses_disponiveis: List[str]
    meses_captura_disponiveis: List[str]
