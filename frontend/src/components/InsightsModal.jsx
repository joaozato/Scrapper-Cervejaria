import React, { useEffect, useState } from 'react';
import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
} from 'recharts';
import api from '../api/client';

const COR = { alerta: '#f59e0b', destaque: '#10b981', info: '#6b7280' };
const COR_BARRA = '#f97316';
const COR_BARRA_2 = '#6b7280';
const COR_POS = '#10b981';
const COR_NEG = '#ef4444';

const PERIODOS = [
  { dias: 1, label: 'Último dia' },
  { dias: 7, label: 'Últimos 7 dias' },
  { dias: 15, label: 'Últimos 15 dias' },
  { dias: 30, label: 'Últimos 30 dias' },
  { dias: 90, label: 'Últimos 90 dias' },
  { dias: 3650, label: 'Todo o histórico' },
];

const SUGESTOES = [
  'Qual rota rendeu mais neste período?',
  'Quais rotas estão ficando mais tempo paradas?',
  'Em que dia da semana entram mais cargas?',
  'O que mudou em relação ao período anterior?',
];

const DIAS_SEMANA_CURTO = ['Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb', 'Dom'];

const labelPeriodo = (dias) => PERIODOS.find((p) => p.dias === dias)?.label || `Últimos ${dias} dias`;

const FONTES = [
  { id: 'pool', label: 'Pool de Cargas' },
  { id: 'smart', label: 'Carga Prioritária' },
  { id: 'ambos', label: 'Pool + Smart' },
];
const labelFonte = (id) => FONTES.find((f) => f.id === id)?.label || 'Pool de Cargas';

const capitalizar = (t) => t.charAt(0).toUpperCase() + t.slice(1);
const labelInsumos = (insumos) => (insumos?.length ? insumos.map(capitalizar).join(', ') : 'Todos os insumos');

const fmtMin = (min) => {
  if (min == null) return '--';
  const total = Math.round(min);
  if (total < 60) return `${total} min`;
  const h = Math.floor(total / 60);
  const m = total % 60;
  return m ? `${h}h${String(m).padStart(2, '0')}` : `${h}h`;
};

const fmtBrl = (v) => (v == null ? '--' : v.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' }));

// Os nomes de rota vêm como endereços longos; no gráfico mostra só os códigos
// entre colchetes ("[294528] → [PBR02]") ou um trecho curto.
const rotaCurta = (rota) => {
  const codigos = (rota.match(/\[[^\]]+\]/g) || []);
  if (codigos.length >= 2) return `${codigos[0]} → ${codigos[1]}`;
  return rota.length > 38 ? `${rota.slice(0, 36)}…` : rota;
};

function csvCelula(v) {
  const s = v == null ? '' : String(v);
  return /[";\n\r]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

function montarCsv(dados, dias, insumos) {
  const linhas = [];
  const add = (...cols) => linhas.push(cols.map(csvCelula).join(';'));
  const { metricas, destaques, narrativa } = dados;
  const pool = metricas.pool;

  add('Insights das cargas');
  add('Período', labelPeriodo(dias));
  add('Insumos', labelInsumos(insumos));
  add('Fonte', labelFonte(metricas.fonte));
  add('Gerado em', new Date(metricas.gerado_em).toLocaleString('pt-BR'));
  add();
  add('Indicadores');
  add('Cargas vistas no pool', pool.cargas_vistas);
  add('Já saíram', pool.saidas);
  add('Ainda no pool', pool.ainda_no_pool);
  add('Tempo médio no pool (min)', pool.permanencia.media_min ?? '');
  add('Mediana no pool (min)', pool.permanencia.mediana_min ?? '');
  add('Valor médio Pool (R$)', metricas.valor?.media ?? '');
  if (metricas.valor_smart?.cargas_com_valor) add('Valor médio Carga Prioritária (R$)', metricas.valor_smart.media ?? '');
  if (metricas.assistente) {
    add('Aceitas Assistente', metricas.assistente.aceitas);
    add('Confirmadas Assistente', metricas.assistente.confirmadas);
  }
  add('Capturas de relatório', metricas.relatorios.capturas);
  add('Cargas novas nos relatórios', metricas.relatorios.novos);
  add('Cargas que sumiram dos relatórios', metricas.relatorios.sumidos);
  if (metricas.reprogramacoes) {
    add('Cargas reprogramadas', metricas.reprogramacoes.reprogramados);
    add('Atraso médio das reprogramadas (dias)', metricas.reprogramacoes.atraso_medio_dias ?? '');
  }
  if (metricas.anomalias?.length) {
    add();
    add('Alertas de anomalia (contra o período anterior)');
    add('Título', 'Texto');
    metricas.anomalias.forEach((a) => add(a.titulo, a.texto));
  }
  add();
  add('Destaques');
  add('Título', 'Texto');
  destaques.forEach((d) => add(d.titulo, d.texto));
  if (narrativa) {
    add();
    add('Análise da IA');
    narrativa.split('\n').filter((l) => l.trim()).forEach((l) => add(l));
  }
  const det = metricas.detalhe;
  if (det) {
    add();
    add('Permanência e valor por rota');
    add('Rota', 'Cargas (saíram)', 'Média (min)', 'Mediana (min)', 'Máximo (min)', 'Cargas com valor', 'Valor médio (R$)', 'Valor mín. (R$)', 'Valor máx. (R$)');
    det.rotas.forEach((r) => add(r.rota, r.cargas, r.media_min ?? '', r.mediana_min ?? '', r.max_min ?? '', r.cargas_com_valor, r.valor_medio ?? '', r.valor_min ?? '', r.valor_max ?? ''));
    add();
    add('Distribuição do tempo no pool');
    add('Faixa', 'Cargas');
    det.faixas_permanencia.forEach((f) => add(f.faixa, f.cargas));
    add();
    add('Entradas por hora (horário de Brasília)');
    add('Hora', 'Cargas');
    det.entradas_por_hora.forEach((h) => add(`${String(h.hora).padStart(2, '0')}h`, h.cargas));
    add();
    add('Entradas por dia');
    add('Dia', 'Cargas');
    det.entradas_por_dia.forEach((d) => add(d.dia, d.cargas));
    if (det.mapa_calor) {
      add();
      add('Entradas por dia da semana e hora');
      add('Dia', ...Array.from({ length: 24 }, (_, h) => `${String(h).padStart(2, '0')}h`));
      det.mapa_calor.forEach((linha, i) => add(DIAS_SEMANA_CURTO[i], ...linha));
    }
    if (det.reajustes?.length) {
      add();
      add('Cargas que mudaram de valor');
      add('Load', 'Rota', 'De (R$)', 'Para (R$)', 'Variação (R$)', 'Variação (%)', 'Reajustes', 'Horas até o último');
      det.reajustes.forEach((r) => add(r.load_id, r.rota, r.de, r.para, r.delta, r.pct ?? '', r.reajustes, r.horas_ate_ultimo));
    }
    if (det.reprogramadas?.length) {
      add();
      add('Cargas reprogramadas (relatórios)');
      add('Pedido', 'Rota', 'Reprogramação', 'Data original', 'Data de carregamento', 'Atraso (dias)');
      det.reprogramadas.forEach((r) => add(r.pedido, r.rota, r.reprogramacao ?? '', r.data_original ?? '', r.data_carregamento ?? '', r.atraso_dias ?? ''));
    }
  }
  // BOM pro Excel abrir os acentos corretamente.
  return `﻿${linhas.join('\r\n')}`;
}

function baixarCsv(dados, dias, insumos) {
  const blob = new Blob([montarCsv(dados, dias, insumos)], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `insights-cargas-${new Date().toISOString().slice(0, 10)}-${dias >= 3650 ? 'historico' : `${dias}d`}${insumos?.length ? `-${insumos.join('-')}` : ''}.csv`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export default function InsightsModal({ onClose }) {
  const [dias, setDias] = useState(7);
  const [comIA, setComIA] = useState(true);
  const [dados, setDados] = useState(null);
  const [diasGerados, setDiasGerados] = useState(null);
  const [insumos, setInsumos] = useState([]);
  const [insumosGerados, setInsumosGerados] = useState([]);
  const [fonte, setFonte] = useState('pool');
  const [fonteGerada, setFonteGerada] = useState('pool');
  const [opcoesInsumo, setOpcoesInsumo] = useState([]);
  const [loading, setLoading] = useState(false);
  const [erro, setErro] = useState('');
  const [aba, setAba] = useState('resumo');

  useEffect(() => {
    api.get('/insights/insumos')
      .then((res) => setOpcoesInsumo(res.data.insumos || []))
      .catch((e) => console.error('Erro ao carregar insumos', e));
  }, []);

  const alternarInsumo = (nome) => setInsumos((atual) => (atual.includes(nome) ? atual.filter((i) => i !== nome) : [...atual, nome]));

  // Só gera quando o usuário clica: a análise da IA consome tokens e o período
  // é escolha dele (nada roda automático ao abrir o modal).
  const gerar = async () => {
    setErro('');
    setLoading(true);
    try {
      const res = await api.get('/insights/cargas', { params: { dias, insumos: insumos.join(','), fonte, narrativa: comIA } });
      setDados(res.data);
      setDiasGerados(dias);
      setInsumosGerados(insumos);
      setFonteGerada(fonte);
      setAba('resumo');
    } catch (e) {
      console.error('Erro ao carregar insights', e);
      setErro(e.response?.data?.detail || 'Erro ao carregar os insights.');
    } finally {
      setLoading(false);
    }
  };

  const atualizarUso = (uso) => setDados((d) => (d && uso ? { ...d, uso_api: uso } : d));

  const pool = dados?.metricas?.pool;
  const abas = [['resumo', 'Resumo'], ['graficos', 'Gráficos'], ['perguntar', 'Perguntar']];

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" style={{ maxWidth: 900, maxHeight: '88vh', overflowY: 'auto' }} onClick={(e) => e.stopPropagation()}>
        <h2>Insights das cargas</h2>

        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center', margin: '12px 0' }}>
          <select value={dias} onChange={(e) => setDias(Number(e.target.value))} disabled={loading}>
            {PERIODOS.map((p) => <option key={p.dias} value={p.dias}>{p.label}</option>)}
          </select>
          <select value={fonte} onChange={(e) => setFonte(e.target.value)} disabled={loading}>
            {FONTES.map((f) => <option key={f.id} value={f.id}>{f.label}</option>)}
          </select>
          <label style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: '0.85rem' }}>
            <input type="checkbox" checked={comIA} onChange={(e) => setComIA(e.target.checked)} disabled={loading} />
            Incluir análise da IA
          </label>
          <button className="btn-primary" onClick={gerar} disabled={loading}>
            {loading ? 'Gerando...' : dados ? 'Gerar novamente' : 'Gerar insights'}
          </button>
          {dados && !loading && (
            <button className="btn-primary" style={{ marginLeft: 'auto' }} onClick={() => baixarCsv(dados, diasGerados, insumosGerados)}>
              Baixar CSV
            </button>
          )}
        </div>

        {opcoesInsumo.length > 0 && (
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center', marginBottom: 12 }}>
            <span style={{ fontSize: '0.85rem', opacity: 0.7 }}>Insumo:</span>
            <ChipInsumo ativo={insumos.length === 0} onClick={() => setInsumos([])} disabled={loading}>Todos</ChipInsumo>
            {opcoesInsumo.map((nome) => (
              <ChipInsumo key={nome} ativo={insumos.includes(nome)} onClick={() => alternarInsumo(nome)} disabled={loading}>
                {capitalizar(nome)}
              </ChipInsumo>
            ))}
          </div>
        )}

        {erro && <div className="alert-error">{erro}</div>}

        {!dados && !loading && !erro && (
          <p style={{ opacity: 0.7 }}>
            Escolha o período e clique em &quot;Gerar insights&quot;. A análise da IA só é feita quando você pedir
            (desmarque a opção acima para ver só os números, sem gastar tokens).
          </p>
        )}
        {loading && <p>Carregando cargas{comIA ? ' e gerando a análise' : ''}...</p>}

        {dados && !loading && (
          <>
            <p style={{ fontSize: '0.8rem', opacity: 0.7, margin: '0 0 8px' }}>
              Resultado de: <strong>{labelPeriodo(diasGerados)}</strong> · <strong>{labelInsumos(insumosGerados)}</strong> · <strong>{labelFonte(fonteGerada)}</strong>
            </p>

            <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
              {abas.map(([id, nome]) => (
                <button key={id} className="btn-primary" style={aba !== id ? { opacity: 0.5 } : undefined} onClick={() => setAba(id)}>
                  {nome}
                </button>
              ))}
            </div>

            {aba === 'resumo' && (
              <>
                <Alertas anomalias={dados.metricas.anomalias} periodoCompara={diasGerados < 3650} />

                <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', margin: '12px 0' }}>
                  <Kpi label="Cargas vistas no pool" valor={pool.cargas_vistas} />
                  {fonteGerada !== 'pool' && <Kpi label="Cargas Carga Prioritária" valor={pool.cargas_smart} />}
                  <Kpi label="Já saíram" valor={pool.saidas} />
                  <Kpi label="Ainda no pool" valor={pool.ainda_no_pool} />
                  {dados.metricas.assistente && <Kpi label="Aceitas Assistente" valor={dados.metricas.assistente.aceitas} />}
                </div>

                {dados.destaques.map((d, i) => (
                  <div key={i} style={{ borderLeft: `4px solid ${COR[d.tipo] || COR.info}`, padding: '6px 12px', margin: '8px 0', background: 'rgba(128,128,128,0.08)' }}>
                    <strong>{d.titulo}</strong>
                    <div style={{ fontSize: '0.9rem' }}>{d.texto}</div>
                  </div>
                ))}

                <div style={{ marginTop: 16 }}>
                  <h3>Análise da IA</h3>
                  {!comIA && !dados.narrativa ? (
                    <p style={{ opacity: 0.7 }}>Análise da IA não solicitada nesta geração.</p>
                  ) : !dados.tem_dados ? (
                    <p style={{ opacity: 0.7 }}>Sem cargas, aceites ou relatórios no período — nada para analisar. Tente um período maior.</p>
                  ) : dados.narrativa ? (
                    <div style={{ whiteSpace: 'pre-wrap', fontSize: '0.92rem' }}><TextoIA texto={dados.narrativa} /></div>
                  ) : dados.llm_disponivel ? (
                    <p style={{ opacity: 0.7 }}>A IA não retornou análise desta vez. Tente &quot;Gerar novamente&quot;.</p>
                  ) : (
                    <p style={{ opacity: 0.7 }}>Configure GEMINI_API_KEY no backend para habilitar a análise em texto.</p>
                  )}
                </div>

                {dados.tem_dados && <ResumoEnvio dias={diasGerados} insumos={insumosGerados} fonte={fonteGerada} onUso={atualizarUso} />}
              </>
            )}

            {aba === 'graficos' && <Graficos metricas={dados.metricas} temDados={dados.tem_dados} />}

            {aba === 'perguntar' && (
              <Perguntar
                dias={diasGerados}
                insumos={insumosGerados}
                fonte={fonteGerada}
                habilitado={dados.llm_disponivel && dados.tem_dados}
                motivo={!dados.llm_disponivel ? 'Configure GEMINI_API_KEY no backend para fazer perguntas.' : 'Sem dados no período/insumo — tente um período maior ou outro insumo.'}
                onUso={atualizarUso}
              />
            )}

            {dados.uso_api && <UsoApi uso={dados.uso_api} />}
          </>
        )}

        <div style={{ marginTop: 16, textAlign: 'right' }}>
          <button className="btn-primary" onClick={onClose}>Fechar</button>
        </div>
      </div>
    </div>
  );
}

// A IA devolve **negrito** em markdown; o modal não interpreta, então converte aqui.
function TextoIA({ texto }) {
  return texto.split(/(\*\*[^*]+\*\*)/g).map((parte, i) => (
    parte.startsWith('**') && parte.endsWith('**') && parte.length > 4
      ? <strong key={i}>{parte.slice(2, -2)}</strong>
      : <React.Fragment key={i}>{parte.replace(/^\s*\*\s+/gm, '• ')}</React.Fragment>
  ));
}

function ChipInsumo({ ativo, onClick, disabled, children }) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      style={{
        fontSize: '0.82rem', padding: '3px 10px', borderRadius: 12, cursor: 'pointer',
        border: `1px solid ${ativo ? COR_BARRA : 'rgba(128,128,128,0.4)'}`,
        background: ativo ? COR_BARRA : 'transparent', color: ativo ? '#fff' : 'inherit',
      }}
    >
      {children}
    </button>
  );
}

function Alertas({ anomalias, periodoCompara }) {
  if (!periodoCompara) {
    return <p style={{ fontSize: '0.8rem', opacity: 0.6 }}>Alertas de anomalia comparam com o período anterior e não existem para &quot;Todo o histórico&quot;.</p>;
  }
  if (!anomalias || anomalias.length === 0) {
    return (
      <div style={{ padding: '8px 12px', borderRadius: 8, background: 'rgba(16,185,129,0.1)', fontSize: '0.9rem' }}>
        <strong>Sem anomalias</strong> em relação ao período anterior.
      </div>
    );
  }
  return (
    <div style={{ marginBottom: 8 }}>
      <h3 style={{ fontSize: '0.95rem', marginBottom: 6 }}>Alertas (contra o período anterior)</h3>
      {anomalias.map((a, i) => (
        <div key={i} style={{ borderLeft: `4px solid ${COR[a.tipo] || COR.info}`, padding: '6px 12px', margin: '6px 0', background: `${a.tipo === 'alerta' ? 'rgba(245,158,11,0.12)' : 'rgba(128,128,128,0.08)'}` }}>
          <strong>{a.titulo}</strong>
          <div style={{ fontSize: '0.9rem' }}>{a.texto}</div>
        </div>
      ))}
    </div>
  );
}

function ResumoEnvio({ dias, insumos, fonte, onUso }) {
  const [texto, setTexto] = useState('');
  const [origem, setOrigem] = useState('');
  const [loading, setLoading] = useState(false);
  const [copiado, setCopiado] = useState(false);
  const [erro, setErro] = useState('');

  const gerar = async (usarIa) => {
    setLoading(true);
    setErro('');
    setCopiado(false);
    try {
      const res = await api.post('/insights/resumo', { dias, insumos, fonte, usar_ia: usarIa });
      setTexto(res.data.texto);
      setOrigem(res.data.origem);
      onUso(res.data.uso_api);
    } catch (e) {
      setErro(e.response?.data?.detail || 'Erro ao gerar o resumo.');
    } finally {
      setLoading(false);
    }
  };

  const copiar = async () => {
    try {
      await navigator.clipboard.writeText(texto);
      setCopiado(true);
    } catch {
      setErro('Não consegui copiar automaticamente — selecione o texto e copie.');
    }
  };

  return (
    <div style={{ marginTop: 16 }}>
      <h3>Resumo para enviar</h3>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', margin: '6px 0' }}>
        <button className="btn-primary" onClick={() => gerar(true)} disabled={loading}>
          {loading ? 'Gerando...' : 'Gerar com IA'}
        </button>
        <button className="btn-primary" style={{ opacity: 0.7 }} onClick={() => gerar(false)} disabled={loading}>
          Modelo simples (sem IA)
        </button>
      </div>
      {erro && <div className="alert-error">{erro}</div>}
      {texto && (
        <>
          <textarea
            value={texto}
            onChange={(e) => setTexto(e.target.value)}
            rows={8}
            style={{ width: '100%', fontFamily: 'inherit', fontSize: '0.9rem', padding: 8, boxSizing: 'border-box' }}
          />
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <button className="btn-primary" onClick={copiar}>{copiado ? 'Copiado!' : 'Copiar texto'}</button>
            <span style={{ fontSize: '0.78rem', opacity: 0.6 }}>
              {origem === 'ia' ? 'Escrito pela IA — revise antes de enviar.' : 'Modelo fixo, sem IA.'}
            </span>
          </div>
        </>
      )}
    </div>
  );
}

function Perguntar({ dias, insumos, fonte, habilitado, motivo, onUso }) {
  const [pergunta, setPergunta] = useState('');
  const [conversa, setConversa] = useState([]);
  const [loading, setLoading] = useState(false);

  const enviar = async (texto) => {
    const p = (texto ?? pergunta).trim();
    if (p.length < 3 || loading) return;
    setLoading(true);
    setPergunta('');
    try {
      const res = await api.post('/insights/perguntar', { pergunta: p, dias, insumos, fonte });
      setConversa((c) => [{ p, r: res.data.resposta }, ...c]);
      onUso(res.data.uso_api);
    } catch (e) {
      setConversa((c) => [{ p, r: e.response?.data?.detail || 'Erro ao perguntar.', erro: true }, ...c]);
    } finally {
      setLoading(false);
    }
  };

  if (!habilitado) return <p style={{ opacity: 0.7 }}>{motivo}</p>;

  return (
    <div>
      <p style={{ fontSize: '0.85rem', opacity: 0.7, margin: '0 0 8px' }}>
        Pergunte sobre os dados de <strong>{labelPeriodo(dias)}</strong> ({labelInsumos(insumos)}). Cada pergunta usa a IA e consome tokens.
      </p>
      <div style={{ display: 'flex', gap: 8 }}>
        <input
          value={pergunta}
          maxLength={500}
          onChange={(e) => setPergunta(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter') enviar(); }}
          placeholder="Ex.: qual rota teve mais reprogramações?"
          disabled={loading}
          style={{ flex: 1, padding: 8 }}
        />
        <button className="btn-primary" onClick={() => enviar()} disabled={loading || pergunta.trim().length < 3}>
          {loading ? 'Pensando...' : 'Perguntar'}
        </button>
      </div>
      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', margin: '8px 0' }}>
        {SUGESTOES.map((s) => (
          <button key={s} onClick={() => enviar(s)} disabled={loading}
            style={{ fontSize: '0.78rem', padding: '3px 8px', borderRadius: 12, border: '1px solid rgba(128,128,128,0.4)', background: 'transparent', cursor: 'pointer' }}>
            {s}
          </button>
        ))}
      </div>
      {conversa.map((c, i) => (
        <div key={i} style={{ margin: '10px 0' }}>
          <div style={{ fontWeight: 600 }}>{c.p}</div>
          <div style={{ whiteSpace: 'pre-wrap', fontSize: '0.92rem', color: c.erro ? '#ef4444' : undefined }}>{c.r}</div>
        </div>
      ))}
    </div>
  );
}

function MapaCalor({ mapa }) {
  const max = Math.max(1, ...mapa.flat());
  return (
    <div style={{ overflowX: 'auto' }}>
      <div style={{ display: 'grid', gridTemplateColumns: '38px repeat(24, minmax(16px, 1fr))', gap: 2, minWidth: 520, fontSize: 10 }}>
        <div />
        {Array.from({ length: 24 }, (_, h) => (
          <div key={h} style={{ textAlign: 'center', opacity: 0.6 }}>{h % 3 === 0 ? `${h}h` : ''}</div>
        ))}
        {mapa.map((linha, d) => (
          <React.Fragment key={d}>
            <div style={{ opacity: 0.7, alignSelf: 'center' }}>{DIAS_SEMANA_CURTO[d]}</div>
            {linha.map((v, h) => (
              <div
                key={h}
                title={`${DIAS_SEMANA_CURTO[d]} ${String(h).padStart(2, '0')}h: ${v} carga(s)`}
                style={{
                  height: 20, borderRadius: 3,
                  background: v ? COR_BARRA : 'rgba(128,128,128,0.12)',
                  opacity: v ? 0.2 + 0.8 * (v / max) : 1,
                }}
              />
            ))}
          </React.Fragment>
        ))}
      </div>
    </div>
  );
}

function Graficos({ metricas, temDados }) {
  const det = metricas.detalhe;
  if (!det || !temDados) {
    return <p style={{ opacity: 0.7 }}>Sem dados no período para montar gráficos. Tente um período maior.</p>;
  }
  const comNome = (r) => ({ ...r, nome: rotaCurta(r.rota) });
  const rotasPerm = det.rotas.filter((r) => r.cargas >= 2 && r.media_min != null);
  const lentas = [...rotasPerm].sort((a, b) => b.media_min - a.media_min).slice(0, 8).map(comNome);
  const rapidas = [...rotasPerm].sort((a, b) => a.media_min - b.media_min).slice(0, 8).map(comNome);
  const rotasValor = det.rotas.filter((r) => r.cargas_com_valor >= 2 && r.valor_medio != null);
  const caras = [...rotasValor].sort((a, b) => b.valor_medio - a.valor_medio).slice(0, 8).map(comNome);
  const horas = det.entradas_por_hora.map((h) => ({ ...h, nome: `${String(h.hora).padStart(2, '0')}h` }));
  const diasSemana = metricas.pool.por_dia_semana.map((d) => ({ ...d, nome: d.dia.slice(0, 3) }));
  const rj = metricas.reajustes;
  const reajPorRota = (rj?.por_rota || []).map(comNome);
  const rp = metricas.reprogramacoes;
  const reprogPorRota = (rp?.por_rota || []).map(comNome);
  const tickStyle = { fontSize: 11, fill: '#6b7280' };

  return (
    <div>
      <Bloco titulo="Quando as cargas entram no pool (dia da semana × hora, horário de Brasília)">
        <MapaCalor mapa={det.mapa_calor} />
      </Bloco>

      <Bloco titulo="Cargas que entram por dia da semana">
        <ResponsiveContainer width="100%" height={200}>
          <BarChart data={diasSemana}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} />
            <XAxis dataKey="nome" tick={tickStyle} />
            <YAxis tick={tickStyle} allowDecimals={false} />
            <Tooltip formatter={(v) => [v, 'Cargas']} labelFormatter={(_, p) => p?.[0]?.payload?.dia || ''} />
            <Bar dataKey="cargas" fill={COR_BARRA} radius={[3, 3, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </Bloco>

      <Bloco titulo="Cargas que entram por hora">
        <ResponsiveContainer width="100%" height={200}>
          <BarChart data={horas}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} />
            <XAxis dataKey="nome" tick={tickStyle} interval={1} />
            <YAxis tick={tickStyle} allowDecimals={false} />
            <Tooltip formatter={(v) => [v, 'Cargas']} />
            <Bar dataKey="cargas" fill={COR_BARRA} radius={[3, 3, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </Bloco>

      <Bloco titulo="Quanto tempo as cargas ficam no pool">
        <ResponsiveContainer width="100%" height={200}>
          <BarChart data={det.faixas_permanencia}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} />
            <XAxis dataKey="faixa" tick={tickStyle} />
            <YAxis tick={tickStyle} allowDecimals={false} />
            <Tooltip formatter={(v) => [v, 'Cargas']} />
            <Bar dataKey="cargas" fill={COR_BARRA} radius={[3, 3, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </Bloco>

      {det.entradas_por_dia.length > 1 && (
        <Bloco titulo="Cargas que entraram por dia">
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={det.entradas_por_dia}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="dia" tick={tickStyle} tickFormatter={(d) => d.slice(5).split('-').reverse().join('/')} />
              <YAxis tick={tickStyle} allowDecimals={false} />
              <Tooltip formatter={(v) => [v, 'Cargas']} />
              <Bar dataKey="cargas" fill={COR_BARRA} radius={[3, 3, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </Bloco>
      )}

      <Ranking titulo="Valor médio por rota (maiores)" dados={caras} chave="valor_medio" cor={COR_BARRA} fmt={fmtBrl} rotulo="Valor médio" />
      <Ranking titulo="Rotas que mais ficam paradas (tempo médio)" dados={lentas} chave="media_min" cor={COR_BARRA} fmt={fmtMin} rotulo="Tempo médio" />
      <Ranking titulo="Rotas que saem mais rápido (tempo médio)" dados={rapidas} chave="media_min" cor={COR_BARRA_2} fmt={fmtMin} rotulo="Tempo médio" />

      {rj && (
        <Bloco titulo="Evolução do valor: variação média por rota (R$)">
          {reajPorRota.length > 0 ? (
            <Ranking titulo="" dados={reajPorRota} chave="variacao_media_rs" corPorSinal fmt={fmtBrl} rotulo="Variação média" />
          ) : (
            <p style={{ opacity: 0.7, fontSize: '0.88rem' }}>
              Nenhuma carga mudou de valor no período
              {rj.historico_desde ? ` (histórico gravado desde ${new Date(rj.historico_desde).toLocaleDateString('pt-BR')}).` : ' — o histórico de valores ainda não começou a ser gravado.'}
            </p>
          )}
        </Bloco>
      )}

      {rp && rp.itens_analisados > 0 && (
        <Bloco titulo={`Reprogramações por rota (${rp.reprogramados} de ${rp.itens_analisados} cargas)`}>
          {reprogPorRota.length > 0
            ? <Ranking titulo="" dados={reprogPorRota} chave="reprogramadas" cor={COR_BARRA} fmt={(v) => v} rotulo="Reprogramadas" />
            : <p style={{ opacity: 0.7, fontSize: '0.88rem' }}>Nenhuma reprogramação no período.</p>}
        </Bloco>
      )}

      <p style={{ fontSize: '0.75rem', opacity: 0.6 }}>Rankings consideram rotas com pelo menos 2 cargas no período.</p>
    </div>
  );
}

function Ranking({ titulo, dados, chave, cor, corPorSinal, fmt, rotulo }) {
  if (dados.length === 0) return null;
  const conteudo = (
    <ResponsiveContainer width="100%" height={Math.max(160, dados.length * 30 + 30)}>
      <BarChart data={dados} layout="vertical" margin={{ left: 10, right: 20 }}>
        <CartesianGrid strokeDasharray="3 3" horizontal={false} />
        <XAxis type="number" tick={{ fontSize: 11, fill: '#6b7280' }} tickFormatter={(v) => fmt(v)} />
        <YAxis type="category" dataKey="nome" width={150} tick={{ fontSize: 11, fill: '#6b7280' }} />
        <Tooltip
          formatter={(v) => [fmt(v), rotulo]}
          labelFormatter={(_, p) => p?.[0]?.payload?.rota || ''}
        />
        <Bar
          dataKey={chave}
          fill={cor}
          radius={[0, 3, 3, 0]}
          shape={corPorSinal ? (p) => (
            // Valores negativos vêm com largura negativa: inverte pra desenhar a barra.
            <rect x={p.width < 0 ? p.x + p.width : p.x} y={p.y} width={Math.abs(p.width)} height={p.height}
              fill={p[chave] >= 0 ? COR_POS : COR_NEG} rx={3} />
          ) : undefined}
        />
      </BarChart>
    </ResponsiveContainer>
  );
  return titulo ? <Bloco titulo={titulo}>{conteudo}</Bloco> : conteudo;
}

function Bloco({ titulo, children }) {
  return (
    <div style={{ marginBottom: 20 }}>
      <h3 style={{ fontSize: '0.95rem', marginBottom: 6 }}>{titulo}</h3>
      {children}
    </div>
  );
}

function UsoApi({ uso }) {
  const mes = uso.mes;
  const pct = Math.min(mes?.percentual ?? 0, 100);
  const cor = pct >= 90 ? '#ef4444' : pct >= 70 ? '#f59e0b' : '#10b981';
  return (
    <div style={{ marginTop: 16, padding: 10, borderRadius: 8, background: 'rgba(128,128,128,0.08)', fontSize: '0.85rem' }}>
      <strong>Uso da API (Gemini)</strong>
      {mes?.limite > 0 && (
        <div style={{ margin: '8px 0' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <span>Este mês: {mes.tokens.toLocaleString('pt-BR')} de {mes.limite.toLocaleString('pt-BR')} tokens</span>
            <strong style={{ color: cor }}>{mes.percentual}%</strong>
          </div>
          <div style={{ height: 10, borderRadius: 5, background: 'rgba(128,128,128,0.25)', overflow: 'hidden', marginTop: 4 }}>
            <div style={{ width: `${pct}%`, height: '100%', background: cor, transition: 'width 0.4s' }} />
          </div>
        </div>
      )}
      <div style={{ marginTop: 4 }}>
        Total desde o início: {uso.chamadas} chamada(s) · {uso.tokens_total.toLocaleString('pt-BR')} tokens
        {' '}({uso.tokens_entrada.toLocaleString('pt-BR')} entrada + {uso.tokens_saida.toLocaleString('pt-BR')} saída)
        {uso.ultima_chamada && ` · última em ${new Date(uso.ultima_chamada).toLocaleString('pt-BR')}`}
      </div>
    </div>
  );
}

function Kpi({ label, valor }) {
  return (
    <div style={{ flex: '1 1 140px', padding: 10, borderRadius: 8, background: 'rgba(128,128,128,0.1)' }}>
      <div style={{ fontSize: '1.4rem', fontWeight: 700 }}>{valor}</div>
      <div style={{ fontSize: '0.78rem', opacity: 0.7 }}>{label}</div>
    </div>
  );
}
