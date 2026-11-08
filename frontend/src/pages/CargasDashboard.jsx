import React, { useEffect, useRef, useState } from 'react';
import api from '../api/client';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Brush
} from 'recharts';
import useStore from '../store/useStore';
import LiveMonitor from '../components/LiveMonitor';
import CargasFiltros from '../components/CargasFiltros';
import CargasKPIs from '../components/CargasKPIs';
import CargasTabela from '../components/CargasTabela';

const PAGE_SIZE_DEFAULT = 50;

function useDebouncedValue(value, delayMs) {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const handle = setTimeout(() => setDebounced(value), delayMs);
    return () => clearTimeout(handle);
  }, [value, delayMs]);
  return debounced;
}

export default function CargasDashboard() {
  const user = useStore((s) => s.user);
  const [isMonitorOpen, setIsMonitorOpen] = useState(false);

  // Dados da página atual da tabela (busca e paginação acontecem no servidor)
  const [tabelaRows, setTabelaRows] = useState([]);
  const [totalCargasFiltradas, setTotalCargasFiltradas] = useState(0);
  const [loadingTabela, setLoadingTabela] = useState(true);
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(PAGE_SIZE_DEFAULT);

  // KPIs e gráficos, calculados no backend sobre o conjunto filtrado inteiro
  const [resumo, setResumo] = useState({ total_cargas: 0, valor_total: 0, peso_total: 0, por_dia: [], por_mes: [] });

  // Opções para os dropdowns de filtro (valores distintos da tabela inteira)
  const [opcoes, setOpcoes] = useState({
    tipos_carga: [], dias_carregamento: [], dias_captura: [], rounds: [], fontes: [],
    meses_disponiveis: [], meses_captura_disponiveis: [],
  });

  const [scraperStatus, setScraperStatus] = useState({ is_running: false, status: 'Verificando...' });
  const [toast, setToast] = useState({ show: false, message: '' });

  // Filtros
  const [origemFilter, setOrigemFilter] = useState('');
  const [destinoFilter, setDestinoFilter] = useState('');
  const [tipoFilter, setTipoFilter] = useState([]);
  const [buscaGeral, setBuscaGeral] = useState('');
  const [diaCarregamentoFilter, setDiaCarregamentoFilter] = useState([]);
  const [diaCapturaFilter, setDiaCapturaFilter] = useState([]);
  const [mesCapturaFilter, setMesCapturaFilter] = useState([]);
  const [roundFilter, setRoundFilter] = useState([]);
  const [fonteFilter, setFonteFilter] = useState([]);
  const [mesFilter, setMesFilter] = useState([]);

  // Os campos de texto livre só disparam busca no servidor 300ms após o usuário parar de digitar
  const debouncedOrigem = useDebouncedValue(origemFilter, 300);
  const debouncedDestino = useDebouncedValue(destinoFilter, 300);
  const debouncedBusca = useDebouncedValue(buscaGeral, 300);

  const buildFilterParams = () => {
    const params = new URLSearchParams();
    if (debouncedOrigem) params.append('origem', debouncedOrigem);
    if (debouncedDestino) params.append('destino', debouncedDestino);
    if (debouncedBusca) params.append('busca', debouncedBusca);
    tipoFilter.forEach((v) => params.append('tipo_carga', v));
    fonteFilter.forEach((v) => params.append('fonte', v));
    mesFilter.forEach((v) => params.append('mes', v));
    diaCarregamentoFilter.forEach((v) => params.append('dia_carregamento', v));
    diaCapturaFilter.forEach((v) => params.append('dia_captura', v));
    mesCapturaFilter.forEach((v) => params.append('mes_captura', v));
    roundFilter.forEach((v) => params.append('round_hora', v));
    return params;
  };

  const filtersKey = JSON.stringify([
    debouncedOrigem, debouncedDestino, debouncedBusca,
    tipoFilter, fonteFilter, mesFilter, diaCarregamentoFilter, diaCapturaFilter, mesCapturaFilter, roundFilter,
  ]);

  const fetchCargasPage = async (targetPage) => {
    setLoadingTabela(true);
    try {
      const params = buildFilterParams();
      params.set('skip', targetPage * pageSize);
      params.set('limit', pageSize);
      const res = await api.get('/cargas', { params });
      const { items, total } = res.data;
      const maxPage = total > 0 ? Math.ceil(total / pageSize) - 1 : 0;
      if (targetPage > maxPage) {
        // Filtros/atualizações reduziram o total e a página atual ficou fora do intervalo
        setPage(maxPage);
        return;
      }
      setTabelaRows(items);
      setTotalCargasFiltradas(total);
    } catch (error) {
      console.error('Erro ao buscar cargas:', error);
    } finally {
      setLoadingTabela(false);
    }
  };

  const fetchResumo = async () => {
    try {
      const params = buildFilterParams();
      const res = await api.get('/cargas/resumo', { params });
      setResumo(res.data);
    } catch (error) {
      console.error('Erro ao buscar resumo de cargas:', error);
    }
  };

  const fetchOpcoes = async () => {
    try {
      const res = await api.get('/cargas/opcoes');
      setOpcoes(res.data);
    } catch (error) {
      console.error('Erro ao buscar opções de filtro:', error);
    }
  };

  // Sempre que os filtros mudam, volta para a primeira página (evitando buscar
  // a página antiga uma vez e a nova em seguida).
  const prevFiltersKeyRef = useRef(filtersKey);
  useEffect(() => {
    const changed = prevFiltersKeyRef.current !== filtersKey;
    prevFiltersKeyRef.current = filtersKey;
    if (changed && page !== 0) {
      setPage(0);
      return;
    }
    fetchCargasPage(page);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filtersKey, page, pageSize]);

  // KPIs e gráficos consideram o conjunto filtrado inteiro, não dependem da página
  useEffect(() => {
    fetchResumo();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filtersKey]);

  useEffect(() => {
    fetchOpcoes();
  }, []);

  const refreshAll = () => {
    fetchOpcoes();
    fetchResumo();
    fetchCargasPage(page);
  };

  useEffect(() => {
    const interval = setInterval(refreshAll, 15 * 60 * 1000); // 15 min refresh
    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filtersKey, page, pageSize]);

  // Polling do Status do Bot
  useEffect(() => {
    let lastIsRunning = null;

    const checkStatus = async () => {
      try {
        const res = await api.get('/scraper/monitor/status');
        const newState = res.data;
        setScraperStatus(newState);

        // Verifica se o bot acabou de ligar
        if (lastIsRunning === false && newState.is_running === true) {
          setToast({ show: true, message: '🤖 O Bot acabou de acordar e iniciou a extração!' });
          setTimeout(() => setToast({ show: false, message: '' }), 5000);
        }
        lastIsRunning = newState.is_running;
      } catch (error) {
        console.error('Erro ao verificar status do scraper:', error);
      }
    };

    checkStatus();
    const statusInterval = setInterval(checkStatus, 10 * 1000); // 10s polling
    return () => clearInterval(statusInterval);
  }, []);

  const handlePageSizeChange = (newSize) => {
    setPageSize(newSize);
    setPage(0);
  };

  const exportToCSV = async () => {
    let todasCargas = [];
    try {
      const params = buildFilterParams();
      params.set('skip', 0);
      params.set('limit', 100000);
      const res = await api.get('/cargas', { params });
      todasCargas = res.data.items;
    } catch (error) {
      console.error('Erro ao buscar cargas para exportação:', error);
      setToast({ show: true, message: 'Erro ao exportar CSV.' });
      setTimeout(() => setToast({ show: false, message: '' }), 3000);
      return;
    }

    if (todasCargas.length === 0) {
      setToast({ show: true, message: 'Nenhuma carga para exportar.' });
      setTimeout(() => setToast({ show: false, message: '' }), 3000);
      return;
    }

    const headers = ['Fonte', 'Load ID', 'Data Carregamento', 'Origem', 'Destino', 'Qtd', 'Tipo', 'Caminhão', 'Peso Total (KG)', 'Valor Total (R$)', 'Data Captura'];
    const csvRows = [headers.join(';')];

    todasCargas.forEach(carga => {
      const quantidade = carga.quantidade || 1;
      const pesoTotal = (Number(carga.peso_kg) || 0) * quantidade;

      const valorRaw = Number(carga.valor) || 0;
      let valorPorCaminhao = valorRaw;
      if (valorRaw > 0 && valorRaw < 1000 && Number(carga.peso_kg) > 0) {
        valorPorCaminhao = valorRaw * (Number(carga.peso_kg) / 1000);
      }
      const valorTotal = valorPorCaminhao * quantidade;

      const row = [
        carga.fonte || '',
        carga.load_id || '',
        carga.data_carregamento || '',
        carga.origem || '',
        carga.destino || '',
        quantidade,
        carga.tipo_carga || '',
        carga.tipo_caminhao || '',
        pesoTotal ? pesoTotal.toString().replace('.', ',') : '',
        valorTotal ? valorTotal.toFixed(2).replace('.', ',') : '',
        carga.data_captura ? new Date(carga.data_captura).toLocaleString('pt-BR') : ''
      ].map(field => {
        // Tratar ponto e vírgula e aspas duplas dentro dos campos
        const stringField = String(field);
        if (stringField.includes(';') || stringField.includes('"') || stringField.includes('\n')) {
          return `"${stringField.replace(/"/g, '""')}"`;
        }
        return stringField;
      });
      csvRows.push(row.join(';'));
    });

    const csvString = csvRows.join('\n');
    const blob = new Blob(['﻿' + csvString], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', `cargas_export_${new Date().toISOString().split('T')[0]}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);

    setToast({ show: true, message: '✅ Arquivo CSV gerado com sucesso!' });
    setTimeout(() => setToast({ show: false, message: '' }), 3000);
  };

  return (
    <div className="container" style={{ padding: '24px 0' }}>
      <LiveMonitor isOpen={isMonitorOpen} onClose={() => setIsMonitorOpen(false)} />
      <div className="page-header">
        <div>
          <h2>Painel Inteligente CARGO</h2>
          <div className="page-header-subtitle">Visão consolidada das cargas do Pool e Carga Prioritária</div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <div style={{
            display: 'flex', alignItems: 'center', gap: '8px',
            padding: '8px 16px', borderRadius: '999px',
            backgroundColor: scraperStatus.is_running ? '#dcfce7' : '#f3f4f6',
            color: scraperStatus.is_running ? '#166534' : '#4b5563',
            fontSize: '0.875rem', fontWeight: '600',
            border: `1px solid ${scraperStatus.is_running ? '#bbf7d0' : '#e5e7eb'}`,
            transition: 'all 0.3s ease'
          }}>
            <span style={{
              width: '8px', height: '8px', borderRadius: '50%',
              backgroundColor: scraperStatus.is_running ? '#22c55e' : '#9ca3af',
              boxShadow: scraperStatus.is_running ? '0 0 8px #22c55e' : 'none',
              flexShrink: 0
            }}></span>
            <span style={{
              maxWidth: '350px', whiteSpace: 'nowrap',
              overflow: 'hidden', textOverflow: 'ellipsis'
            }} title={scraperStatus.is_running ? scraperStatus.status : 'Bot Dormindo (Aguardando)'}>
              {scraperStatus.is_running ? scraperStatus.status : 'Bot Dormindo (Aguardando)'}
            </span>
          </div>

          {user?.role === 'admin' && (
            <button
              onClick={() => setIsMonitorOpen(true)}
              style={{
                display: 'flex', alignItems: 'center', gap: '8px',
                backgroundColor: '#dc2626', color: 'white', fontWeight: 500,
                padding: '8px 16px', borderRadius: '6px', cursor: 'pointer',
                border: '1px solid rgba(248,113,113,0.5)', boxShadow: '0 4px 6px -1px rgba(0,0,0,0.1)',
                transition: 'background-color 0.2s'
              }}
              onMouseOver={(e) => e.currentTarget.style.backgroundColor = '#ef4444'}
              onMouseOut={(e) => e.currentTarget.style.backgroundColor = '#dc2626'}
            >
              <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 20 20" fill="currentColor">
                <path d="M2 6a2 2 0 012-2h6a2 2 0 012 2v8a2 2 0 01-2 2H4a2 2 0 01-2-2V6zM14.553 7.106A1 1 0 0014 8v4a1 1 0 00.553.894l2 1A1 1 0 0018 13V7a1 1 0 00-1.447-.894l-2 1z" />
              </svg>
              Monitor Portal
            </button>
          )}

          <button className="btn btn-primary" onClick={refreshAll}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{marginRight: '8px'}}><path d="M21 2v6h-6"></path><path d="M3 12a9 9 0 0 1 15-6.7L21 8"></path><path d="M3 22v-6h6"></path><path d="M21 12a9 9 0 0 1-15 6.7L3 16"></path></svg>
            Atualizar Agora
          </button>
          <button className="btn" style={{ backgroundColor: '#10b981', color: 'white' }} onClick={exportToCSV}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{marginRight: '8px'}}><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg>
            Exportar CSV
          </button>
        </div>
      </div>

      <>
          <CargasKPIs
            totalCargas={resumo.total_cargas}
            valorTotal={resumo.valor_total}
          />

          <CargasFiltros
            origemFilter={origemFilter} setOrigemFilter={setOrigemFilter}
            destinoFilter={destinoFilter} setDestinoFilter={setDestinoFilter}
            tipoFilter={tipoFilter} setTipoFilter={setTipoFilter} tiposCarga={opcoes.tipos_carga}
            fonteFilter={fonteFilter} setFonteFilter={setFonteFilter}
            mesFilter={mesFilter} setMesFilter={setMesFilter} mesesDisponiveis={opcoes.meses_disponiveis}
            diaCarregamentoFilter={diaCarregamentoFilter} setDiaCarregamentoFilter={setDiaCarregamentoFilter} diasCarregamento={opcoes.dias_carregamento}
            diaCapturaFilter={diaCapturaFilter} setDiaCapturaFilter={setDiaCapturaFilter} diasCaptura={opcoes.dias_captura}
            mesCapturaFilter={mesCapturaFilter} setMesCapturaFilter={setMesCapturaFilter} mesesCapturaDisponiveis={opcoes.meses_captura_disponiveis}
            roundFilter={roundFilter} setRoundFilter={setRoundFilter} rounds={opcoes.rounds}
            buscaGeral={buscaGeral} setBuscaGeral={setBuscaGeral}
          />

          {/* Charts */}
          <div className="dashboard-grid" style={{ marginBottom: '32px' }}>
            <div className="card col-12">
              <div className="card-header">
                <h3 className="card-title">Cargas por Data de Carregamento</h3>
              </div>
              <div className="card-body" style={{ height: '380px' }}>
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={resumo.por_dia} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e5e7eb" />
                    <XAxis
                      dataKey="dia" axisLine={false} tickLine={false}
                      tick={{ fill: '#6b7280', fontSize: 11 }}
                      angle={-45} textAnchor="end" height={60}
                      interval="preserveStartEnd" minTickGap={14}
                      tickFormatter={(v) => (typeof v === 'string' && v.length >= 10 ? v.slice(0, 5) : v)}
                    />
                    <YAxis axisLine={false} tickLine={false} tick={{fill: '#6b7280'}} />
                    <Tooltip
                      contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)' }}
                      cursor={{fill: '#f3f4f6'}}
                    />
                    <Bar dataKey="quantidade" fill="var(--cargo-blue-500)" radius={[4, 4, 0, 0]} name="Cargas Disponíveis" />
                    <Brush dataKey="dia" height={24} stroke="var(--cargo-blue-500)" travellerWidth={8} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
            <div className="card col-12">
              <div className="card-header">
                <h3 className="card-title">Resumo por Mês</h3>
              </div>
              <div className="card-body" style={{ height: '260px' }}>
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={resumo.por_mes}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e5e7eb" />
                    <XAxis dataKey="mes" axisLine={false} tickLine={false} tick={{fill: '#6b7280'}} />
                    <YAxis axisLine={false} tickLine={false} tick={{fill: '#6b7280'}} />
                    <Tooltip
                      contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)' }}
                      cursor={{fill: '#f3f4f6'}}
                    />
                    <Bar dataKey="quantidade" fill="var(--cargo-blue-400)" radius={[4, 4, 0, 0]} name="Cargas Disponíveis" />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>

          <CargasTabela
            cargas={tabelaRows}
            loading={loadingTabela}
            page={page}
            pageSize={pageSize}
            total={totalCargasFiltradas}
            onPageChange={setPage}
            onPageSizeChange={handlePageSizeChange}
            onDeleted={refreshAll}
            onToast={(message) => {
              setToast({ show: true, message });
              setTimeout(() => setToast({ show: false, message: '' }), 3000);
            }}
          />
      </>

      {/* Toast Notification */}
      {toast.show && (
        <div style={{
          position: 'fixed',
          bottom: '32px',
          right: '32px',
          backgroundColor: '#1e293b',
          color: '#f8fafc',
          padding: '16px 24px',
          borderRadius: '12px',
          boxShadow: '0 10px 25px -5px rgba(0, 0, 0, 0.3)',
          display: 'flex',
          alignItems: 'center',
          gap: '12px',
          zIndex: 9999,
          animation: 'slideIn 0.3s ease-out forwards',
          fontWeight: '500'
        }}>
          {toast.message}
        </div>
      )}
    </div>
  );
}
