import React, { useEffect, useState } from 'react';
import api from '../api/client';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts';

const PERIODOS = [
  { dias: 1, label: 'Hoje' },
  { dias: 3, label: 'Últimos 3 dias' },
  { dias: 7, label: 'Últimos 7 dias' },
  { dias: 15, label: 'Últimos 15 dias' },
  { dias: 30, label: 'Últimos 30 dias' },
];

const brl = (v) => new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(v || 0);
const fmtDia = (iso) => iso.split('-').reverse().slice(0, 2).join('/');

export default function AceitesRelatorio() {
  const [dias, setDias] = useState(7);
  const [dados, setDados] = useState(null);
  const [erro, setErro] = useState('');
  const [aberta, setAberta] = useState(null);

  useEffect(() => {
    let ativo = true;
    setErro('');
    api.get('/estatisticas/aceites', { params: { dias } })
      .then((res) => ativo && setDados(res.data))
      .catch(() => ativo && setErro('Não foi possível carregar o comparativo.'));
    return () => { ativo = false; };
  }, [dias]);

  const porDia = (dados?.por_dia || []).map((d) => ({ ...d, dia: fmtDia(d.dia) }));
  const porHora = (dados?.por_hora_de_deteccao || []).map((h) => ({
    ...h, hora: `${String(h.hora).padStart(2, '0')}h`, outros: h.aceitas - h.no_passe_extra,
  }));
  const taxa = dados?.taxa_confirmacao_pct;

  const atencao = [];
  if (dados) {
    if (taxa != null && taxa < 70) {
      atencao.push(`Só ${taxa}% das aceitas aparecem confirmadas no relatório (${dados.confirmadas_no_relatorio} de ${dados.aceitas_detectadas}).`);
    }
    [...porDia]
      .map((d) => ({ ...d, falta: d.aceitas - d.confirmadas_relatorio }))
      .filter((d) => d.falta > 0)
      .sort((a, b) => b.falta - a.falta)
      .slice(0, 3)
      .forEach((d) => atencao.push(`${d.dia}: ${d.aceitas} aceitas, ${d.confirmadas_relatorio} confirmadas (${d.falta} sem confirmação).`));
    if (dados.detectadas_por_passe.extra > 0) {
      atencao.push(`O passe das :55 pegou ${dados.detectadas_por_passe.extra} aceite(s) que o das :40 não veria.`);
    }
  }

  return (
    <div className="card">
      <div className="card-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 8 }}>
        <h3 className="card-title">Aceites detectados x Confirmadas no relatório</h3>
        <select value={dias} onChange={(e) => setDias(Number(e.target.value))}>
          {PERIODOS.map((p) => <option key={p.dias} value={p.dias}>{p.label}</option>)}
        </select>
      </div>
      <div className="card-body">
        <p style={{ fontSize: '0.85rem', opacity: 0.7, marginTop: 0 }}>
          Cargas com carregamento no período (até +5 dias). "Aceitas" são as vistas como aceitas no Carga Prioritária
          por qualquer operador; "confirmadas" vêm do relatório do Portal (Lata e Arroz), a verdade do que foi repassado à CARGO.
        </p>
        {erro && <p style={{ color: '#ef4444' }}>{erro}</p>}
        {!dados && !erro && <p>Carregando...</p>}
        {dados && (
          <>
            {atencao.length > 0 && (
              <div style={{ border: '1px solid var(--cargo-warning)', borderRadius: 8, padding: '10px 14px', marginBottom: 20 }}>
                <strong>Pontos de atenção</strong>
                <ul style={{ margin: '6px 0 0', paddingLeft: 20 }}>
                  {atencao.map((a, i) => <li key={i}>{a}</li>)}
                </ul>
              </div>
            )}
            <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', marginBottom: 24 }}>
              <Kpi valor={dados.aceitas_detectadas} rotulo="Aceitas detectadas" cor="var(--cargo-warning)" sub={brl(dados.valor_aceito)} />
              <Kpi valor={dados.confirmadas_no_relatorio} rotulo="Confirmadas no relatório" cor="var(--cargo-success)" sub={`${dados.linhas_no_relatorio} linhas no relatório`} />
              <Kpi valor={taxa == null ? '—' : `${taxa}%`} rotulo="Taxa de confirmação" cor={taxa != null && taxa < 70 ? '#ef4444' : 'var(--cargo-success)'} sub="confirmadas ÷ aceitas" />
              <Kpi valor={dados.detectadas_por_passe.extra} rotulo="Pegas no passe extra (:55)" cor="var(--cargo-primary, #C2410C)" sub={`${dados.detectadas_por_passe.completo} no passe completo · ${dados.detectadas_por_passe.historico} anteriores ao registro`} />
            </div>

            <div style={{ display: 'flex', gap: 24, flexWrap: 'wrap' }}>
              <div style={{ flex: 1, minWidth: 320 }}>
                <h4 style={{ margin: '0 0 8px' }}>Por dia de carregamento</h4>
                <ResponsiveContainer width="100%" height={260}>
                  <BarChart data={porDia}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e5e7eb" />
                    <XAxis dataKey="dia" tickLine={false} axisLine={false} />
                    <YAxis allowDecimals={false} tickLine={false} axisLine={false} />
                    <Tooltip />
                    <Legend />
                    <Bar dataKey="aceitas" name="Aceitas" fill="var(--cargo-warning)" radius={[4, 4, 0, 0]} />
                    <Bar dataKey="confirmadas_relatorio" name="Confirmadas (relatório)" fill="var(--cargo-success)" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
              <div style={{ flex: 1, minWidth: 320 }}>
                <h4 style={{ margin: '0 0 8px' }}>Por horário de detecção</h4>
                <ResponsiveContainer width="100%" height={260}>
                  <BarChart data={porHora}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e5e7eb" />
                    <XAxis dataKey="hora" tickLine={false} axisLine={false} />
                    <YAxis allowDecimals={false} tickLine={false} axisLine={false} />
                    <Tooltip />
                    <Legend />
                    <Bar dataKey="outros" stackId="a" name="Passe completo (:40)" fill="var(--cargo-warning)" />
                    <Bar dataKey="no_passe_extra" stackId="a" name="Passe extra (:55)" fill="var(--cargo-primary, #C2410C)" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>

            <h4 style={{ margin: '28px 0 4px' }}>Desdobramento por rota</h4>
            <p style={{ fontSize: '0.8rem', opacity: 0.7, margin: '0 0 8px' }}>
              Vieram = cargas vistas no Carga Prioritária · Aceitas = detectadas como aceitas · Confirmadas = confirmadas no relatório.
            </p>
            <div style={{ overflowX: 'auto' }}>
              <table className="data-table" style={{ width: '100%' }}>
                <thead>
                  <tr>
                    <th style={{ textAlign: 'left', padding: '8px 12px', width: '40%' }}>Rota</th>
                    <th style={{ textAlign: 'center' }}>Vieram</th>
                    <th style={{ textAlign: 'center' }}>Aceitas</th>
                    <th style={{ textAlign: 'center' }}>% aceitas</th>
                    <th style={{ textAlign: 'center' }}>Confirmadas</th>
                    <th style={{ textAlign: 'center' }}>% confirmadas</th>
                    <th style={{ textAlign: 'right', paddingRight: 12 }}>Valor aceito</th>
                  </tr>
                </thead>
                <tbody>
                  {(dados.por_rota || []).map((r) => {
                    const pctAceitas = r.vieram ? Math.round((100 * r.aceitas) / r.vieram) : null;
                    const pctConf = r.aceitas ? Math.round((100 * r.confirmadas) / r.aceitas) : null;
                    const expandida = aberta === r.rota;
                    return (
                      <React.Fragment key={r.rota}>
                      <tr onClick={() => setAberta(expandida ? null : r.rota)} style={{ cursor: 'pointer' }}>
                        <td title={r.rota} style={{ padding: '8px 12px', whiteSpace: 'normal', wordBreak: 'break-word', maxWidth: 420 }}>{expandida ? '▾' : '▸'} {r.rota}</td>
                        <td style={{ textAlign: 'center' }}>{r.vieram}</td>
                        <td style={{ textAlign: 'center' }}>{r.aceitas}</td>
                        <td style={{ textAlign: 'center' }}>{pctAceitas == null ? '—' : `${pctAceitas}%`}</td>
                        <td style={{ textAlign: 'center' }}>{r.confirmadas}</td>
                        <td style={{ textAlign: 'center', color: pctConf != null && pctConf < 70 ? '#ef4444' : 'inherit' }}>
                          {pctConf == null ? '—' : `${pctConf}%`}
                        </td>
                        <td style={{ textAlign: 'right', paddingRight: 12 }}>{brl(r.valor_aceito)}</td>
                      </tr>
                      {expandida && (r.dias || []).map((d) => (
                        <tr key={d.dia} style={{ background: 'rgba(128,128,128,0.08)', fontSize: '0.85rem' }}>
                          <td style={{ padding: '6px 12px 6px 32px' }}>{fmtDia(d.dia)}</td>
                          <td style={{ textAlign: 'center' }}>{d.vieram}</td>
                          <td style={{ textAlign: 'center' }}>{d.aceitas}</td>
                          <td style={{ textAlign: 'center' }}>{d.vieram ? `${Math.round((100 * d.aceitas) / d.vieram)}%` : '—'}</td>
                          <td style={{ textAlign: 'center' }}>{d.confirmadas}</td>
                          <td style={{ textAlign: 'center' }}>{d.aceitas ? `${Math.round((100 * d.confirmadas) / d.aceitas)}%` : '—'}</td>
                          <td />
                        </tr>
                      ))}
                      </React.Fragment>
                    );
                  })}
                </tbody>
              </table>
            </div>

            <h4 style={{ margin: '28px 0 8px' }}>Por dia de carregamento</h4>
            {porDia.length > 0 ? (
              <table className="data-table" style={{ marginTop: 24, width: '100%' }}>
                <thead>
                  <tr>
                    <th style={{ textAlign: 'left', padding: '8px 12px' }}>Dia</th>
                    <th style={{ textAlign: 'center' }}>Aceitas</th>
                    <th style={{ textAlign: 'center' }}>Confirmadas (relatório)</th>
                    <th style={{ textAlign: 'center' }}>Sem confirmação</th>
                    <th style={{ textAlign: 'right', paddingRight: 12 }}>Valor aceito</th>
                  </tr>
                </thead>
                <tbody>
                  {porDia.map((d) => (
                    <tr key={d.dia}>
                      <td style={{ padding: '8px 12px' }}>{d.dia}</td>
                      <td style={{ textAlign: 'center' }}>{d.aceitas}</td>
                      <td style={{ textAlign: 'center' }}>{d.confirmadas_relatorio}</td>
                      <td style={{ textAlign: 'center', color: d.aceitas > d.confirmadas_relatorio ? '#ef4444' : 'inherit' }}>
                        {Math.max(d.aceitas - d.confirmadas_relatorio, 0)}
                      </td>
                      <td style={{ textAlign: 'right', paddingRight: 12 }}>{brl(d.valor_aceito)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <p style={{ opacity: 0.7 }}>Nenhum aceite detectado no período ainda.</p>
            )}
          </>
        )}
      </div>
    </div>
  );
}

function Kpi({ valor, rotulo, cor, sub }) {
  return (
    <div className="card stat-card" style={{ flex: 1, minWidth: 180, margin: 0 }}>
      <div className="card-body">
        <div className="stat-value" style={{ color: cor }}>{valor}</div>
        <div className="stat-label">{rotulo}</div>
        <div style={{ marginTop: 6, fontSize: '0.8rem', color: '#6b7280' }}>{sub}</div>
      </div>
    </div>
  );
}
