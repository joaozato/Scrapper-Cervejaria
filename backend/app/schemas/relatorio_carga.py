import uuid
from datetime import date, datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict


class RelatorioCapturaResponse(BaseModel):
    id: uuid.UUID
    data_referencia: date
    capturado_em: datetime
    origem_captura: str
    status: str
    total_linhas_csv: int
    total_itens_lata: int
    arquivo_nome: Optional[str] = None
    mensagem_erro: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class RelatorioCapturaListResponse(BaseModel):
    items: List[RelatorioCapturaResponse]
    total: int


class RelatorioCargaItemResponse(BaseModel):
    id: uuid.UUID
    pedido_insumos: str
    carga_tms: Optional[str] = None
    tipo_material: Optional[str] = None
    origem: Optional[str] = None
    destino: Optional[str] = None
    data_carregamento: Optional[str] = None
    status_smartcargas: Optional[str] = None
    aceita: Optional[str] = None
    confirmado: Optional[str] = None
    reprogramacao: Optional[str] = None
    data_original: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class RelatorioCapturaDetailResponse(RelatorioCapturaResponse):
    itens: List[RelatorioCargaItemResponse]


class RelatorioCargaDiffResponse(BaseModel):
    id: uuid.UUID
    pedido_insumos: str
    tipo_mudanca: str
    status_anterior: Optional[str] = None
    status_atual: Optional[str] = None
    origem: Optional[str] = None
    destino: Optional[str] = None
    data_carregamento: Optional[str] = None
    elegivel_erp: bool

    model_config = ConfigDict(from_attributes=True)


class RelatorioComparacaoResponse(BaseModel):
    relatorio_atual_id: uuid.UUID
    relatorio_anterior_id: Optional[uuid.UUID] = None
    total_novos: int
    total_sumidos: int
    total_status_alterado: int
    novos: List[RelatorioCargaDiffResponse]
    sumidos: List[RelatorioCargaDiffResponse]
    status_alterado: List[RelatorioCargaDiffResponse]
