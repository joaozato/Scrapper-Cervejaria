import React, { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import useStore from '../store/useStore';
import api from '../api/client';
import LGPDModal from './LGPDModal';
import { connectWebSocket, disconnectWebSocket } from '../api/websocket';

export default function Layout({ children }) {
  const user = useStore((s) => s.user);
  const clearAuth = useStore((s) => s.clearAuth);
  const wsConnected = useStore((s) => s.wsConnected);
  const navigate = useNavigate();

  useEffect(() => {
    connectWebSocket();
    return () => disconnectWebSocket();
  }, []);

  const handleLogout = async () => {
    try {
      await api.post('/auth/logout');
    } catch (e) {
      // ignore
    }
    clearAuth();
    navigate('/login');
  };

  const initials = user?.full_name
    ? user.full_name.split(' ').map((n) => n[0]).join('').slice(0, 2).toUpperCase()
    : 'GM';

  return (
    <div className="app-layout">
      <header className="topbar">
        <div className="topbar-logo">
          <span className="logo-text">Captador de Cargas</span>
        </div>

        <nav className="topbar-nav">
          <a href="/" className={window.location.pathname === '/' ? 'active' : ''}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"></path>
              <polyline points="9 22 9 12 15 12 15 22"></polyline>
            </svg>
            Home
          </a>
          <a href="/cargas" className={window.location.pathname === '/cargas' ? 'active' : ''}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <rect x="2" y="7" width="20" height="14" rx="2" ry="2"></rect>
              <path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"></path>
            </svg>
            Monitor e Cargas
          </a>
          <a href="/relatorios" className={window.location.pathname === '/relatorios' ? 'active' : ''}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M4 4a2 2 0 0 1 2-2h8l6 6v12a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2z"></path>
              <path d="M14 2v6h6"></path>
              <line x1="8" y1="13" x2="16" y2="13"></line>
              <line x1="8" y1="17" x2="16" y2="17"></line>
            </svg>
            Relatórios
          </a>
          <a href="/estatisticas" className={window.location.pathname === '/estatisticas' ? 'active' : ''}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="12" y1="1" x2="12" y2="23"></line>
              <path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"></path>
            </svg>
            Estatísticas
          </a>
          {user?.role === 'admin' && (
            <a href="/auditoria" className={window.location.pathname === '/auditoria' ? 'active' : ''}>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path>
              </svg>
              Auditoria
            </a>
          )}
          <a href="/assistente-ia" className={window.location.pathname === '/assistente-ia' ? 'active' : ''}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
            </svg>
            Assistente IA
          </a>
        </nav>

        <div className="topbar-user">
          <div className="topbar-user-info">
            <div className="topbar-user-avatar">{initials}</div>
            <div className="topbar-user-name">{user?.full_name || 'Usuário'}</div>
          </div>
          <button className="btn-logout" onClick={handleLogout}>Sair</button>
        </div>
      </header>

      <main className="main-content">
        <div className="page-header" style={{ justifyContent: 'flex-end', marginBottom: 'var(--space-md)' }}>
          <div className="live-indicator">
            <span className="live-dot"></span>
            {wsConnected ? 'Ao vivo' : 'Conectando...'}
          </div>
        </div>
        {children}
      </main>
      <LGPDModal />
    </div>
  );
}
