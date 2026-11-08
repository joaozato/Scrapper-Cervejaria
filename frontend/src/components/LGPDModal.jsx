import React, { useState, useEffect } from 'react';

export default function LGPDModal() {
  const [show, setShow] = useState(false);

  useEffect(() => {
    // Check if the user has already accepted the LGPD terms
    const accepted = localStorage.getItem('cargo_lgpd_accepted');
    if (!accepted) {
      setShow(true);
    }
  }, []);

  const handleAccept = () => {
    localStorage.setItem('cargo_lgpd_accepted', 'true');
    setShow(false);
  };

  if (!show) return null;

  return (
    <div className="modal-overlay" style={{ zIndex: 9999, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <div className="modal-content" style={{ maxWidth: '600px', width: '90%' }}>
        <h2 style={{ marginBottom: '16px', color: 'var(--cargo-blue-800)', borderBottom: '1px solid #e5e7eb', paddingBottom: '12px' }}>
          Termo de Confidencialidade e LGPD
        </h2>
        
        <div style={{ fontSize: '0.95rem', lineHeight: '1.6', color: '#4b5563', marginBottom: '24px' }}>
          <p style={{ marginBottom: '12px' }}>
            <strong>Atenção:</strong> Você está acessando um sistema corporativo interno da <strong>a transportadora</strong>.
          </p>
          <p style={{ marginBottom: '12px' }}>
            Este painel contém dados sensíveis e métricas operacionais, incluindo nomes de profissionais parceiros (Motoristas e Proprietários), valores de frete e rotas logísticas.
          </p>
          <p style={{ marginBottom: '12px' }}>
            Em conformidade com a <strong>Lei Geral de Proteção de Dados (Lei nº 13.709/2018 - LGPD)</strong>, você concorda que:
          </p>
          <ul style={{ marginLeft: '24px', marginBottom: '12px' }}>
            <li style={{ marginBottom: '8px' }}>Não compartilhará capturas de tela (prints) contendo nomes de motoristas com pessoas não autorizadas.</li>
            <li style={{ marginBottom: '8px' }}>Utilizará estas informações exclusivamente para fins operacionais internos da CARGO.</li>
            <li style={{ marginBottom: '8px' }}>O sistema registra atividades (logs) e exclusões para fins de auditoria de segurança.</li>
          </ul>
          <p style={{ fontWeight: 'bold' }}>
            A CARGO garante o direito à pseudo-anonimização dos titulares dos dados mediante solicitação.
          </p>
        </div>

        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px' }}>
          <button 
            className="btn btn-primary" 
            onClick={handleAccept}
            style={{ padding: '10px 24px', fontSize: '1rem' }}
          >
            Li e Concordo
          </button>
        </div>
      </div>
    </div>
  );
}
