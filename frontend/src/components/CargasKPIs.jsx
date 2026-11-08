import React from 'react';

export default function CargasKPIs({ totalCargas, valorTotal }) {
  return (
    <div className="dashboard-grid" style={{ marginBottom: '32px' }}>
      <div className="card stat-card col-6">
        <div className="card-body">
          <div className="stat-value">{totalCargas}</div>
          <div className="stat-label">Cargas Encontradas</div>
        </div>
      </div>
      <div className="card stat-card col-6">
        <div className="card-body">
          <div className="stat-value" style={{ color: 'var(--cargo-success)' }}>
            {new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL', minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(valorTotal)}
          </div>
          <div className="stat-label">Valor Total (R$)</div>
        </div>
      </div>
    </div>
  );
}
