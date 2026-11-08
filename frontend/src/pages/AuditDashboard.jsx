import React, { useEffect, useState } from 'react';
import api from '../api/client';

export default function AuditDashboard() {
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  // Filters
  const [userFilter, setUserFilter] = useState('');
  const [actionFilter, setActionFilter] = useState('');
  const [dateFilter, setDateFilter] = useState('');

  const fetchLogs = async () => {
    try {
      const res = await api.get('/audit');
      setLogs(res.data);
    } catch (err) {
      if (err.response?.status === 403) {
        setError('Acesso negado. Apenas administradores podem ver os logs.');
      } else {
        setError('Erro ao carregar logs.');
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLogs();
  }, []);

  const filteredLogs = logs.filter(log => {
    const matchUser = userFilter === '' || (log.user_name && log.user_name.toLowerCase().includes(userFilter.toLowerCase()));
    const matchAction = actionFilter === '' || log.action.toLowerCase().includes(actionFilter.toLowerCase());
    const logDate = new Date(log.created_at).toLocaleDateString('pt-BR');
    const matchDate = dateFilter === '' || logDate === dateFilter;
    
    return matchUser && matchAction && matchDate;
  });

  const uniqueDates = [...new Set(logs.map(log => new Date(log.created_at).toLocaleDateString('pt-BR')))];
  const uniqueActions = [...new Set(logs.map(log => log.action))];

  return (
    <div className="dashboard animate-fade-in" style={{ paddingBottom: '40px' }}>
      <div className="card" style={{ marginBottom: '24px' }}>
        <div className="card-header">
          <h3 className="card-title">Trilha de Auditoria (Logs do Sistema)</h3>
        </div>
        <div className="card-body">
          {error ? (
            <div className="alert-error" style={{ padding: '16px', background: '#fee2e2', color: '#991b1b', borderRadius: '8px' }}>
              {error}
            </div>
          ) : (
            <>
              <div style={{ display: 'flex', gap: '16px', marginBottom: '24px', flexWrap: 'wrap' }}>
                <input 
                  type="text" 
                  className="form-control" 
                  placeholder="Filtrar por Usuário..." 
                  value={userFilter}
                  onChange={(e) => setUserFilter(e.target.value)}
                  style={{ flex: 1, minWidth: '200px' }}
                />
                <select 
                  className="form-control" 
                  value={actionFilter}
                  onChange={(e) => setActionFilter(e.target.value)}
                  style={{ flex: 1, minWidth: '200px' }}
                >
                  <option value="">Todas as Ações</option>
                  {uniqueActions.map(act => (
                    <option key={act} value={act}>{act}</option>
                  ))}
                </select>
                <select 
                  className="form-control" 
                  value={dateFilter}
                  onChange={(e) => setDateFilter(e.target.value)}
                  style={{ flex: 1, minWidth: '200px' }}
                >
                  <option value="">Qualquer Data</option>
                  {uniqueDates.map(d => (
                    <option key={d} value={d}>{d}</option>
                  ))}
                </select>
              </div>

              {loading ? (
                <div style={{ padding: '40px', textAlign: 'center' }}>Carregando logs...</div>
              ) : (
                <div className="table-container" style={{ maxHeight: '600px', overflowY: 'auto' }}>
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>Data / Hora</th>
                        <th>Usuário</th>
                        <th>Ação</th>
                        <th>Alvo</th>
                        <th>Detalhes</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredLogs.map(log => (
                        <tr key={log.id}>
                          <td style={{ whiteSpace: 'nowrap' }}>
                            {new Date(log.created_at).toLocaleString('pt-BR')}
                          </td>
                          <td style={{ fontWeight: 600 }}>{log.user_name || 'Sistema'}</td>
                          <td>
                            <span className="badge badge-ok" style={{ background: 'var(--cargo-blue-100)', color: 'var(--cargo-blue-700)' }}>
                              {log.action}
                            </span>
                          </td>
                          <td>{log.target_type || '-'}</td>
                          <td>{log.details || '-'}</td>
                        </tr>
                      ))}
                      {filteredLogs.length === 0 && (
                        <tr>
                          <td colSpan="5" style={{ textAlign: 'center', padding: '24px' }}>Nenhum log encontrado.</td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
