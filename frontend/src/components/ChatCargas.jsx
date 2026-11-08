import React, { useEffect, useRef, useState } from 'react';
import api from '../api/client';

export const SUGESTOES_GERAIS = [
  'Qual o faturamento das cargas nos últimos 7 dias?',
  'Quais as rotas que mais pagam no mês?',
  'Qual rota fica mais tempo parada no pool?',
  'Quantas cargas foram reprogramadas esta semana?',
];

// Converte **negrito** em <strong> (sem dangerouslySetInnerHTML) e "* " no início da linha em "•".
function renderTexto(texto) {
  return texto.split(/(\*\*[^*]+\*\*)/g).map((parte, i) =>
    parte.startsWith('**') && parte.endsWith('**') && parte.length > 4
      ? <strong key={i}>{parte.slice(2, -2)}</strong>
      : parte.replace(/^\s*[*-] /gm, '• ')
  );
}

export default function ChatCargas({ sugestoes = SUGESTOES_GERAIS, maxAltura = '55vh' }) {
  const [mensagens, setMensagens] = useState([]);
  const [texto, setTexto] = useState('');
  const [loading, setLoading] = useState(false);
  const fimRef = useRef(null);

  useEffect(() => {
    fimRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [mensagens, loading]);

  const enviar = async (pergunta) => {
    const p = (pergunta ?? texto).trim();
    if (p.length < 3 || loading) return;
    const historico = mensagens
      .filter((m) => !m.erro)
      .slice(-6)
      .map((m) => ({ papel: m.papel, texto: m.texto }));
    setMensagens((m) => [...m, { papel: 'user', texto: p }]);
    setTexto('');
    setLoading(true);
    try {
      const res = await api.post('/assistente-ia/chat', { pergunta: p, historico });
      setMensagens((m) => [...m, { papel: 'ia', texto: res.data.resposta, foraEscopo: !res.data.escopo_ok }]);
    } catch (e) {
      setMensagens((m) => [...m, { papel: 'ia', texto: e.response?.data?.detail || 'Erro ao consultar a IA.', erro: true }]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
        <p style={{ fontSize: '0.85rem', opacity: 0.7, marginTop: 0 }}>
          Pergunte sobre cargas, faturamento, rotas, permanência no pool, reajustes e reprogramações.
          Outros assuntos não são respondidos. Cada pergunta consome tokens da IA.
        </p>

        <div style={{ minHeight: 280, maxHeight: maxAltura, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 10, padding: '8px 0' }}>
          {mensagens.length === 0 && (
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
              {sugestoes.map((s) => (
                <button key={s} className="btn btn-outline btn-sm" onClick={() => enviar(s)}>{s}</button>
              ))}
            </div>
          )}
          {mensagens.map((m, i) => (
            <div
              key={i}
              style={{
                alignSelf: m.papel === 'user' ? 'flex-end' : 'flex-start',
                maxWidth: '85%',
                whiteSpace: 'pre-wrap',
                padding: '10px 14px',
                borderRadius: 12,
                background: m.papel === 'user' ? 'var(--cargo-blue-600)' : 'rgba(128,128,128,0.15)',
                color: m.papel === 'user' ? '#fff' : m.erro ? '#ef4444' : 'inherit',
                opacity: m.foraEscopo ? 0.8 : 1,
              }}
            >
              {m.papel === 'ia' ? renderTexto(m.texto) : m.texto}
            </div>
          ))}
          {loading && <div style={{ opacity: 0.7 }}>Consultando as cargas...</div>}
          <div ref={fimRef} />
        </div>

        <form
          onSubmit={(e) => { e.preventDefault(); enviar(); }}
          style={{ display: 'flex', gap: 8, marginTop: 12 }}
        >
          <input
            className="form-input"
            style={{ flex: 1 }}
            value={texto}
            maxLength={500}
            onChange={(e) => setTexto(e.target.value)}
            placeholder="Ex.: qual o faturamento de lata na última semana?"
            disabled={loading}
          />
          <button className="btn btn-primary" type="submit" disabled={loading || texto.trim().length < 3}>
            Enviar
          </button>
        </form>
    </div>
  );
}
