import React, { useEffect, useState } from 'react';
import api from '../api/client';
import InsightsModal from '../components/InsightsModal';

function formatDateTime(value) {
  if (!value) return '--';
  return new Date(value).toLocaleString('pt-BR');
}

function ItensTable({ itens }) {
  if (itens.length === 0) {
    return <p style={{ opacity: 0.7 }}>Nenhuma carga (Lata) neste relatório.</p>;
  }
  return (
    <div className="table-container">
      <table className="data-table">
        <thead>
          <tr>
            <th>Pedido de insumos</th>
            <th>Carga</th>
            <th>Origem</th>
            <th>Destino</th>
            <th>Data carregamento</th>
            <th>Status SmartCargas</th>
            <th>Reprogramação</th>
          </tr>
        </thead>
        <tbody>
          {itens.map((item) => (
            <tr key={item.id}>
              <td>{item.pedido_insumos}</td>
              <td>{item.carga_tms || '--'}</td>
              <td>{item.origem || '--'}</td>
              <td>{item.destino || '--'}</td>
              <td>{item.data_carregamento || '--'}</td>
              <td>{item.status_smartcargas || '--'}</td>
              <td>{item.reprogramacao || '--'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function DiffTable({ titulo, itens, vazio }) {
  return (
    <div className="card" style={{ marginBottom: 16 }}>
      <div className="card-header">
        <h3>{titulo} ({itens.length})</h3>
      </div>
      <div className="card-body">
        {itens.length === 0 ? (
          <p style={{ opacity: 0.7 }}>{vazio}</p>
        ) : (
          <div className="table-container">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Pedido de insumos</th>
                  <th>Origem</th>
                  <th>Destino</th>
                  <th>Data carregamento</th>
                  <th>Status anterior</th>
                  <th>Status atual</th>
                  <th>Vai para o ERP?</th>
                </tr>
              </thead>
              <tbody>
                {itens.map((item) => (
                  <tr key={item.id}>
                    <td>{item.pedido_insumos}</td>
                    <td>{item.origem || '--'}</td>
                    <td>{item.destino || '--'}</td>
                    <td>{item.data_carregamento || '--'}</td>
                    <td>{item.status_anterior || '--'}</td>
                    <td>{item.status_atual || '--'}</td>
                    <td>
                      <span className={`badge ${item.elegivel_erp ? 'badge-ok' : 'badge-nok'}`}>
                        {item.elegivel_erp ? 'Sim' : 'Não'}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

export default function RelatoriosCargas() {
  const [capturas, setCapturas] = useState([]);
  const [loadingLista, setLoadingLista] = useState(true);
  const [capturando, setCapturando] = useState(false);
  const [statusCaptura, setStatusCaptura] = useState('');
  const [erro, setErro] = useState('');
  const [selecionada, setSelecionada] = useState(null);
  const [detalhe, setDetalhe] = useState(null);
  const [loadingDetalhe, setLoadingDetalhe] = useState(false);
  const [comparacao, setComparacao] = useState(null);
  const [loadingComparacao, setLoadingComparacao] = useState(false);
  const [aba, setAba] = useState('itens');
  const [mostrarInsights, setMostrarInsights] = useState(false);
  const [pagina, setPagina] = useState(1);
  const [porPagina, setPorPagina] = useState(10);
  const [marcadas, setMarcadas] = useState(new Set());
  const [exportando, setExportando] = useState(false);

  const totalPaginas = Math.max(1, Math.ceil(capturas.length / porPagina));
  const inicio = (pagina - 1) * porPagina;
  const capturasPagina = capturas.slice(inicio, inicio + porPagina);
  const todasMarcadas = capturas.length > 0 && marcadas.size === capturas.length;
  const paginaMarcada = capturasPagina.length > 0 && capturasPagina.every((c) => marcadas.has(c.id));

  const alternar = (id) => setMarcadas((prev) => {
    const n = new Set(prev);
    if (n.has(id)) n.delete(id); else n.add(id);
    return n;
  });
  const alternarPagina = () => setMarcadas((prev) => {
    const n = new Set(prev);
    capturasPagina.forEach((c) => (paginaMarcada ? n.delete(c.id) : n.add(c.id)));
    return n;
  });
  const alternarTodas = () => setMarcadas(todasMarcadas ? new Set() : new Set(capturas.map((c) => c.id)));

  const exportarCsv = async () => {
    setExportando(true);
    try {
      const res = await api.get('/relatorios-carga/exportar', {
        params: { ids: Array.from(marcadas).join(',') },
        responseType: 'blob',
      });
      const url = URL.createObjectURL(res.data);
      const a = document.createElement('a');
      a.href = url;
      a.download = marcadas.size === 1 ? 'relatorio.csv' : `relatorios_${marcadas.size}_capturas.csv`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setErro('Erro ao exportar o CSV.');
    } finally {
      setExportando(false);
    }
  };

  const carregarCapturas = async () => {
    setLoadingLista(true);
    try {
      const res = await api.get('/relatorios-carga');
      setCapturas(res.data.items);
      setMarcadas(new Set());
    } catch (e) {
      console.error('Erro ao carregar histórico de relatórios', e);
    } finally {
      setLoadingLista(false);
    }
  };

  useEffect(() => {
    carregarCapturas();
  }, []);

  const handleCapturar = async () => {
    setErro('');
    setCapturando(true);
    setStatusCaptura('Iniciando captura do relatório...');
    try {
      await api.post('/scraper/monitor/run-report');
    } catch (e) {
      setCapturando(false);
      setErro(e.response?.data?.message || 'Erro ao iniciar a captura do relatório.');
      return;
    }

    const intervalId = setInterval(async () => {
      try {
        const res = await api.get('/scraper/monitor/status');
        setStatusCaptura(res.data.status || '');
        if (!res.data.is_running) {
          clearInterval(intervalId);
          setCapturando(false);
          carregarCapturas();
        }
      } catch (e) {
        clearInterval(intervalId);
        setCapturando(false);
      }
    }, 2000);
  };

  const handleSelecionar = async (captura) => {
    setSelecionada(captura);
    setAba('itens');
    setDetalhe(null);
    setComparacao(null);

    setLoadingDetalhe(true);
    api.get(`/relatorios-carga/${captura.id}`)
      .then((res) => setDetalhe(res.data))
      .catch((e) => console.error('Erro ao carregar detalhe do relatório', e))
      .finally(() => setLoadingDetalhe(false));

    setLoadingComparacao(true);
    api.get(`/relatorios-carga/${captura.id}/comparacao`)
      .then((res) => setComparacao(res.data))
      .catch((e) => console.error('Erro ao carregar comparação', e))
      .finally(() => setLoadingComparacao(false));
  };

  return (
    <div>
      {mostrarInsights && <InsightsModal onClose={() => setMostrarInsights(false)} />}
      <div className="card" style={{ marginBottom: 16 }}>
        <div className="card-header">
          <h3>Captura de Relatórios de Cargas</h3>
        </div>
        <div className="card-body">
          <p style={{ marginBottom: 12 }}>
            Baixa o relatório de cargas do Portal (janela de hoje até os próximos 5 dias), guarda
            um histórico e compara com a última captura do mesmo dia para identificar cargas novas,
            que sumiram ou que mudaram de status. Só as latas confirmadas explicitamente seguem
            elegíveis para o ERP.
          </p>
          <button className="btn btn-primary" onClick={handleCapturar} disabled={capturando}>
            {capturando ? 'Capturando...' : 'Capturar Relatório'}
          </button>
          <button className="btn btn-primary" style={{ marginLeft: 8 }} onClick={() => setMostrarInsights(true)}>
            Insights
          </button>
          {capturando && <span style={{ marginLeft: 12, opacity: 0.8 }}>{statusCaptura}</span>}
          {erro && <p style={{ color: '#ef4444', marginTop: 8 }}>{erro}</p>}
        </div>
      </div>

      <div className="card" style={{ marginBottom: 16 }}>
        <div className="card-header">
          <h3>Histórico de Capturas</h3>
        </div>
        <div className="card-body">
          {capturas.length > 0 && (
            <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap', marginBottom: 12 }}>
              <span style={{ opacity: 0.8 }}>{marcadas.size} de {capturas.length} marcado(s)</span>
              <button className="btn btn-outline btn-sm" onClick={alternarTodas}>
                {todasMarcadas ? 'Desmarcar todos' : 'Selecionar todos'}
              </button>
              <button className="btn btn-primary btn-sm" onClick={exportarCsv} disabled={marcadas.size === 0 || exportando}>
                {exportando ? 'Exportando...' : 'Exportar CSV'}
              </button>
            </div>
          )}
          {loadingLista ? (
            <p>Carregando...</p>
          ) : capturas.length === 0 ? (
            <p style={{ opacity: 0.7 }}>Nenhum relatório capturado ainda.</p>
          ) : (
            <div className="table-container">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>
                      <input type="checkbox" checked={paginaMarcada} onChange={alternarPagina} title="Marcar página" />
                    </th>
                    <th>Dia da captura</th>
                    <th>Capturado em</th>
                    <th>Origem</th>
                    <th>Itens (Lata)</th>
                    <th>Status</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {capturasPagina.map((c) => (
                    <tr
                      key={c.id}
                      className={selecionada?.id === c.id ? 'just-updated' : ''}
                      style={{ cursor: 'pointer' }}
                      onClick={() => handleSelecionar(c)}
                    >
                      <td onClick={(e) => e.stopPropagation()}>
                        <input type="checkbox" checked={marcadas.has(c.id)} onChange={() => alternar(c.id)} />
                      </td>
                      <td>{c.data_referencia}</td>
                      <td>{formatDateTime(c.capturado_em)}</td>
                      <td>{c.origem_captura === 'manual' ? 'Manual' : 'Agendado'}</td>
                      <td>{c.total_itens_lata}</td>
                      <td>
                        <span className={`badge ${c.status === 'sucesso' ? 'badge-ok' : 'badge-nok'}`}>
                          {c.status}
                        </span>
                      </td>
                      <td>
                        <button className="btn btn-outline btn-sm" onClick={(e) => { e.stopPropagation(); handleSelecionar(c); }}>
                          Ver relatório
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {capturas.length > 0 && (
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12, flexWrap: 'wrap', marginTop: 12 }}>
              <span style={{ opacity: 0.8 }}>
                {inicio + 1}–{Math.min(inicio + porPagina, capturas.length)} de {capturas.length}
                <select
                  value={porPagina}
                  onChange={(e) => { setPorPagina(Number(e.target.value)); setPagina(1); }}
                  className="form-input" style={{ marginLeft: 12, width: 'auto', padding: '6px 10px', fontSize: '0.8rem' }}
                >
                  {[10, 25, 50, 100].map((n) => <option key={n} value={n}>{n} por página</option>)}
                </select>
              </span>
              <span style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                <button className="btn btn-outline btn-sm" onClick={() => setPagina(1)} disabled={pagina === 1}>«</button>
                <button className="btn btn-outline btn-sm" onClick={() => setPagina((p) => Math.max(1, p - 1))} disabled={pagina === 1}>Anterior</button>
                <span>Página {pagina} de {totalPaginas}</span>
                <button className="btn btn-outline btn-sm" onClick={() => setPagina((p) => Math.min(totalPaginas, p + 1))} disabled={pagina === totalPaginas}>Próxima</button>
                <button className="btn btn-outline btn-sm" onClick={() => setPagina(totalPaginas)} disabled={pagina === totalPaginas}>»</button>
              </span>
            </div>
          )}
        </div>
      </div>

      {selecionada && (
        <div>
          <h3 style={{ marginBottom: 12 }}>
            Relatório capturado em {formatDateTime(selecionada.capturado_em)}
          </h3>

          <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
            <button
              className={`btn btn-sm ${aba === 'itens' ? 'btn-primary' : 'btn-outline'}`}
              onClick={() => setAba('itens')}
            >
              Cargas do relatório ({selecionada.total_itens_lata})
            </button>
            <button
              className={`btn btn-sm ${aba === 'comparacao' ? 'btn-primary' : 'btn-outline'}`}
              onClick={() => setAba('comparacao')}
            >
              Comparação com captura anterior
            </button>
          </div>

          {aba === 'itens' && (
            <div className="card" style={{ marginBottom: 16 }}>
              <div className="card-body">
                {loadingDetalhe ? (
                  <p>Carregando cargas do relatório...</p>
                ) : !detalhe ? (
                  <p>Não foi possível carregar o relatório.</p>
                ) : (
                  <ItensTable itens={detalhe.itens} />
                )}
              </div>
            </div>
          )}

          {aba === 'comparacao' && (
            loadingComparacao ? (
              <p>Carregando comparação...</p>
            ) : !comparacao ? (
              <p>Não foi possível carregar a comparação.</p>
            ) : !comparacao.relatorio_anterior_id ? (
              <p style={{ opacity: 0.7 }}>
                Esta é a primeira captura do dia — ainda não há uma captura anterior para comparar.
              </p>
            ) : (
              <>
                <DiffTable
                  titulo="Novas cargas"
                  itens={comparacao.novos}
                  vazio="Nenhuma carga nova em relação à captura anterior."
                />
                <DiffTable
                  titulo="Sumiram (revisar antes de confirmar cancelamento)"
                  itens={comparacao.sumidos}
                  vazio="Nenhuma carga sumiu em relação à captura anterior."
                />
                <DiffTable
                  titulo="Mudaram de status"
                  itens={comparacao.status_alterado}
                  vazio="Nenhuma mudança de status em relação à captura anterior."
                />
              </>
            )
          )}
        </div>
      )}
    </div>
  );
}
