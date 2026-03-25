import { writable } from 'svelte/store';

export interface WsMessage {
  type: string;
  [key: string]: any;
}

export const connected = writable(false);
export const logs = writable<WsMessage[]>([]);
export const progress = writable<WsMessage | null>(null);
export const installState = writable<WsMessage | null>(null);
export const manualDownloads = writable<WsMessage[]>([]);

let ws: WebSocket | null = null;
let reconnectTimer: ReturnType<typeof setInterval> | null = null;

export function connectWs() {
  if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) return;

  const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
  ws = new WebSocket(`${proto}//${location.host}/ws`);

  ws.onopen = () => {
    connected.set(true);
    if (reconnectTimer) { clearInterval(reconnectTimer); reconnectTimer = null; }
  };

  ws.onclose = () => {
    connected.set(false);
    if (!reconnectTimer) {
      reconnectTimer = setInterval(() => connectWs(), 3000);
    }
  };

  ws.onmessage = (event) => {
    let msg: WsMessage;
    try {
      msg = JSON.parse(event.data);
    } catch {
      return; // Drop malformed messages
    }
    switch (msg.type) {
      case 'log':
        logs.update(l => {
          l.push(msg);
          if (l.length > 50000) l.splice(0, l.length - 40000);
          return l;
        });
        break;
      case 'progress':
        progress.set(msg);
        break;
      case 'state':
        installState.set(msg);
        break;
      case 'manual_needed':
        manualDownloads.update(m => {
          if (m.some(d => d.name === msg.name)) return m; // Deduplicate
          return [...m, msg];
        });
        break;
      case 'manual_complete':
        manualDownloads.update(m => m.filter(d => d.name !== msg.name));
        break;
      case 'error':
        installState.set(msg);
        break;
    }
  };
}

export function sendWs(msg: WsMessage) {
  if (ws?.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify(msg));
  }
}

export function clearLogs() {
  logs.set([]);
}
