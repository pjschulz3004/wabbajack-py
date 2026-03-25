const BASE = '/api';

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`);
  return res.json();
}

async function post<T>(path: string, body?: any): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: body ? { 'Content-Type': 'application/json' } : {},
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`);
  return res.json();
}

async function put<T>(path: string, body: any): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
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
  nexusSetKey: (key: string) => post<any>(`/auth/nexus/key?key=${encodeURIComponent(key)}`),
  nexusLogout: () => post<any>('/auth/nexus/logout'),
};
