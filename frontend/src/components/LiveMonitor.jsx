import React, { useState, useEffect } from 'react';
import api from '../api/client';

const LiveMonitor = ({ isOpen, onClose }) => {
  const [status, setStatus] = useState(null);
  const [timestamp, setTimestamp] = useState(Date.now());

  useEffect(() => {
    let intervalId;
    
    const fetchStatus = async () => {
      try {
        const response = await api.get(`/scraper/monitor/status`);
        setStatus(response.data);
        setTimestamp(Date.now());
      } catch (error) {
        console.error('Erro ao buscar status do monitor', error);
      }
    };

    if (isOpen) {
      fetchStatus();
      intervalId = setInterval(fetchStatus, 2000);
    }

    return () => {
      if (intervalId) clearInterval(intervalId);
    };
  }, [isOpen]);

  const handleRunScraper = async () => {
    try {
      await api.post(`/scraper/monitor/run`);
      setStatus(prev => ({...prev, is_running: true, status: 'Iniciando execução manual forçada...'}));
    } catch (error) {
      console.error('Erro:', error);
      alert(error.response?.data?.message || 'Erro de conexão ao tentar iniciar o scraper');
    }
  };

  const handleStopScraper = async () => {
    try {
      await api.post(`/scraper/monitor/stop`);
      setStatus(prev => ({...prev, status: 'Parada solicitada pelo usuário. Encerrando...'}));
    } catch (error) {
      console.error('Erro:', error);
      alert(error.response?.data?.message || 'Erro de conexão ao tentar parar o scraper');
    }
  };

  const handleRunReportScraper = async () => {
    try {
      await api.post(`/scraper/monitor/run-report`);
      setStatus(prev => ({...prev, is_running: true, status: 'Iniciando busca do Relatório...'}));
    } catch (error) {
      console.error('Erro:', error);
      alert(error.response?.data?.message || 'Erro de conexão ao tentar iniciar o scraper de relatório');
    }
  };

  if (!isOpen) return null;

  return (
    <div style={{
      position: 'fixed',
      top: 0, left: 0, right: 0, bottom: 0,
      zIndex: 9999,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      backgroundColor: 'rgba(0,0,0,0.8)',
      backdropFilter: 'blur(4px)',
      padding: '16px'
    }}>
      <div style={{
        backgroundColor: '#0a0a0a',
        border: '1px solid #1f2937',
        borderRadius: '8px',
        width: '100%',
        maxWidth: '1000px',
        height: '85vh',
        display: 'flex',
        flexDirection: 'column',
        boxShadow: '0 25px 50px -12px rgba(0,0,0,0.5)',
        overflow: 'hidden',
        fontFamily: 'sans-serif'
      }}>
        {/* Header */}
        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          padding: '12px 20px',
          backgroundColor: '#111827',
          borderBottom: '1px solid #1f2937'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <div style={{ position: 'relative', width: '12px', height: '12px', display: 'flex' }}>
              <span style={{
                position: 'absolute', width: '100%', height: '100%', borderRadius: '50%',
                backgroundColor: status?.is_running ? '#f87171' : '#9ca3af',
                animation: status?.is_running ? 'ping 1.5s cubic-bezier(0, 0, 0.2, 1) infinite' : 'none',
                opacity: 0.75
              }}></span>
              <span style={{
                position: 'relative', width: '100%', height: '100%', borderRadius: '50%',
                backgroundColor: status?.is_running ? '#ef4444' : '#6b7280'
              }}></span>
            </div>
            <h2 style={{ color: 'white', fontWeight: 'bold', fontSize: '1.125rem', margin: 0, display: 'flex', alignItems: 'center', gap: '8px' }}>
              Monitor de CFTV - Scraper
              {status?.is_running && <span style={{
                padding: '2px 6px', borderRadius: '4px', fontSize: '0.75rem',
                backgroundColor: 'rgba(239,68,68,0.2)', color: '#f87171', border: '1px solid rgba(239,68,68,0.3)'
              }}>AO VIVO</span>}
            </h2>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            {!status?.is_running && (
              <>
                <button onClick={handleRunReportScraper} style={{
                  backgroundColor: '#EA580C', color: 'white', padding: '6px 12px', borderRadius: '4px',
                  fontSize: '0.875rem', fontWeight: 500, border: '1px solid #C2410C', cursor: 'pointer',
                  display: 'flex', alignItems: 'center', gap: '6px'
                }}>
                  <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 20 20" fill="currentColor">
                    <path fillRule="evenodd" d="M4 4a2 2 0 012-2h4.586A2 2 0 0112 2.586L15.414 6A2 2 0 0116 7.414V16a2 2 0 01-2 2H6a2 2 0 01-2-2V4zm2 6a1 1 0 011-1h6a1 1 0 110 2H7a1 1 0 01-1-1zm1 3a1 1 0 100 2h6a1 1 0 100-2H7z" clipRule="evenodd" />
                  </svg>
                  Relatório
                </button>
                <button onClick={handleRunScraper} style={{
                  backgroundColor: '#16a34a', color: 'white', padding: '6px 12px', borderRadius: '4px',
                  fontSize: '0.875rem', fontWeight: 500, border: '1px solid #22c55e', cursor: 'pointer',
                  display: 'flex', alignItems: 'center', gap: '6px'
                }}>
                  <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 20 20" fill="currentColor">
                    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM9.555 7.168A1 1 0 008 8v4a1 1 0 001.555.832l3-2a1 1 0 000-1.664l-3-2z" clipRule="evenodd" />
                  </svg>
                  Iniciar Scraper
                </button>
              </>
            )}
            {status?.is_running && (
              <button onClick={handleStopScraper} style={{
                backgroundColor: '#dc2626', color: 'white', padding: '6px 12px', borderRadius: '4px',
                fontSize: '0.875rem', fontWeight: 500, border: '1px solid #ef4444', cursor: 'pointer',
                display: 'flex', alignItems: 'center', gap: '6px'
              }}>
                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 20 20" fill="currentColor">
                  <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8 7a1 1 0 00-1 1v4a1 1 0 001 1h4a1 1 0 001-1V8a1 1 0 00-1-1H8z" clipRule="evenodd" />
                </svg>
                Parada de Emergência
              </button>
            )}
            <button onClick={onClose} style={{
              background: 'none', border: 'none', color: '#9ca3af', cursor: 'pointer', padding: '4px', marginLeft: '8px'
            }}>
              <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>

        {/* Content Area */}
        <div style={{
          flex: 1, backgroundColor: '#000', position: 'relative', display: 'flex',
          flexDirection: 'column', justifyContent: 'center', alignItems: 'center', overflow: 'hidden'
        }}>
          {(() => {
            const hasError = status?.status && status.status.toLowerCase().includes('erro');
            const isRunning = status?.is_running;

            if (hasError) {
              return (
                <div style={{ textAlign: 'center', color: '#f87171', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '16px', zIndex: 10 }}>
                  <img src="/bot_error.png" alt="Erro no Bot" style={{ height: '200px', filter: 'drop-shadow(0 10px 15px rgba(220,38,38,0.3))' }} />
                  <div style={{ fontFamily: 'monospace' }}>
                    <p style={{ fontSize: '1.25rem', margin: 0, color: '#ef4444', fontWeight: 'bold' }}>Problema Detectado</p>
                    <p style={{ fontSize: '0.875rem', margin: '4px 0 0 0', color: '#fca5a5' }}>O Scraper reportou um erro ou falha no servidor.</p>
                  </div>
                </div>
              );
            }

            if (isRunning) {
              return (
                <>
                  <img 
                    src={`/api/scraper/monitor/stream?t=${timestamp}`} 
                    alt="Live View" 
                    style={{ maxHeight: '100%', maxWidth: '100%', objectFit: 'contain', zIndex: 1 }}
                    onError={(e) => { e.target.src = "data:image/svg+xml;charset=UTF-8,%3Csvg xmlns='http://www.w3.org/2000/svg' width='800' height='600' style='background:%23000'%3E%3Ctext x='50%25' y='50%25' fill='%236b7280' dominant-baseline='middle' text-anchor='middle' font-family='monospace' font-size='24'%3EAguardando conexão com a câmera...%3C/text%3E%3C/svg%3E"; }}
                  />
                  <div style={{
                    position: 'absolute', bottom: '20px', right: '20px', zIndex: 2,
                    animation: 'bounce 2s infinite'
                  }}>
                    <img src="/bot.png" alt="Scraper Bot Trabalhando" style={{ height: '180px', filter: 'drop-shadow(0 10px 15px rgba(0,0,0,0.8))' }} />
                  </div>
                </>
              );
            }

            return (
              <div style={{ textAlign: 'center', color: '#6b7280', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '16px' }}>
                <img src="/bot.png" alt="Bot Dormindo" style={{ height: '150px', opacity: 0.5, filter: 'grayscale(100%)' }} />
                <div style={{ fontFamily: 'monospace' }}>
                  <p style={{ fontSize: '1.25rem', margin: 0, color: '#9ca3af' }}>Bot Dormindo</p>
                  <p style={{ fontSize: '0.875rem', margin: '4px 0 0 0' }}>O Scraper não está executando no momento.</p>
                </div>
              </div>
            );
          })()}
        </div>

        {/* Terminal Logger */}
        <div style={{
          backgroundColor: '#050505', padding: '12px 16px', borderTop: '1px solid #1f2937', fontFamily: 'monospace'
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', color: '#6b7280', fontSize: '0.75rem', marginBottom: '8px' }}>
            <span>Última atualização: {status?.last_update ? new Date(status.last_update).toLocaleTimeString() : '--:--:--'}</span>
            {status?.total_cards > 0 && (
              <span>Progresso: {status.cards_read} / {status.total_cards} cards</span>
            )}
          </div>
          <div style={{ color: '#4ade80', fontSize: '0.875rem', display: 'flex', gap: '8px' }}>
            <span style={{ color: '#4b5563' }}>&gt;</span>
            <span>{status?.status || 'Aguardando status do sistema...'}</span>
          </div>
        </div>
        
        <style dangerouslySetInnerHTML={{__html: `
          @keyframes ping {
            75%, 100% {
              transform: scale(2);
              opacity: 0;
            }
          }
          @keyframes bounce {
            0%, 100% {
              transform: translateY(-5%);
              animation-timing-function: cubic-bezier(0.8,0,1,1);
            }
            50% {
              transform: none;
              animation-timing-function: cubic-bezier(0,0,0.2,1);
            }
          }
        `}} />
      </div>
    </div>
  );
};

export default LiveMonitor;
