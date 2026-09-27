/**
 * API helper — fetch wrappers for the SYNAPSE backend.
 * Supports VITE_API_BASE_URL for cross-origin backend deployments (e.g. Render).
 * In local dev without env var, relative paths are proxied by Vite.
 */

export const API_BASE = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/+$/, '');

const TOKEN_KEY = 'synapse_auth_token';

// ── Token Storage Helpers ────────────────────────────────────

export function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token) {
  if (token) {
    localStorage.setItem(TOKEN_KEY, token);
  } else {
    localStorage.removeItem(TOKEN_KEY);
  }
}

export function clearToken() {
  localStorage.removeItem(TOKEN_KEY);
}

export function getAuthHeaders(extraHeaders = {}) {
  const token = getToken();
  return {
    ...extraHeaders,
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
}

// ── Authentication API ───────────────────────────────────────

export async function register(email, password, username = '', fullName = '') {
  const res = await fetch(`${API_BASE}/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      email,
      password,
      username: username || undefined,
      full_name: fullName || undefined,
    }),
  });
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.detail || 'Registration failed');
  }
  if (data.access_token) {
    setToken(data.access_token);
  }
  return data;
}

export async function login(email, password) {
  const res = await fetch(`${API_BASE}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  });
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.detail || 'Invalid email or password');
  }
  if (data.access_token) {
    setToken(data.access_token);
  }
  return data;
}

export async function fetchCurrentUser() {
  const token = getToken();
  if (!token) return null;
  try {
    const res = await fetch(`${API_BASE}/auth/me`, {
      headers: getAuthHeaders(),
    });
    if (!res.ok) {
      if (res.status === 401) {
        clearToken();
      }
      return null;
    }
    const data = await res.json();
    return data.user || null;
  } catch {
    return null;
  }
}

export async function logout() {
  try {
    await fetch(`${API_BASE}/auth/logout`, {
      method: 'POST',
      headers: getAuthHeaders(),
    });
  } catch (e) {
    console.warn('Logout network error:', e);
  } finally {
    clearToken();
  }
}

// ── Legacy & Unified History ─────────────────────────────────

export async function fetchHistory() {
  const res = await fetch(`${API_BASE}/history`, {
    headers: getAuthHeaders(),
  });
  if (!res.ok) throw new Error('Failed to load history');
  return res.json();
}

export async function fetchHistoryEntry(id) {
  const res = await fetch(`${API_BASE}/history/${id}`, {
    headers: getAuthHeaders(),
  });
  if (!res.ok) throw new Error('Entry not found or access forbidden');
  return res.json();
}

export async function deleteHistoryEntry(id) {
  const res = await fetch(`${API_BASE}/history/${id}`, {
    method: 'DELETE',
    headers: getAuthHeaders(),
  });
  if (!res.ok) throw new Error('Delete failed or unauthorized');
  return res.json();
}

// ── Persistent Research Workspace Projects & Sessions ────────

export async function fetchProjects() {
  const res = await fetch(`${API_BASE}/projects`, {
    headers: getAuthHeaders(),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || 'Failed to load projects');
  }
  return res.json();
}

export async function createProject(title, description = '') {
  const res = await fetch(`${API_BASE}/projects`, {
    method: 'POST',
    headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify({ title, description }),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || 'Failed to create project');
  return data;
}

export async function fetchProject(projectId) {
  const res = await fetch(`${API_BASE}/projects/${projectId}`, {
    headers: getAuthHeaders(),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || 'Project not found');
  return data;
}

export async function deleteProject(projectId) {
  const res = await fetch(`${API_BASE}/projects/${projectId}`, {
    method: 'DELETE',
    headers: getAuthHeaders(),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || 'Failed to delete project');
  return data;
}

export async function fetchProjectSessions(projectId) {
  const res = await fetch(`${API_BASE}/projects/${projectId}/sessions`, {
    headers: getAuthHeaders(),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || 'Failed to load project sessions');
  return data;
}

export async function createProjectSession(projectId, topic, sessionName = '') {
  const res = await fetch(`${API_BASE}/projects/${projectId}/sessions`, {
    method: 'POST',
    headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify({ topic, session_name: sessionName }),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || 'Failed to create project session');
  return data;
}

export async function fetchSessionDetails(sessionId) {
  const res = await fetch(`${API_BASE}/sessions/${sessionId}`, {
    headers: getAuthHeaders(),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || 'Session not found');
  return data;
}

export async function deleteSession(sessionId) {
  const res = await fetch(`${API_BASE}/sessions/${sessionId}`, {
    method: 'DELETE',
    headers: getAuthHeaders(),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || 'Failed to delete session');
  return data;
}

export async function fetchSessionReports(sessionId) {
  const res = await fetch(`${API_BASE}/sessions/${sessionId}/reports`, {
    headers: getAuthHeaders(),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || 'Failed to load reports');
  return data;
}

export async function fetchSessionTelemetry(sessionId) {
  try {
    const res = await fetch(`${API_BASE}/sessions/${sessionId}/telemetry`, {
      headers: getAuthHeaders(),
    });
    if (res.ok) return await res.json();
  } catch (err) {
    console.warn('Session telemetry endpoint failed, trying history fallback', err);
  }

  try {
    const res2 = await fetch(`${API_BASE}/history/${sessionId}/telemetry`, {
      headers: getAuthHeaders(),
    });
    if (res2.ok) return await res2.json();
  } catch (err2) {
    console.warn('History telemetry endpoint failed', err2);
  }
  return null;
}

// ── Document Export & Session Dossier ────────────────────────

function normalizeExportPayload(arg1, arg2) {
  if (typeof arg1 === 'object' && arg1 !== null && !Array.isArray(arg1)) {
    const rawClaims = Array.isArray(arg1.claims)
      ? arg1.claims
      : (arg1.claims?.claims || arg1.claims?.items || []);
    const rawSources = Array.isArray(arg1.sources)
      ? arg1.sources
      : (arg1.sources?.sources || arg1.sources?.items || []);

    return {
      report: arg1.report || '',
      topic: arg1.topic || 'Research Report',
      session_id: arg1.sessionId || arg1.session_id,
      structured_data: arg1.structuredData || arg1.structured_data,
      claims: rawClaims,
      sources: rawSources,
    };
  }
  return {
    report: arg1 || '',
    topic: arg2 || 'Research Report',
  };
}

export async function downloadPdf(arg1, arg2) {
  const payload = normalizeExportPayload(arg1, arg2);
  const res = await fetch(`${API_BASE}/download-pdf`, {
    method: 'POST',
    headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error('PDF download failed');
  return res.blob();
}

export async function downloadDocx(arg1, arg2) {
  const payload = normalizeExportPayload(arg1, arg2);
  const res = await fetch(`${API_BASE}/download-docx`, {
    method: 'POST',
    headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error('Word (.docx) download failed');
  return res.blob();
}

export async function downloadMarkdown(arg1, arg2) {
  const payload = normalizeExportPayload(arg1, arg2);
  const res = await fetch(`${API_BASE}/download-markdown`, {
    method: 'POST',
    headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error('Markdown download failed');
  return res.blob();
}

export async function fetchStructuredReport(sessionId) {
  const res = await fetch(`${API_BASE}/sessions/${sessionId}/structured-report`, {
    headers: getAuthHeaders(),
  });
  if (!res.ok) throw new Error('Failed to fetch structured report');
  return await res.json();
}

export async function fetchSessionDossier(sessionId) {
  try {
    const res = await fetch(`${API_BASE}/sessions/${sessionId}/dossier`, {
      headers: getAuthHeaders(),
    });
    if (res.ok) return await res.json();
  } catch (err) {
    console.warn('Session dossier endpoint failed, trying history endpoint', err);
  }

  const res2 = await fetch(`${API_BASE}/history/${sessionId}/dossier`, {
    headers: getAuthHeaders(),
  });
  if (!res2.ok) throw new Error('Failed to export session dossier');
  return await res2.json();
}

export function triggerDownload(content, filename, mimeType = 'text/markdown;charset=utf-8') {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

