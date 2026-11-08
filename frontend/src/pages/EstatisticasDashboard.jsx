import React, { useEffect, useState, useMemo } from 'react';
import api from '../api/client';
import { 
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend
} from 'recharts';
import useStore from '../store/useStore';
import AceitesRelatorio from '../components/AceitesRelatorio';
import RankingAceites from '../components/RankingAceites';
import ChatCargas from '../components/ChatCargas';

const SUGESTOES_ESTATISTICAS = [
  'Quantas cargas aceitamos nos últimos 7 dias e quantas foram confirmadas no relatório?',
  'Em qual dia a diferença entre aceitas e confirmadas foi maior?',
  'Qual o faturamento aceito por rota esta semana?',
  'O passe das :55 está detectando aceites que o das :40 perdia?',
];

const ABAS = [
  ['aceites', 'Aceites x Relatório'],
  ['ranking', 'Aceites x Ranking'],
  ['faturamento', 'Faturamento'],
  ['ia', 'Perguntar à IA'],
];

export default function EstatisticasDashboard() {
  const [cargas, setCargas] = useState([]);
  const [loading, setLoading] = useState(true);
  const [aba, setAba] = useState('aceites');
  
  const baixarCsv = async (endpoint, arquivo) => {
    try {
      const res = await api.get(endpoint, { responseType: 'blob' });
      const url = URL.createObjectURL(res.data);
      const a = document.createElement('a');
      a.href = url;
      a.download = arquivo;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      alert('Não foi possível baixar o CSV.');
    }
  };

  const fetchCargas = async () => {
    try {
      const res = await api.get('/cargas', { params: { limit: 100000 } });
      // Filtra apenas as ganhas e que são "Lata" ou "Arroz"
      const ganhas = res.data.items.filter(c => {
        const isGanha = c.status_portal === 'Aceita' || c.status_portal === 'Confirmada';
        const tipoCarga = (c.tipo_carga || '').toLowerCase();
        const isArrozOuLata = tipoCarga.includes('arroz') || tipoCarga.includes('lata');
        
        return isGanha && isArrozOuLata;
      });
      setCargas(ganhas);
    } catch (error) {
      console.error('Erro ao buscar cargas:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchCargas();
    const interval = setInterval(fetchCargas, 15 * 60 * 1000); // 15 min refresh
    return () => clearInterval(interval);
  }, []);

  // KPIs
  const kpis = useMemo(() => {
    let faturamentoAceita = 0;
    let faturamentoConfirmada = 0;
    let pesoTotal = 0;
    let totalCargas = 0;

    cargas.forEach(c => {
      const qtde = c.quantidade || 1;
      const valorRaw = Number(c.valor) || 0;
      const pesoKg = Number(c.peso_kg) || 0;
      
      let valorPorCaminhao = valorRaw;
      if (valorRaw > 0 && valorRaw < 1000 && pesoKg > 0) {
        valorPorCaminhao = valorRaw * (pesoKg / 1000); // É tarifa por tonelada
      }
      
      const valTotal = valorPorCaminhao * qtde;

      if (c.status_portal === 'Aceita') {
        faturamentoAceita += valTotal;
      } else if (c.status_portal === 'Confirmada') {
        faturamentoConfirmada += valTotal;
      }
      
      pesoTotal += pesoKg * qtde;
      totalCargas += qtde;
    });

    return { faturamentoAceita, faturamentoConfirmada, pesoTotal, totalCargas };
  }, [cargas]);

  // Gráfico: Faturamento por Rota
  const dataPorRota = useMemo(() => {
    const rotas = {};
    cargas.forEach(c => {
      const rota = `${c.origem || '?'} ➔ ${c.destino || '?'}`;
      const qtde = c.quantidade || 1;
      const valorRaw = Number(c.valor) || 0;
      const pesoKg = Number(c.peso_kg) || 0;
      
      let valorPorCaminhao = valorRaw;
      if (valorRaw > 0 && valorRaw < 1000 && pesoKg > 0) {
        valorPorCaminhao = valorRaw * (pesoKg / 1000);
      }
      
      if (!rotas[rota]) rotas[rota] = { rota, Aceita: 0, Confirmada: 0 };
      rotas[rota][c.status_portal] += (valorPorCaminhao * qtde);
    });

    // Ordenar pelas rotas que mais deram dinheiro
    return Object.values(rotas).sort((a, b) => (b.Aceita + b.Confirmada) - (a.Aceita + a.Confirmada)).slice(0, 10);
  }, [cargas]);

  // Gráfico: Faturamento por Dia
  const dataPorDia = useMemo(() => {
    const dias = {};
    cargas.forEach(c => {
      const dia = c.data_carregamento || 'Indefinido';
      const qtde = c.quantidade || 1;
      const valorRaw = Number(c.valor) || 0;
      const pesoKg = Number(c.peso_kg) || 0;
      
      let valorPorCaminhao = valorRaw;
      if (valorRaw > 0 && valorRaw < 1000 && pesoKg > 0) {
        valorPorCaminhao = valorRaw * (pesoKg / 1000);
      }
      
      if (!dias[dia]) dias[dia] = { dia, Aceita: 0, Confirmada: 0 };
      dias[dia][c.status_portal] += (valorPorCaminhao * qtde);
    });
    
    return Object.values(dias).sort((a, b) => a.dia.localeCompare(b.dia));
  }, [cargas]);

  const formatCurrency = (value) => {
    return new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL', minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(value);
  };

  const conteudoFaturamento = loading ? (
    <div style={{ padding: '24px', textAlign: 'center' }}>Carregando faturamento...</div>
  ) : (
    <>
      
      {/* KPIs Grid */}
      <div className="dashboard-grid" style={{ marginBottom: '32px', display: 'flex', gap: '24px' }}>
        
        <div className="card stat-card" style={{ flex: 1 }}>
          <div className="card-body">
            <div className="stat-value" style={{ color: 'var(--cargo-success)' }}>
              {formatCurrency(kpis.faturamentoAceita + kpis.faturamentoConfirmada)}
            </div>
            <div className="stat-label">Faturamento Total Estimado</div>
            <div style={{ marginTop: '8px', fontSize: '0.85rem', fontWeight: 'bold' }}>
              <span style={{ color: 'var(--cargo-warning)' }}>Aceitas: {formatCurrency(kpis.faturamentoAceita)}</span> |{' '}
              <span style={{ color: 'var(--cargo-success)' }}>Confirmadas: {formatCurrency(kpis.faturamentoConfirmada)}</span>
            </div>
          </div>
        </div>
        
        <div className="card stat-card" style={{ flex: 1 }}>
          <div className="card-body">
            <div className="stat-value" style={{ color: 'var(--cargo-primary, #C2410C)' }}>{kpis.totalCargas}</div>
            <div className="stat-label">Total de Cargas Fechadas</div>
            <div style={{ marginTop: '8px', fontSize: '0.85rem', color: '#6b7280' }}>Unidades / Veículos</div>
          </div>
        </div>
        
        <div className="card stat-card" style={{ flex: 1 }}>
          <div className="card-body">
            <div className="stat-value" style={{ color: 'var(--cargo-warning)' }}>
              {(kpis.pesoTotal / 1000).toLocaleString('pt-BR', { maximumFractionDigits: 1 })} <span style={{fontSize: '1rem'}}>t</span>
            </div>
            <div className="stat-label">Volume Movimentado</div>
          </div>
        </div>
      </div>

      {/* Gráficos Grid */}
      <div className="dashboard-grid" style={{ display: 'flex', gap: '24px', marginBottom: '32px' }}>
        
        <div className="card" style={{ flex: 1 }}>
          <div className="card-header">
            <h3 className="card-title">Faturamento por Dia</h3>
          </div>
          <div className="card-body">
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={dataPorDia} margin={{ top: 20, right: 20, left: 20, bottom: 20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" vertical={false} />
                <XAxis 
                  dataKey="dia" 
                  stroke="#6b7280" 
                  tick={{ fill: '#6b7280', fontSize: 12, fontWeight: 500 }} 
                  axisLine={false} 
                  tickLine={false}
                  dy={10}
                />
                <YAxis 
                  stroke="#6b7280" 
                  tick={{ fill: '#6b7280', fontSize: 12, fontWeight: 500 }} 
                  axisLine={false} 
                  tickLine={false}
                  tickFormatter={(val) => `R$${(val/1000).toFixed(0)}k`}
                />
                <Tooltip 
                  contentStyle={{ backgroundColor: 'white', border: '1px solid #e5e7eb', borderRadius: '8px', boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)' }}
                  itemStyle={{ color: '#1f2937', fontWeight: 'bold' }}
                  formatter={(value) => formatCurrency(value)}
                />
                <Legend wrapperStyle={{ paddingTop: '20px' }} />
                <Bar dataKey="Aceita" stackId="a" fill="var(--cargo-warning)" name="Aceitas (R$)" radius={[0, 0, 0, 0]} barSize={40} />
                <Bar dataKey="Confirmada" stackId="a" fill="var(--cargo-success)" name="Confirmadas (R$)" radius={[4, 4, 0, 0]} barSize={40} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="card" style={{ flex: 1 }}>
          <div className="card-header">
            <h3 className="card-title">Faturamento por Rota (Top 10)</h3>
          </div>
          <div className="card-body">
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={dataPorRota} margin={{ top: 20, right: 20, left: 20, bottom: 60 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" vertical={false} />
                <XAxis 
                  dataKey="rota" 
                  stroke="#6b7280" 
                  tick={{ fill: '#6b7280', fontSize: 11, fontWeight: 500 }} 
                  axisLine={false} 
                  tickLine={false}
                  angle={-25}
                  textAnchor="end"
                  height={80}
                  dx={-10}
                  dy={10}
                  tickFormatter={(val) => val.length > 20 ? val.substring(0, 20) + '...' : val}
                />
                <YAxis 
                  stroke="#6b7280" 
                  tick={{ fill: '#6b7280', fontSize: 12, fontWeight: 500 }} 
                  axisLine={false} 
                  tickLine={false}
                  tickFormatter={(val) => `R$${(val/1000).toFixed(0)}k`}
                />
                <Tooltip 
                  contentStyle={{ backgroundColor: 'white', border: '1px solid #e5e7eb', borderRadius: '8px', boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)' }}
                  itemStyle={{ color: '#1f2937', fontWeight: 'bold' }}
                  formatter={(value) => formatCurrency(value)}
                  labelFormatter={(label) => `Rota: ${label}`}
                />
                <Legend wrapperStyle={{ paddingTop: '20px' }} />
                <Bar dataKey="Aceita" stackId="a" fill="var(--cargo-warning)" name="Aceitas (R$)" radius={[0, 0, 0, 0]} barSize={40} />
                <Bar dataKey="Confirmada" stackId="a" fill="var(--cargo-success)" name="Confirmadas (R$)" radius={[4, 4, 0, 0]} barSize={40} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
        
      </div>

      {/* Tabela de Detalhes */}
      <div className="card">
        <div className="card-header">
          <h3 className="card-title">Listagem de Cargas Ganhas</h3>
        </div>
        <div className="table-container" style={{ maxHeight: '500px', overflowY: 'auto' }}>
          <table className="data-table">
            <thead style={{ position: 'sticky', top: 0, zIndex: 10, backgroundColor: 'white' }}>
              <tr>
                <th style={{ padding: '12px 16px', fontWeight: '500', color: '#4b5563' }}>Status</th>
                <th style={{ padding: '12px 16px', fontWeight: '500', color: '#4b5563' }}>Origem</th>
                <th style={{ padding: '12px 16px', fontWeight: '500', color: '#4b5563' }}>Destino</th>
                <th style={{ padding: '12px 16px', fontWeight: '500', color: '#4b5563' }}>Data</th>
                <th style={{ padding: '12px 16px', fontWeight: '500', color: '#4b5563' }}>Tipo</th>
                <th style={{ padding: '12px 16px', fontWeight: '500', color: '#4b5563', textAlign: 'center' }}>Qtd</th>
                <th style={{ padding: '12px 16px', fontWeight: '500', color: '#4b5563', textAlign: 'right' }}>Valor Estimado</th>
              </tr>
            </thead>
            <tbody>
              {cargas.map((c, i) => {
                const qtde = c.quantidade || 1;
                const valorRaw = Number(c.valor) || 0;
                const pesoKg = Number(c.peso_kg) || 0;
                let valorPorCaminhao = valorRaw;
                if (valorRaw > 0 && valorRaw < 1000 && pesoKg > 0) {
                  valorPorCaminhao = valorRaw * (pesoKg / 1000);
                }
                const valTotal = valorPorCaminhao * qtde;

                return (
                  <tr key={`${c.id}-${i}`} style={{ borderBottom: '1px solid #e5e7eb' }}>
                    <td style={{ padding: '12px 16px' }}>
                      <span style={{ 
                        backgroundColor: c.status_portal === 'Confirmada' ? '#ecfccb' : '#fef3c7', 
                        color: c.status_portal === 'Confirmada' ? '#4d7c0f' : '#b45309', 
                        padding: '2px 8px', borderRadius: '12px', fontSize: '0.75rem', fontWeight: 'bold' 
                      }}>
                        {c.status_portal}
                      </span>
                    </td>
                    <td style={{ padding: '12px 16px', fontWeight: '500' }}>{c.origem}</td>
                    <td style={{ padding: '12px 16px', fontWeight: '500' }}>{c.destino}</td>
                    <td style={{ padding: '12px 16px' }}>{c.data_carregamento}</td>
                    <td style={{ padding: '12px 16px' }}>{c.tipo_carga || '-'}</td>
                    <td style={{ padding: '12px 16px', textAlign: 'center', fontWeight: 'bold' }}>{qtde}</td>
                    <td style={{ padding: '12px 16px', textAlign: 'right', fontWeight: 'bold', color: '#059669' }}>{formatCurrency(valTotal)}</td>
                  </tr>
                )
              })}
              {cargas.length === 0 && (
                <tr>
                  <td colSpan="7" style={{ textAlign: 'center', padding: '24px' }}>Nenhuma carga fechada encontrada ainda.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );

  return (
    <div style={{ padding: '0 24px 24px 24px' }}>
      <div style={{ display: 'flex', gap: 8, marginBottom: 20, flexWrap: 'wrap' }}>
        {ABAS.map(([id, rotulo]) => (
          <button
            key={id}
            className={aba === id ? 'btn btn-primary' : 'btn btn-outline'}
            onClick={() => setAba(id)}
          >
            {rotulo}
          </button>
        ))}
        <button className="btn btn-outline" style={{ marginLeft: 'auto' }}
          onClick={() => baixarCsv('/estatisticas/rotas-acompanhadas/export', 'cargas_rotas_acompanhadas.csv')}>
          Baixar CSV de cada carga
        </button>
        <button className="btn btn-outline"
          onClick={() => baixarCsv('/estatisticas/rotas-acompanhadas/resumo', 'resumo_rotas_acompanhadas.csv')}>
          Baixar resumo mês a mês
        </button>
        <button className="btn btn-outline"
          onClick={() => baixarCsv('/estatisticas/rotas-acompanhadas/diagnostico', 'diagnostico_rotas_acompanhadas.csv')}>
          Diagnóstico de origens não casadas
        </button>
      </div>

      {aba === 'aceites' && <AceitesRelatorio />}
      {aba === 'ranking' && <RankingAceites />}
      {aba === 'faturamento' && conteudoFaturamento}
      {aba === 'ia' && (
        <div className="card">
          <div className="card-header">
            <h3 className="card-title">Pergunte sobre aceites, confirmações, cargas e faturamento</h3>
          </div>
          <div className="card-body">
            <ChatCargas sugestoes={SUGESTOES_ESTATISTICAS} maxAltura="60vh" />
          </div>
        </div>
      )}
    </div>
  );
}
