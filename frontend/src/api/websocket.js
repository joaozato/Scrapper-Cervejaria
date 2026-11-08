import api from './client';
import useStore from '../store/useStore';

let ws = null;
let reconnectTimer = null;
let messageHandlers = [];
let isConnecting = false;

export async function connectWebSocket() {
  if (ws && ws.readyState === WebSocket.OPEN) return;
  if (isConnecting) return;
  isConnecting = true;

  try {
    const res = await api.post('/auth/ws-ticket');
    const ticket = res.data.ticket;

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host;
    ws = new WebSocket(`${protocol}//${host}/ws?ticket=${ticket}`);


  ws.onopen = () => {
    isConnecting = false;
    console.log('[WS] Connected');
    useStore.getState().setWsConnected(true);
    // Start ping interval
    const pingInterval = setInterval(() => {
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send('ping');
      } else {
        clearInterval(pingInterval);
      }
    }, 30000);
  };

  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      if (data.type === 'pong') return;
      messageHandlers.forEach((handler) => handler(data));
    } catch (e) {
      console.warn('[WS] Invalid message:', event.data);
    }
  };

  ws.onclose = () => {
    isConnecting = false;
    console.log('[WS] Disconnected, reconnecting in 3s...');
    useStore.getState().setWsConnected(false);
    reconnectTimer = setTimeout(() => connectWebSocket(), 3000);
  };

  ws.onerror = (err) => {
    isConnecting = false;
    console.error('[WS] Error:', err);
    useStore.getState().setWsConnected(false);
  };
  } catch (error) {
    isConnecting = false;
    console.error('[WS] Failed to get ticket:', error);
    reconnectTimer = setTimeout(() => connectWebSocket(), 3000);
  }
}

export function disconnectWebSocket() {
  if (reconnectTimer) clearTimeout(reconnectTimer);
  if (ws) {
    useStore.getState().setWsConnected(false);
    ws.close();
    ws = null;
  }
  isConnecting = false;
}

export function onWebSocketMessage(handler) {
  messageHandlers.push(handler);
  return () => {
    messageHandlers = messageHandlers.filter((h) => h !== handler);
  };
}
