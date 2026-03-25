const BASE = '/api';

// Session token for authenticated mutating requests
let sessionToken: string | null = null;

async function ensureToken(): Promise<string> {
  if (!sessionToken) {
    const res = await fetch(`${BASE}/session`);
    if (res.ok) {
      const data = await res.json();
      sessionToken = data.token;
    }
  }
  return sessionToken ?? '';
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`);
  return res.json();
}

async function post<T>(path: string, body?: any): Promise<T> {
  const token = await ensureToken();
  const headers: Record<string, string> = { 'X-Session-Token': token };
  if (body) headers['Content-Type'] = 'application/json';
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`);
  return res.json();
}

async function put<T>(path: string, body: any): Promise<T> {
  const token = await ensureToken();
  const res = await fetch(`${BASE}${path}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json', 'X-Session-Token': token },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`);
  return res.json();
}

export const api = {
  gallery: () => get<any[]>('/gallery'),
  galleryItem: (id: string) => get<any>(`/gallery/${id}`),
  games: () => get<any>('/games'),
  settings: () => get<any>('/settings'),
  updateSettings: (s: any) => put<any>('/settings', s),
  profiles: () => get<any>('/profiles'),
  switchProfile: (name: string) => post<any>(`/profiles/${name}/switch`),
  openModlist: (path: string) => post<any>(`/modlist/open?wabbajack_path=${encodeURIComponent(path)}`),
  startInstall: (req: any) => post<any>('/install/start', req),
  installStatus: () => get<any>('/install/status'),
  nexusStatus: () => get<any>('/auth/nexus/status'),
  nexusLogin: () => get<any>('/auth/nexus/login'),
  nexusSsoStatus: () => get<any>('/auth/nexus/sso-status'),
  nexusSetKey: (key: string) => post<any>('/auth/nexus/key', { key }),
  nexusLogout: () => post<any>('/auth/nexus/logout'),
  checkUpdate: () => get<any>('/update/check'),
  applyUpdate: () => post<any>('/update/apply'),
  loadOrderSupported: () => get<any>('/loadorder/supported'),
  loadOrder: (gameType: string) => get<any>(`/loadorder/${gameType}`),
  saveLoadOrder: (gameType: string, data: any) => put<any>(`/loadorder/${gameType}`, data),
};
