const API_BASE = 'http://127.0.0.1:8000';

export function getToken() {
  return localStorage.getItem('warden_jwt');
}

export function setToken(token) {
  if (token) {
    localStorage.setItem('warden_jwt', token);
  } else {
    localStorage.removeItem('warden_jwt');
  }
}

export function getCurrentUser() {
  const user = localStorage.getItem('warden_user');
  try {
    return user ? JSON.parse(user) : null;
  } catch {
    return null;
  }
}

export function setCurrentUser(user) {
  if (user) {
    localStorage.setItem('warden_user', JSON.stringify(user));
  } else {
    localStorage.removeItem('warden_user');
  }
}

async function request(endpoint, options = {}) {
  const url = `${API_BASE}${endpoint}`;
  const headers = {
    'Content-Type': 'application/json',
    ...(options.headers || {})
  };

  const token = getToken();
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const res = await fetch(url, { ...options, headers });
  
  if (res.status === 401) {
    // Session expired or unauthenticated
    setToken(null);
    setCurrentUser(null);
    if (!endpoint.includes('/auth/login')) {
      window.dispatchEvent(new CustomEvent('warden_auth_expired'));
    }
  }

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(errorData.detail || `Request failed with status ${res.status}`);
  }

  return res.json();
}

export const api = {
  // Auth
  async login(username, password) {
    const data = await request('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ username, password })
    });
    setToken(data.access_token);
    setCurrentUser(data.user);
    return data;
  },

  async getMe() {
    return request('/auth/me');
  },

  logout() {
    setToken(null);
    setCurrentUser(null);
  },

  // Agents
  async getAgents() {
    return request('/agents');
  },

  async createAgent(agentData) {
    return request('/agents', {
      method: 'POST',
      body: JSON.stringify(agentData)
    });
  },

  async pauseAgent(agentId, reason) {
    return request(`/agents/${agentId}/pause`, {
      method: 'POST',
      body: JSON.stringify({ reason: reason || 'Manual pause from console' })
    });
  },

  async resumeAgent(agentId, reason) {
    return request(`/agents/${agentId}/resume`, {
      method: 'POST',
      body: JSON.stringify({ reason: reason || 'Manual resume from console' })
    });
  },

  // Approvals
  async getApprovals(params = {}) {
    const query = new URLSearchParams();
    if (params.status) query.set('status', params.status);
    if (params.mine) query.set('mine', 'true');
    const qs = query.toString();
    return request(`/approvals${qs ? `?${qs}` : ''}`);
  },

  async getApproval(id) {
    return request(`/approvals/${id}`);
  },

  async approve(id, reason) {
    return request(`/approvals/${id}/approve`, {
      method: 'POST',
      body: JSON.stringify({ reason })
    });
  },

  async reject(id, reason) {
    return request(`/approvals/${id}/reject`, {
      method: 'POST',
      body: JSON.stringify({ reason })
    });
  },

  // Ledger
  async getLedger(limit = 50, offset = 0) {
    return request(`/ledger?limit=${limit}&offset=${offset}`);
  },

  async verifyLedger() {
    return request('/ledger/verify');
  },

  async tamperLedger(id, note) {
    return request(`/ledger/_tamper/${id}`, {
      method: 'POST',
      body: JSON.stringify({ note: note || 'Simulated tamper test' })
    });
  },

  // Audit Report
  getAuditReportUrl(format = 'csv') {
    const token = getToken();
    return `${API_BASE}/reports/audit?format=${format}&token=${token || ''}`;
  }
};
