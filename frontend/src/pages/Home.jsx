import React from 'react';
import useStore from '../store/useStore';

export default function Home() {
  const user = useStore((s) => s.user);

  return (
    <div className="container" style={{ padding: '24px 0' }}>
      <div className="card">
        <div className="card-header">
          <h2 className="card-title" style={{ fontSize: '1.5rem', color: 'var(--cargo-blue-800)' }}>
            Bem-vindo ao Sistema CARGO, {user?.full_name || 'Usuário'}!
          </h2>
        </div>
        <div className="card-body" style={{ lineHeight: '1.6', color: '#4b5563' }}>
          <p style={{ marginBottom: '16px' }}>
            Este sistema ajuda a CARGO a captar, aceitar e confirmar cargas no Portal, com visão clara do que está disponível e do que já foi fechado.
          </p>

          <h3 style={{ marginTop: '24px', marginBottom: '12px', color: '#1f2937' }}>Como Funciona?</h3>

          <ol style={{ paddingLeft: '24px', marginBottom: '24px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
            <li>
              <strong>Captura e coleta:</strong> o sistema consulta o Portal (Pool de Cargas e Carga Prioritária) e registra as cargas disponíveis, com origem, destino, data de carregamento, tipo de caminhão e valor. Você acompanha tudo em <em>Monitor e Cargas</em>, com filtros e gráficos.
            </li>
            <li>
              <strong>Aceite:</strong> as cargas de interesse são aceitas no Portal, manualmente ou pelo aceite automático, que segue as rotas e os limites definidos no monitor. As cargas aceitas ficam na aba de aceitas.
            </li>
            <li>
              <strong>Confirmação:</strong> depois do aceite, a carga precisa ser confirmada. Só as cargas confirmadas explicitamente seguem como fechadas e entram nos números de <em>Estatísticas</em>.
            </li>
            <li>
              <strong>Relatórios:</strong> a cada captura o sistema guarda um histórico e compara com a anterior, mostrando cargas novas, que sumiram ou que mudaram de status.
            </li>
          </ol>

          <div style={{ padding: '16px', backgroundColor: '#FFF7ED', borderLeft: '4px solid #F97316', borderRadius: '4px' }}>
            <h4 style={{ margin: '0 0 8px 0', color: 'var(--cargo-blue-800)' }}>Informações de Segurança e LGPD</h4>
            <p style={{ margin: 0, fontSize: '0.9rem' }}>
              Este é um sistema interno corporativo. Os dados trafegados aqui possuem informações sensíveis de parceiros e clientes. 
              Siga rigorosamente as políticas de segurança da CARGO e respeite as conformidades com a Lei Geral de Proteção de Dados (LGPD).
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
