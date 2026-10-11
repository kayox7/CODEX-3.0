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

export class ApiError extends Error {
  constructor(message, status, fieldErrors = {}, rawDetail = null) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.fieldErrors = fieldErrors || {};
    this.detail = rawDetail;
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
    let message = `Request failed with status ${res.status}`;
    const fieldErrors = {};

    if (Array.isArray(errorData.detail)) {
      const parts = errorData.detail.map(item => {
        if (typeof item === 'object' && item !== null) {
          const field = Array.isArray(item.loc) && item.loc.length > 0
            ? String(item.loc[item.loc.length - 1])
            : 'field';
          const msg = item.msg ? item.msg.toLowerCase() : 'field required';
          fieldErrors[field] = item.msg || 'Field required';
          return `${field}: ${msg}`;
        }
        return String(item);
      });
      message = parts.join('; ');
    } else if (typeof errorData.detail === 'string') {
      message = errorData.detail;
      if (message.toLowerCase().includes('reason')) {
        fieldErrors['reason'] = message;
      }
    } else if (errorData.detail && typeof errorData.detail === 'object') {
      message = JSON.stringify(errorData.detail);
    }

    throw new ApiError(message, res.status, fieldErrors, errorData.detail);
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
    const res = await request(`/agents/${agentId}/pause`, {
      method: 'POST',
      body: JSON.stringify({ reason: reason || 'Manual pause from console' })
    });
    window.dispatchEvent(new CustomEvent('warden_data_changed'));
    return res;
  },

  async resumeAgent(agentId, reason) {
    const res = await request(`/agents/${agentId}/resume`, {
      method: 'POST',
      body: JSON.stringify({ reason: reason || 'Manual resume from console' })
    });
    window.dispatchEvent(new CustomEvent('warden_data_changed'));
    return res;
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
    const res = await request(`/approvals/${id}/approve`, {
      method: 'POST',
      body: JSON.stringify({ reason })
    });
    window.dispatchEvent(new CustomEvent('warden_data_changed'));
    return res;
  },

  async reject(id, reason) {
    const res = await request(`/approvals/${id}/reject`, {
      method: 'POST',
      body: JSON.stringify({ reason })
    });
    window.dispatchEvent(new CustomEvent('warden_data_changed'));
    return res;
  },

  // System
  async getHealth() {
    return request('/health');
  },

  // Ledger
  async getLedger(params = 50, offset = 0) {
    let p = {};
    if (typeof params === 'number') {
      p = { limit: params, offset: offset || 0 };
    } else if (params && typeof params === 'object') {
      p = { ...params };
    }
    const query = new URLSearchParams();
    if (p.limit !== undefined) query.set('limit', p.limit);
    if (p.offset !== undefined) query.set('offset', p.offset);
    if (p.q) query.set('q', p.q);
    if (p.event_type) query.set('event_type', p.event_type);
    if (p.agent_id) query.set('agent_id', p.agent_id);
    if (p.risk_level) query.set('risk_level', p.risk_level);
    if (p.from) query.set('from', p.from);
    if (p.to) query.set('to', p.to);
    const qs = query.toString();
    return request(`/v1/ledger${qs ? `?${qs}` : ''}`);
  },

  async getLedgerCount() {
    return request('/v1/ledger/count');
  },

  async getLedgerProof(id) {
    return request(`/v1/ledger/proof/${id}`);
  },

  async verifyLedger() {
    return request('/v1/ledger/verify');
  },

  async tamperLedger(id, note) {
    return request(`/v1/ledger/_tamper/${id}`, {
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
