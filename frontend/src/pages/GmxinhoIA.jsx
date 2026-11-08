import React from 'react';
import ChatCargas from '../components/ChatCargas';

export default function AssistenteIA() {
  return (
    <div className="card" style={{ maxWidth: 900, margin: '0 auto' }}>
      <div className="card-header">
        <h3>Assistente IA</h3>
      </div>
      <div className="card-body">
        <ChatCargas />
      </div>
    </div>
  );
}
