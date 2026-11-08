from app.models.user import User
from app.models.motorista import Motorista
from app.models.disponibilidade import Disponibilidade
from app.models.carga import Carga
from app.models.audit import AuditLog
from app.models.relatorio_carga import RelatorioCaptura, RelatorioCargaItem, RelatorioCargaDiff
from app.models.insights_uso import InsightsUso
from app.models.carga_valor_historico import CargaValorHistorico
from app.models.carga_aceite import CargaAceite
from app.models.carga_ranking import CargaRanking, CargaRankingLeitura

__all__ = [
    "User", "Motorista", "Disponibilidade", "Carga", "AuditLog",
    "RelatorioCaptura", "RelatorioCargaItem", "RelatorioCargaDiff",
    "InsightsUso", "CargaValorHistorico", "CargaAceite",
    "CargaRanking", "CargaRankingLeitura",
]
