import React, { useEffect, useState } from 'react';
import api from '../api/client';

function formatUltimaVisualizacao(carga) {
  if (carga.fonte !== 'Pool de Cargas' || !carga.ultima_visualizacao || !carga.data_captura) return null;
  const diffTime = new Date(carga.ultima_visualizacao) - new Date(carga.data_captura);
  const diffDays = Math.floor(diffTime / (1000 * 60 * 60 * 24));
  const diffHours = Math.floor((diffTime / (1000 * 60 * 60)) % 24);
  if (diffDays <= 0 && diffHours <= 0) return null;
  return (
    <div style={{ marginTop: '4px' }}>
      <span style={{ backgroundColor: '#fef3c7', color: '#b45309', padding: '2px 6px', borderRadius: '4px', fontSize: '0.7rem', fontWeight: 'bold' }} title={`Vista primeiro: ${new Date(carga.data_captura).toLocaleString()}`}>
        ⏳ No Pool há {diffDays > 0 ? `${diffDays}d ` : ''}{diffHours}h
      </span>
    </div>
  );
}

const PAGE_SIZE_OPTIONS = [25, 50, 100, 200];

function Paginacao({ page, pageSize, total, onPageChange, onPageSizeChange }) {
  const totalPages = total > 0 ? Math.ceil(total / pageSize) : 1;
  const inicio = total === 0 ? 0 : page * pageSize + 1;
  const fim = Math.min((page + 1) * pageSize, total);

  return (
    <div style={{
      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      flexWrap: 'wrap', gap: '12px', padding: '12px 16px', borderTop: '1px solid #e5e7eb',
    }}>
      <div style={{ fontSize: '0.8125rem', color: '#6b7280' }}>
        {total === 0 ? 'Nenhuma carga encontrada' : `Mostrando ${inicio}–${fim} de ${total} cargas`}
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
        <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.8125rem', color: '#4b5563' }}>
          Por página:
          <select
            className="form-input"
            style={{ padding: '4px 8px', width: 'auto' }}
            value={pageSize}
            onChange={(e) => onPageSizeChange(Number(e.target.value))}
          >
            {PAGE_SIZE_OPTIONS.map((size) => (
              <option key={size} value={size}>{size}</option>
            ))}
          </select>
        </label>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <button
            className="btn"
            style={{ backgroundColor: '#e5e7eb', color: '#4b5563', padding: '4px 12px' }}
            onClick={() => onPageChange(0)}
            disabled={page === 0}
          >
            «
          </button>
          <button
            className="btn"
            style={{ backgroundColor: '#e5e7eb', color: '#4b5563', padding: '4px 12px' }}
            onClick={() => onPageChange(Math.max(0, page - 1))}
            disabled={page === 0}
          >
            Anterior
          </button>
          <span style={{ fontSize: '0.8125rem', color: '#4b5563', whiteSpace: 'nowrap' }}>
            Página {page + 1} de {totalPages}
          </span>
          <button
            className="btn"
            style={{ backgroundColor: '#e5e7eb', color: '#4b5563', padding: '4px 12px' }}
            onClick={() => onPageChange(Math.min(totalPages - 1, page + 1))}
            disabled={page >= totalPages - 1}
          >
            Próxima
          </button>
          <button
            className="btn"
            style={{ backgroundColor: '#e5e7eb', color: '#4b5563', padding: '4px 12px' }}
            onClick={() => onPageChange(totalPages - 1)}
            disabled={page >= totalPages - 1}
          >
            »
          </button>
        </div>
      </div>
    </div>
  );
}

function ExcluirCargaModal({ alvo, onClose, onConfirm }) {
  const [motivo, setMotivo] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    setMotivo('');
    setError('');
    setSubmitting(false);
  }, [alvo]);

  if (!alvo) return null;

  const isBulk = alvo.type === 'bulk';
  const count = isBulk ? alvo.ids.length : 1;
  const motivoValido = motivo.trim().length >= 3;

  const handleConfirm = async () => {
    if (!motivoValido || submitting) return;
    setSubmitting(true);
    setError('');
    try {
      await onConfirm(motivo.trim());
    } catch (err) {
      setError(err.response?.data?.detail || 'Erro ao excluir. Tente novamente.');
      setSubmitting(false);
    }
  };

  return (
    <div className="modal-overlay" style={{ zIndex: 9999, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <div className="modal-content" style={{ maxWidth: '480px', width: '90%' }}>
        <h3 style={{ marginBottom: '12px', color: 'var(--cargo-blue-800)' }}>
          Tem certeza que deseja excluir {isBulk ? `${count} cargas` : 'esta carga'}?
        </h3>
        {!isBulk && (
          <div style={{ fontSize: '0.875rem', color: '#4b5563', marginBottom: '16px', background: '#f9fafb', padding: '10px 12px', borderRadius: '6px' }}>
            <strong>{alvo.carga.origem} → {alvo.carga.destino}</strong>
            {alvo.carga.load_id && <span> · Load ID: {alvo.carga.load_id}</span>}
          </div>
        )}
        <p style={{ fontSize: '0.8125rem', color: '#6b7280', marginBottom: '8px' }}>
          Isso remove {isBulk ? 'as cargas' : 'a carga'} do banco de dados e de todos os dashboards. Não pode ser desfeito pela interface.
        </p>
        <label style={{ display: 'block', fontSize: '0.875rem', fontWeight: 600, color: '#374151', marginBottom: '6px' }}>
          Justificativa (obrigatória)
        </label>
        <textarea
          className="form-input"
          rows={3}
          style={{ width: '100%', resize: 'vertical', marginBottom: '8px', fontFamily: 'inherit' }}
          placeholder="Explique o motivo da exclusão..."
          value={motivo}
          onChange={(e) => setMotivo(e.target.value)}
          autoFocus
        />
        {error && <div style={{ color: '#dc2626', fontSize: '0.8125rem', marginBottom: '8px' }}>{error}</div>}
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px', marginTop: '16px' }}>
          <button className="btn" style={{ backgroundColor: '#e5e7eb', color: '#4b5563' }} onClick={onClose} disabled={submitting}>
            Não
          </button>
          <button
            className="btn"
            style={{ backgroundColor: '#dc2626', color: 'white', opacity: motivoValido ? 1 : 0.5 }}
            onClick={handleConfirm}
            disabled={!motivoValido || submitting}
          >
            {submitting ? 'Excluindo...' : 'Sim, excluir'}
          </button>
        </div>
      </div>
    </div>
  );
}

export default function CargasTabela({ cargas, loading, page, pageSize, total, onPageChange, onPageSizeChange, onDeleted, onToast }) {
  const [selectedIds, setSelectedIds] = useState(new Set());
  const [alvoExclusao, setAlvoExclusao] = useState(null);

  // A seleção não persiste entre páginas/filtros para evitar excluir por engano
  // uma carga que já saiu de vista.
  useEffect(() => {
    setSelectedIds(new Set());
  }, [cargas]);

  const toggleSelected = (id) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  };

  const handleConfirmDelete = async (motivo) => {
    if (alvoExclusao.type === 'single') {
      await api.delete(`/cargas/${alvoExclusao.carga.id}`, { data: { motivo } });
      onToast?.('Carga excluída com sucesso.');
    } else {
      const ids = Array.from(alvoExclusao.ids);
      await api.post('/cargas/bulk-delete', { ids, motivo });
      onToast?.(`${ids.length} carga(s) excluída(s) com sucesso.`);
      setSelectedIds(new Set());
    }
    setAlvoExclusao(null);
    onDeleted?.();
  };

  return (
    <div className="card">
      <div className="card-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '12px' }}>
        <h3 className="card-title">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="8" y1="6" x2="21" y2="6"></line><line x1="8" y1="12" x2="21" y2="12"></line><line x1="8" y1="18" x2="21" y2="18"></line><line x1="3" y1="6" x2="3.01" y2="6"></line><line x1="3" y1="12" x2="3.01" y2="12"></line><line x1="3" y1="18" x2="3.01" y2="18"></line></svg>
          Listagem de Cargas
        </h3>
        {selectedIds.size > 0 && (
          <button
            className="btn"
            style={{ backgroundColor: '#dc2626', color: 'white', display: 'flex', alignItems: 'center', gap: '6px' }}
            onClick={() => setAlvoExclusao({ type: 'bulk', ids: selectedIds })}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
            Excluir selecionadas ({selectedIds.size})
          </button>
        )}
      </div>
      <div className="table-container" style={{ maxHeight: '500px', overflowY: 'auto' }}>
        <table className="data-table">
          <thead style={{ position: 'sticky', top: 0, zIndex: 10, backgroundColor: 'white' }}>
            <tr>
              <th style={{ padding: '12px 8px', width: '32px' }}></th>
              <th style={{ padding: '12px 16px', fontWeight: '500', color: '#4b5563' }}>Fonte</th>
              <th style={{ padding: '12px 16px', fontWeight: '500', color: '#4b5563' }}>Load ID</th>
              <th style={{ padding: '12px 16px', fontWeight: '500', color: '#4b5563' }}>Data Carregamento</th>
              <th style={{ padding: '12px 16px', fontWeight: '500', color: '#4b5563' }}>Data Absorção</th>
              <th style={{ padding: '12px 16px', fontWeight: '500', color: '#4b5563' }}>Origem</th>
              <th style={{ padding: '12px 16px', fontWeight: '500', color: '#4b5563' }}>Destino</th>
              <th style={{ padding: '12px 16px', fontWeight: '500', color: '#4b5563', textAlign: 'center' }}>Qtd</th>
              <th style={{ padding: '12px 16px', fontWeight: '500', color: '#4b5563' }}>Tipo/Caminhão</th>
              <th style={{ padding: '12px 16px', fontWeight: '500', color: '#4b5563', textAlign: 'right' }}>Valor Total</th>
              <th style={{ padding: '12px 16px', fontWeight: '500', color: '#4b5563', textAlign: 'center' }}>Ações</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan="12" style={{ textAlign: 'center', padding: '24px' }}>Carregando dados do servidor...</td></tr>
            ) : cargas.length === 0 ? (
              <tr><td colSpan="12" style={{ textAlign: 'center', padding: '24px' }}>Nenhuma carga encontrada.</td></tr>
            ) : (
              cargas.map((carga, idx) => (
                <tr key={carga.id || idx} style={{ borderBottom: '1px solid #e5e7eb', transition: 'background-color 0.2s' }}>
                  <td style={{ padding: '12px 8px', textAlign: 'center' }}>
                    <input
                      type="checkbox"
                      checked={selectedIds.has(carga.id)}
                      onChange={() => toggleSelected(carga.id)}
                      style={{ cursor: 'pointer' }}
                    />
                  </td>
                  <td style={{ padding: '12px 16px' }}>
                    <span style={{
                      backgroundColor: carga.fonte === 'Pool de Cargas' ? '#fdf2f8' : '#FFF7ED',
                      color: carga.fonte === 'Pool de Cargas' ? '#be185d' : '#C2410C',
                      padding: '2px 8px', borderRadius: '12px', fontSize: '0.75rem', fontWeight: 'bold'
                    }}>
                      {carga.fonte || 'Desconhecida'}
                    </span>
                  </td>
                  <td style={{ padding: '12px 16px', fontWeight: 'bold', color: '#374151' }}>{carga.load_id || '-'}</td>
                  <td style={{ padding: '12px 16px', fontWeight: '500' }}>
                    {carga.data_carregamento}
                    {formatUltimaVisualizacao(carga)}
                  </td>
                  <td style={{ padding: '12px 16px', fontSize: '0.875rem', color: '#4b5563' }}>
                    {carga.data_captura ? new Date(carga.data_captura).toLocaleDateString('pt-BR') : '-'}
                  </td>
                  <td style={{ padding: '12px 16px' }}>
                    <div style={{ fontSize: '0.875rem' }}>{carga.origem}</div>
                  </td>
                  <td style={{ padding: '12px 16px' }}>
                    <div style={{ fontSize: '0.875rem' }}>{carga.destino}</div>
                  </td>
                  <td style={{ padding: '12px 16px', textAlign: 'center', fontWeight: 'bold' }}>
                    <span style={{ backgroundColor: 'var(--cargo-blue-100)', color: 'var(--cargo-blue-700)', padding: '2px 8px', borderRadius: '12px' }}>
                      {carga.quantidade || 1}x
                    </span>
                  </td>
                  <td style={{ padding: '12px 16px' }}>
                    <div style={{ fontSize: '0.875rem' }}>{carga.tipo_carga}</div>
                    <div style={{ fontSize: '0.75rem', color: '#6b7280' }}>{carga.tipo_caminhao}</div>
                    {carga.tags && (
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px', marginTop: '4px' }}>
                        {carga.tags.split(',').map(tag => tag.trim()).filter(Boolean).map((tag, i) => (
                          <span key={i} style={{ backgroundColor: '#f3f4f6', color: '#4b5563', padding: '2px 6px', borderRadius: '4px', fontSize: '0.7rem' }}>
                            {tag}
                          </span>
                        ))}
                      </div>
                    )}
                  </td>
                  <td style={{ padding: '12px 16px', textAlign: 'right' }}>
                    {carga.valor ? (
                      <span style={{ backgroundColor: '#dcfce7', color: '#166534', padding: '4px 8px', borderRadius: '4px', fontSize: '0.875rem', fontWeight: 'bold' }}>
                        {(() => {
                          const valorRaw = Number(carga.valor) || 0;
                          const pesoKg = Number(carga.peso_kg) || 0;
                          let valorTotalCaminhao = valorRaw;
                          if (valorRaw > 0 && valorRaw < 1000 && pesoKg > 0) {
                            valorTotalCaminhao = valorRaw * (pesoKg / 1000);
                          }
                          const valorFinal = valorTotalCaminhao * (carga.quantidade || 1);
                          return new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(valorFinal);
                        })()}
                      </span>
                    ) : (
                      <span style={{ backgroundColor: '#f3f4f6', color: '#6b7280', padding: '4px 8px', borderRadius: '4px', fontSize: '0.875rem' }}>N/A</span>
                    )}
                  </td>
                  <td style={{ padding: '12px 16px', textAlign: 'center' }}>
                    <button
                      title="Excluir carga"
                      onClick={() => setAlvoExclusao({ type: 'single', carga })}
                      style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#dc2626', padding: '4px', display: 'inline-flex' }}
                    >
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path><line x1="10" y1="11" x2="10" y2="17"></line><line x1="14" y1="11" x2="14" y2="17"></line></svg>
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
      <Paginacao
        page={page}
        pageSize={pageSize}
        total={total}
        onPageChange={onPageChange}
        onPageSizeChange={onPageSizeChange}
      />
      <ExcluirCargaModal
        alvo={alvoExclusao}
        onClose={() => setAlvoExclusao(null)}
        onConfirm={handleConfirmDelete}
      />
    </div>
  );
}
