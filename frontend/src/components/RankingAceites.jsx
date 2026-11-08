import React, { useEffect, useState } from 'react';
import api from '../api/client';

const PERIODOS = [
  { dias: 1, label: 'Hoje' },
  { dias: 3, label: 'Últimos 3 dias' },
  { dias: 7, label: 'Últimos 7 dias' },
  { dias: 15, label: 'Últimos 15 dias' },
];

const fmtRound = (s) => {
  const [dia, hora] = s.split(' ');
  return `${dia.split('-').reverse().slice(0, 2).join('/')} ${hora}`;
};

const Kpi = ({ valor, rotulo, cor, sub }) => (
  <div style={{ flex: '1 1 160px', borderLeft: `4px solid ${cor}`, padding: '8px 14px' }}>
    <div style={{ fontSize: '1.6rem', fontWeight: 700 }}>{valor}</div>
    <div style={{ fontSize: '0.85rem' }}>{rotulo}</div>
    {sub && <div style={{ fontSize: '0.75rem', opacity: 0.7 }}>{sub}</div>}
  </div>
);

export default function RankingAceites() {
  const [dias, setDias] = useState(3);
  const [dados, setDados] = useState(null);
  const [erro, setErro] = useState('');
  const [msg, setMsg] = useState('');

  const carregar = () => {
    setErro('');
    api.get('/estatisticas/ranking', { params: { dias } })
      .then((res) => setDados(res.data))
      .catch(() => setErro('Não foi possível carregar o comparativo com os rankings.'));
  };

  useEffect(carregar, [dias]);

  const lerAgora = async () => {
    setMsg('Iniciando leitura...');
    try {
      const res = await api.post('/estatisticas/ranking/ler-agora');
      if (!res.data.ok) { setMsg(res.data.status); return; }
    } catch {
      setMsg('Não foi possível iniciar a leitura.');
      return;
    }
    const timer = setInterval(async () => {
      try {
        const { data } = await api.get('/estatisticas/ranking/status');
        setMsg(data.status);
        if (!data.is_running) { clearInterval(timer); carregar(); }
      } catch { clearInterval(timer); }
    }, 5000);
  };

  const t = dados?.totais;
  const pct = t && t.aceitas ? Math.round((100 * t.no_ranking) / t.aceitas) : null;

  return (
    <div className="card">
      <div className="card-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 8 }}>
        <h3 className="card-title">Aceites x Rankings de confirmação</h3>
        <div style={{ display: 'flex', gap: 8 }}>
          <button className="btn btn-outline" onClick={lerAgora}>Ler rankings agora</button>
          <select value={dias} onChange={(e) => setDias(Number(e.target.value))}>
            {PERIODOS.map((p) => <option key={p.dias} value={p.dias}>{p.label}</option>)}
          </select>
        </div>
      </div>
      <div className="card-body">
        <p style={{ fontSize: '0.85rem', opacity: 0.7, marginTop: 0 }}>
          A cada início de hora o scraper lê o 1º, 2º e 3º lugar do Smart Cargas e compara com o que foi aceito
          no round anterior (passes das :40 e :55): mostra se a carga foi para o ranking e em qual posição.
        </p>
        {msg && <p style={{ fontSize: '0.85rem' }}>{msg}</p>}
        {erro && <p style={{ color: '#ef4444' }}>{erro}</p>}
        {!dados && !erro && <p>Carregando...</p>}
        {dados && (
          <>
            <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', marginBottom: 24 }}>
              <Kpi valor={t.aceitas} rotulo="Aceitas nos rounds lidos" cor="var(--cargo-warning)" />
              <Kpi valor={t.no_ranking} rotulo="Foram para o ranking" cor="var(--cargo-success)"
                sub={`${pct == null ? '—' : pct + '%'} · 1º: ${dados.por_posicao[1]} · 2º: ${dados.por_posicao[2]} · 3º: ${dados.por_posicao[3]}`} />
              <Kpi valor={t.fora} rotulo="Fora do ranking" cor="#ef4444" />
              <Kpi valor={t.sem_aceite_nosso} rotulo="No ranking sem aceite nosso" cor="var(--cargo-primary, #C2410C)" sub="não bateram com nenhum aceite detectado" />
            </div>

            {dados.rounds.length === 0 && <p>Nenhuma leitura de ranking no período ainda.</p>}
            {dados.rounds.map((r) => (
              <div key={r.round} style={{ marginBottom: 20 }}>
                <h4 style={{ margin: '0 0 6px' }}>Round {fmtRound(r.round)}</h4>
                <div style={{ overflowX: 'auto' }}>
                  <table className="data-table" style={{ width: '100%' }}>
                    <thead>
                      <tr>
                        <th style={{ textAlign: 'left', padding: '8px 12px' }}>Carga</th>
                        <th style={{ textAlign: 'left' }}>Rota</th>
                        <th style={{ textAlign: 'center' }}>Resultado</th>
                      </tr>
                    </thead>
                    <tbody>
                      {r.aceitas.map((a, i) => (
                        <tr key={`a${i}`}>
                          <td style={{ padding: '6px 12px' }}>{a.load_id || '—'}</td>
                          <td>{a.origem} → {a.destino}</td>
                          <td style={{ textAlign: 'center', color: a.posicao ? 'var(--cargo-success)' : '#ef4444', fontWeight: 600 }}>
                            {a.posicao ? `${a.posicao}º lugar` : 'Fora do ranking'}
                          </td>
                        </tr>
                      ))}
                      {r.sem_aceite_nosso.map((a, i) => (
                        <tr key={`s${i}`} style={{ opacity: 0.8 }}>
                          <td style={{ padding: '6px 12px' }}>{a.load_id || '—'}</td>
                          <td>{a.origem} → {a.destino}</td>
                          <td style={{ textAlign: 'center' }}>{a.posicao}º lugar · sem aceite nosso</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            ))}
          </>
        )}
      </div>
    </div>
  );
}
