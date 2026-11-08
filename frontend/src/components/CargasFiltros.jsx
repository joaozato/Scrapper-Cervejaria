import React, { useState, useMemo } from 'react';

function MultiSelectDropdown({ options, selected, onChange, placeholder }) {
  const [isOpen, setIsOpen] = useState(false);

  const toggleOption = (option) => {
    if (selected.includes(option)) {
      onChange(selected.filter(o => o !== option));
    } else {
      onChange([...selected, option]);
    }
  };

  return (
    <div style={{ position: 'relative' }}>
      <div
        className="form-input"
        style={{ cursor: 'pointer', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}
        onClick={() => setIsOpen(!isOpen)}
      >
        <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', color: selected.length === 0 ? '#6b7280' : 'inherit' }}>
          {selected.length === 0 ? placeholder : `${selected.length} selecionado(s)`}
        </span>
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="6 9 12 15 18 9"></polyline></svg>
      </div>

      {isOpen && (
        <>
          <div style={{ position: 'fixed', inset: 0, zIndex: 40 }} onClick={() => setIsOpen(false)} />
          <div style={{
            position: 'absolute', top: '100%', left: 0, right: 0,
            backgroundColor: 'white', border: '1px solid #e5e7eb', borderRadius: '8px',
            marginTop: '4px', padding: '8px', zIndex: 50, maxHeight: '200px', overflowY: 'auto',
            boxShadow: '0 10px 15px -3px rgba(0,0,0,0.1)'
          }}>
            {options.map(opt => (
              <div key={opt} style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '6px 4px', cursor: 'pointer', borderRadius: '4px' }}
                   onClick={() => toggleOption(opt)}
                   onMouseOver={(e) => e.currentTarget.style.backgroundColor = '#f3f4f6'}
                   onMouseOut={(e) => e.currentTarget.style.backgroundColor = 'transparent'}>
                <input type="checkbox" checked={selected.includes(opt)} readOnly style={{ cursor: 'pointer' }} />
                <span style={{ fontSize: '0.875rem' }}>{opt}</span>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

const MESES_ABREV = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez'];
const DIAS_SEMANA = ['D', 'S', 'T', 'Q', 'Q', 'S', 'S'];

// Aceita "dd/mm/aaaa" ou "aaaa-mm-dd" (os dois formatos usados nas cargas
// raspadas do Portal) e devolve {y, m, d, key} ou null se não reconhecer.
function parseRawDate(raw) {
  if (!raw) return null;
  let m = /^(\d{4})-(\d{2})-(\d{2})/.exec(raw);
  if (m) {
    const [, y, mo, d] = m;
    return { y: Number(y), m: Number(mo), d: Number(d), key: `${y}-${mo}-${d}` };
  }
  m = /^(\d{2})\/(\d{2})\/(\d{4})/.exec(raw);
  if (m) {
    const [, d, mo, y] = m;
    return { y: Number(y), m: Number(mo), d: Number(d), key: `${y}-${mo}-${d}` };
  }
  return null;
}

// Dropdown com um calendário de verdade (em vez de lista de dias soltos):
// navega mês a mês, destaca os dias que existem nos dados e deixa clicar
// direto no dia pra selecionar/desselecionar.
function CalendarMultiSelectDropdown({ options, selected, onChange, placeholder }) {
  const [isOpen, setIsOpen] = useState(false);

  // raw string -> data parseada, e um índice por "ano-mes" pra saber quais
  // meses têm dado disponível (evita o usuário navegar pra um mês vazio).
  const { byKey, monthsWithData } = useMemo(() => {
    const byKey = new Map();
    const monthsWithData = new Set();
    for (const raw of options) {
      const parsed = parseRawDate(raw);
      if (!parsed) continue;
      byKey.set(parsed.key, raw);
      monthsWithData.add(`${parsed.y}-${parsed.m}`);
    }
    return { byKey, monthsWithData };
  }, [options]);

  const maisRecente = useMemo(() => {
    let best = null;
    for (const raw of options) {
      const parsed = parseRawDate(raw);
      if (!parsed) continue;
      if (!best || parsed.key > best.key) best = parsed;
    }
    return best;
  }, [options]);

  const [viewY, setViewY] = useState(() => maisRecente?.y ?? new Date().getFullYear());
  const [viewM, setViewM] = useState(() => maisRecente?.m ?? new Date().getMonth() + 1);

  const abrirCalendario = () => {
    // Ao abrir, foca no mês do dia selecionado mais recente (se houver) ou no
    // mês mais recente com dados disponíveis - sempre mostrando algo útil.
    let ref = maisRecente;
    for (const raw of selected) {
      const parsed = parseRawDate(raw);
      if (parsed && (!ref || parsed.key > ref.key)) ref = parsed;
    }
    if (ref) {
      setViewY(ref.y);
      setViewM(ref.m);
    }
    setIsOpen(true);
  };

  const mudarMes = (delta) => {
    let m = viewM + delta;
    let y = viewY;
    if (m < 1) { m = 12; y -= 1; }
    if (m > 12) { m = 1; y += 1; }
    setViewM(m);
    setViewY(y);
  };

  const toggleDia = (raw) => {
    if (selected.includes(raw)) {
      onChange(selected.filter(o => o !== raw));
    } else {
      onChange([...selected, raw]);
    }
  };

  // Grid do mês: começa no domingo anterior (ou igual) ao dia 1, sempre 6 linhas.
  const celulas = useMemo(() => {
    const primeiro = new Date(viewY, viewM - 1, 1);
    const inicioGrid = new Date(viewY, viewM - 1, 1 - primeiro.getDay());
    const dias = [];
    for (let i = 0; i < 42; i++) {
      const dt = new Date(inicioGrid);
      dt.setDate(inicioGrid.getDate() + i);
      const key = `${dt.getFullYear()}-${String(dt.getMonth() + 1).padStart(2, '0')}-${String(dt.getDate()).padStart(2, '0')}`;
      dias.push({
        date: dt,
        key,
        foraDoMes: dt.getMonth() + 1 !== viewM,
        raw: byKey.get(key) || null,
      });
    }
    return dias;
  }, [viewY, viewM, byKey]);

  const mesTemDados = monthsWithData.has(`${viewY}-${viewM}`);

  return (
    <div style={{ position: 'relative' }}>
      <div
        className="form-input"
        style={{ cursor: 'pointer', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}
        onClick={() => (isOpen ? setIsOpen(false) : abrirCalendario())}
      >
        <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', color: selected.length === 0 ? '#6b7280' : 'inherit' }}>
          {selected.length === 0 ? placeholder : `${selected.length} selecionado(s)`}
        </span>
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="6 9 12 15 18 9"></polyline></svg>
      </div>

      {isOpen && (
        <>
          <div style={{ position: 'fixed', inset: 0, zIndex: 40 }} onClick={() => setIsOpen(false)} />
          <div style={{
            position: 'absolute', top: '100%', left: 0,
            backgroundColor: 'white', border: '1px solid #e5e7eb', borderRadius: '10px',
            marginTop: '4px', padding: '10px', zIndex: 50, width: '240px',
            boxShadow: '0 10px 15px -3px rgba(0,0,0,0.15)'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
              <button type="button" onClick={() => mudarMes(-1)} className="btn-icon"
                style={{ border: 'none', background: 'transparent', cursor: 'pointer', padding: '4px', color: 'var(--cargo-blue-700)' }}>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="15 18 9 12 15 6"></polyline></svg>
              </button>
              <span style={{ fontWeight: 600, fontSize: '0.875rem', color: 'var(--cargo-blue-800)' }}>
                {MESES_ABREV[viewM - 1]}/{viewY}
              </span>
              <button type="button" onClick={() => mudarMes(1)} className="btn-icon"
                style={{ border: 'none', background: 'transparent', cursor: 'pointer', padding: '4px', color: 'var(--cargo-blue-700)' }}>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="9 18 15 12 9 6"></polyline></svg>
              </button>
            </div>

            {!mesTemDados && (
              <div style={{ fontSize: '0.75rem', color: '#9ca3af', textAlign: 'center', marginBottom: '6px' }}>
                Sem cargas neste mês
              </div>
            )}

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: '2px', marginBottom: '4px' }}>
              {DIAS_SEMANA.map((d, i) => (
                <div key={i} style={{ textAlign: 'center', fontSize: '0.7rem', color: '#9ca3af', fontWeight: 600 }}>{d}</div>
              ))}
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: '2px' }}>
              {celulas.map(({ date, key, foraDoMes, raw }) => {
                const disponivel = !!raw;
                const marcado = disponivel && selected.includes(raw);
                return (
                  <button
                    type="button"
                    key={key}
                    disabled={!disponivel}
                    onClick={() => disponivel && toggleDia(raw)}
                    title={disponivel ? raw : undefined}
                    style={{
                      aspectRatio: '1', border: 'none', borderRadius: '6px',
                      fontSize: '0.75rem', cursor: disponivel ? 'pointer' : 'default',
                      background: marcado ? 'var(--cargo-blue-600)' : disponivel ? 'var(--cargo-blue-50)' : 'transparent',
                      color: marcado ? 'white' : disponivel ? 'var(--cargo-blue-800)' : '#d1d5db',
                      fontWeight: marcado ? 700 : 400,
                      opacity: foraDoMes ? 0.4 : 1,
                    }}
                  >
                    {date.getDate()}
                  </button>
                );
              })}
            </div>

            {selected.length > 0 && (
              <button
                type="button"
                onClick={() => onChange([])}
                style={{
                  marginTop: '8px', width: '100%', fontSize: '0.75rem', padding: '6px',
                  border: '1px solid #e5e7eb', borderRadius: '6px', background: 'white',
                  color: '#6b7280', cursor: 'pointer'
                }}
              >
                Limpar seleção ({selected.length})
              </button>
            )}
          </div>
        </>
      )}
    </div>
  );
}

export default function CargasFiltros({
  origemFilter, setOrigemFilter,
  destinoFilter, setDestinoFilter,
  tipoFilter, setTipoFilter, tiposCarga,
  fonteFilter, setFonteFilter,
  mesFilter, setMesFilter, mesesDisponiveis,
  diaCarregamentoFilter, setDiaCarregamentoFilter, diasCarregamento,
  diaCapturaFilter, setDiaCapturaFilter, diasCaptura,
  mesCapturaFilter, setMesCapturaFilter, mesesCapturaDisponiveis,
  roundFilter, setRoundFilter, rounds,
  buscaGeral, setBuscaGeral
}) {
  return (
    <div className="card card-glass" style={{ marginBottom: '32px', overflow: 'visible' }}>
      <div className="card-header" style={{ borderBottom: 'none', paddingBottom: 0 }}>
        <h3 style={{ color: 'var(--cargo-blue-800)' }}>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"></polygon></svg>
          Filtros Avançados
        </h3>
      </div>
      <div className="card-body">
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '16px' }}>
          <input
            type="text"
            className="form-input"
            placeholder="Origem..."
            value={origemFilter}
            onChange={(e) => setOrigemFilter(e.target.value)}
          />
          <input
            type="text"
            className="form-input"
            placeholder="Destino..."
            value={destinoFilter}
            onChange={(e) => setDestinoFilter(e.target.value)}
          />
          <MultiSelectDropdown
            options={tiposCarga}
            selected={tipoFilter}
            onChange={setTipoFilter}
            placeholder="Todos os Tipos"
          />
          <MultiSelectDropdown
            options={['Smart Cargas', 'Pool de Cargas']}
            selected={fonteFilter}
            onChange={setFonteFilter}
            placeholder="Todas as Fontes"
          />
          <MultiSelectDropdown
            options={mesesDisponiveis}
            selected={mesFilter}
            onChange={setMesFilter}
            placeholder="Mês de Coleta..."
          />
          <CalendarMultiSelectDropdown
            options={diasCarregamento}
            selected={diaCarregamentoFilter}
            onChange={setDiaCarregamentoFilter}
            placeholder="Dias de Coleta..."
          />
          <CalendarMultiSelectDropdown
            options={diasCaptura}
            selected={diaCapturaFilter}
            onChange={setDiaCapturaFilter}
            placeholder="Dias de Absorção..."
          />
          <MultiSelectDropdown
            options={mesesCapturaDisponiveis}
            selected={mesCapturaFilter}
            onChange={setMesCapturaFilter}
            placeholder="Mês de Absorção..."
          />
          <MultiSelectDropdown
            options={rounds}
            selected={roundFilter}
            onChange={setRoundFilter}
            placeholder="Rounds de Captura..."
          />
          <input
            type="text"
            className="form-input"
            placeholder="Busca livre (Rota, Caminhão, Load ID)..."
            value={buscaGeral}
            onChange={(e) => setBuscaGeral(e.target.value)}
          />
        </div>
      </div>
    </div>
  );
}
