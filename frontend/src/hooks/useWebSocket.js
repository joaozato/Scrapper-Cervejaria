import { useEffect } from 'react';
import { onWebSocketMessage } from '../api/websocket';
import useStore from '../store/useStore';

export default function useWebSocket() {
  const updateDisponibilidade = useStore((s) => s.updateDisponibilidade);
  const addDisponibilidade = useStore((s) => s.addDisponibilidade);
  const removeDisponibilidade = useStore((s) => s.removeDisponibilidade);
  const setDashboardTotal = useStore((s) => s.setDashboardTotal);
  const setDashboardDias = useStore((s) => s.setDashboardDias);
  const setRanking = useStore((s) => s.setRanking);
  const setSheetsSyncStatus = useStore((s) => s.setSheetsSyncStatus);
  const incrementRefresh = useStore((s) => s.incrementRefresh);

  useEffect(() => {
    const unsubscribe = onWebSocketMessage((message) => {
      switch (message.type) {
        case 'disponibilidade_update':
          if (message.action === 'update') {
            updateDisponibilidade(message.data);
          } else if (message.action === 'create') {
            addDisponibilidade(message.data);
          } else if (message.action === 'delete') {
            removeDisponibilidade(message.data.id);
          }
          break;

        case 'dashboard_refresh':
          setDashboardTotal({
            total_disponiveis: message.data.total_disponiveis,
            total_podem_carregar: message.data.total_podem_carregar,
            total_nao_podem: message.data.total_nao_podem,
          });
          if (message.data.dias) {
            setDashboardDias(message.data.dias);
          }
          break;

        case 'ranking_update':
          setRanking(message.data);
          break;

        case 'sheets_sync_status':
          setSheetsSyncStatus(message.data);
          break;

        case 'full_refresh':
          incrementRefresh();
          break;

        default:
          break;
      }
    });

    return unsubscribe;
  }, []);
}
