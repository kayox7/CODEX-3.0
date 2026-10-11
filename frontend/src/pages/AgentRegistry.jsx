import React, { useEffect, useState } from 'react';
import { api } from '../api';
import {
  Bot, Plus, Pause, Play, Loader2, AlertCircle,
  CheckCircle2, ShieldX, RefreshCw, X, Shield
} from 'lucide-react';

const RISK_LEVELS = ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'];
const DATA_CLASSES = ['public', 'internal', 'confidential', 'restricted'];

function StatusBadge({ status }) {
  const map = {
    ACTIVE: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30',
    PAUSED: 'bg-rose-500/15 text-rose-400 border-rose-500/30',
    REVOKED: 'bg-slate-700 text-slate-400 border-slate-600',
  };
  return (
    <span className={`text-[10px] font-mono font-bold px-2 py-0.5 rounded-full border ${map[status] || 'bg-slate-700 text-slate-400 border-slate-600'}`}>
      {status}
    </span>
  );
}

function AgentCard({ agent, user, onAction }) {
  const [actionLoading, setActionLoading] = useState(null);
  const [reason, setReason] = useState('');
  const canControl = user?.role === 'admin' || user?.role === 'risk_officer';

  const handlePause = async () => {
    setActionLoading('pause');
    try {
      await api.pauseAgent(agent.id, reason || 'Kill switch activated from console');
      onAction();
    } catch (e) {
      alert(e.message);
    } finally {
      setActionLoading(null);
      setReason('');
    }
  };

  const handleResume = async () => {
    setActionLoading('resume');
    try {
      await api.resumeAgent(agent.id, reason || 'Resumed from console');
      onAction();
    } catch (e) {
      alert(e.message);
    } finally {
      setActionLoading(null);
      setReason('');
    }
  };

  return (
    <div className={`glass-panel rounded-xl p-5 transition ${agent.status === 'PAUSED' ? 'border-rose-500/20 glow-rose' : ''}`}>
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center space-x-3 min-w-0">
          <div className={`p-2 rounded-lg ${agent.status === 'ACTIVE' ? 'bg-emerald-500/10' : 'bg-rose-500/10'}`}>
            {agent.status === 'ACTIVE'
              ? <Bot className="w-5 h-5 text-emerald-400" />
              : <ShieldX className="w-5 h-5 text-rose-400" />
            }
          </div>
          <div className="min-w-0">
            <p className="font-bold text-white truncate">{agent.name}</p>
            <p className="text-[10px] text-slate-500 font-mono truncate">{agent.id}</p>
          </div>
        </div>
        <StatusBadge status={agent.status} />
      </div>

      <div className="grid grid-cols-2 gap-2 mb-4">
        <div className="bg-slate-900/60 rounded-lg px-3 py-2">
          <p className="text-[10px] text-slate-500 uppercase tracking-wider">Risk Level</p>
          <p className={`text-sm font-bold font-mono mt-0.5 ${
            agent.risk_level === 'CRITICAL' ? 'text-rose-400'
            : agent.risk_level === 'HIGH' ? 'text-orange-400'
            : agent.risk_level === 'MEDIUM' ? 'text-amber-400'
            : 'text-emerald-400'
          }`}>{agent.risk_level || '—'}</p>
        </div>
        <div className="bg-slate-900/60 rounded-lg px-3 py-2">
          <p className="text-[10px] text-slate-500 uppercase tracking-wider">Data Class</p>
          <p className="text-sm font-bold font-mono mt-0.5 text-violet-400">{agent.max_data_class || '—'}</p>
        </div>
      </div>

      {agent.allowed_actions?.length > 0 && (
        <div className="mb-4">
          <p className="text-[10px] text-slate-500 uppercase tracking-wider mb-1.5">Allowed Actions</p>
          <div className="flex flex-wrap gap-1.5">
            {agent.allowed_actions.slice(0, 6).map(a => (
              <span key={a} className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-800 text-slate-400 border border-slate-700">{a}</span>
            ))}
            {agent.allowed_actions.length > 6 && (
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-800 text-slate-500">+{agent.allowed_actions.length - 6} more</span>
            )}
          </div>
        </div>
      )}

      {canControl && (
        <div className="flex items-center space-x-2">
          <input
            type="text"
            placeholder="Reason (optional)"
            value={reason}
            onChange={e => setReason(e.target.value)}
            className="flex-1 text-xs bg-slate-900 border border-slate-700 rounded-lg px-3 py-1.5 text-slate-300 placeholder-slate-600 focus:outline-none focus:border-slate-600"
          />
          {agent.status === 'ACTIVE' ? (
            <button
              onClick={handlePause}
              disabled={actionLoading === 'pause'}
              className="flex items-center space-x-1.5 px-3 py-1.5 bg-rose-500/15 hover:bg-rose-500/25 text-rose-400 border border-rose-500/30 rounded-lg text-xs font-bold transition disabled:opacity-50"
            >
              {actionLoading === 'pause' ? <Loader2 className="w-3 h-3 animate-spin" /> : <Pause className="w-3 h-3" />}
              <span>Pause</span>
            </button>
          ) : agent.status === 'PAUSED' ? (
            <button
              onClick={handleResume}
              disabled={actionLoading === 'resume'}
              className="flex items-center space-x-1.5 px-3 py-1.5 bg-emerald-500/15 hover:bg-emerald-500/25 text-emerald-400 border border-emerald-500/30 rounded-lg text-xs font-bold transition disabled:opacity-50"
            >
              {actionLoading === 'resume' ? <Loader2 className="w-3 h-3 animate-spin" /> : <Play className="w-3 h-3" />}
              <span>Resume</span>
            </button>
          ) : null}
        </div>
      )}
    </div>
  );
}

function CreateAgentModal({ onClose, onCreated }) {
  const [form, setForm] = useState({
    name: '',
    risk_level: 'LOW',
    max_data_class: 'public',
    allowed_actions: '',
    owner_email: '',
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const payload = {
        ...form,
        allowed_actions: form.allowed_actions
          ? form.allowed_actions.split(',').map(s => s.trim()).filter(Boolean)
          : [],
      };
      await api.createAgent(payload);
      onCreated();
      onClose();
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const field = (label, key, type = 'text', placeholder = '') => (
    <div>
      <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1.5">{label}</label>
      <input
        type={type}
        value={form[key]}
        onChange={e => setForm(p => ({ ...p, [key]: e.target.value }))}
        placeholder={placeholder}
        className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white placeholder-slate-600 focus:outline-none focus:border-sky-500 transition"
      />
    </div>
  );

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
      <div className="glass-panel rounded-2xl w-full max-w-lg p-6">
        <div className="flex items-center justify-between mb-6">
          <h3 className="text-lg font-bold text-white flex items-center space-x-2">
            <Shield className="w-5 h-5 text-sky-400" />
            <span>Register Agent Passport</span>
          </h3>
          <button onClick={onClose} className="text-slate-500 hover:text-white transition">
            <X className="w-5 h-5" />
          </button>
        </div>
        <form onSubmit={handleSubmit} className="space-y-4">
          {field('Agent Name', 'name', 'text', 'e.g. refund-processor-v2')}
          {field('Owner Email', 'owner_email', 'email', 'owner@company.com')}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1.5">Risk Level</label>
              <select
                value={form.risk_level}
                onChange={e => setForm(p => ({ ...p, risk_level: e.target.value }))}
                className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-sky-500 transition"
              >
                {RISK_LEVELS.map(r => <option key={r} value={r}>{r}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1.5">Max Data Class</label>
              <select
                value={form.max_data_class}
                onChange={e => setForm(p => ({ ...p, max_data_class: e.target.value }))}
                className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-sky-500 transition"
              >
                {DATA_CLASSES.map(d => <option key={d} value={d}>{d}</option>)}
              </select>
            </div>
          </div>
          {field('Allowed Actions', 'allowed_actions', 'text', 'refund_order, read_customer (comma-separated)')}

          {error && (
            <div className="flex items-center space-x-2 text-rose-400 text-xs bg-rose-500/10 border border-rose-500/20 rounded-lg px-3 py-2">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}
          <div className="flex space-x-3 pt-2">
            <button type="button" onClick={onClose} className="flex-1 py-2.5 border border-slate-700 rounded-lg text-sm text-slate-400 hover:text-white hover:border-slate-600 transition">Cancel</button>
            <button type="submit" disabled={loading} className="flex-1 py-2.5 bg-sky-600 hover:bg-sky-500 disabled:opacity-50 text-white font-semibold rounded-lg text-sm transition flex items-center justify-center space-x-2">
              {loading && <Loader2 className="w-4 h-4 animate-spin" />}
              <span>{loading ? 'Registering...' : 'Register Agent'}</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default function AgentRegistry({ user }) {
  const [agents, setAgents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [filter, setFilter] = useState('ALL');

  const canCreate = user?.role === 'admin';

  const load = async () => {
    try {
      const data = await api.getAgents();
      setAgents(Array.isArray(data) ? data : []);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const filtered = filter === 'ALL' ? agents : agents.filter(a => a.status === filter);

  return (
    <div className="p-6 space-y-5 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h2 className="text-2xl font-extrabold text-white">Agent Registry</h2>
          <p className="text-slate-500 text-sm mt-0.5">Manage AI agent passports and kill switches</p>
        </div>
        <div className="flex items-center space-x-3">
          <button onClick={load} className="p-2 rounded-lg border border-slate-700 text-slate-400 hover:text-white hover:border-slate-600 transition">
            <RefreshCw className="w-4 h-4" />
          </button>
          {canCreate && (
            <button
              id="create-agent-btn"
              onClick={() => setShowCreate(true)}
              className="flex items-center space-x-2 px-4 py-2 bg-sky-600 hover:bg-sky-500 text-white font-semibold rounded-lg text-sm transition"
            >
              <Plus className="w-4 h-4" />
              <span>Register Agent</span>
            </button>
          )}
        </div>
      </div>

      {/* Filters */}
      <div className="flex space-x-2">
        {['ALL', 'ACTIVE', 'PAUSED', 'REVOKED'].map(s => (
          <button
            key={s}
            onClick={() => setFilter(s)}
            className={`px-3 py-1.5 text-xs font-mono font-bold rounded-lg border transition ${
              filter === s
                ? 'bg-sky-500/15 text-sky-400 border-sky-500/30'
                : 'text-slate-500 border-slate-800 hover:border-slate-700 hover:text-slate-400'
            }`}
          >
            {s} {s === 'ALL' ? `(${agents.length})` : `(${agents.filter(a => a.status === s).length})`}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-40">
          <Loader2 className="w-8 h-8 text-sky-400 animate-spin" />
        </div>
      ) : filtered.length === 0 ? (
        <div className="text-center py-16 text-slate-500">
          <Bot className="w-10 h-10 mx-auto mb-3 opacity-40" />
          <p>No agents found</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {filtered.map(agent => (
            <AgentCard key={agent.id} agent={agent} user={user} onAction={load} />
          ))}
        </div>
      )}

      {showCreate && (
        <CreateAgentModal onClose={() => setShowCreate(false)} onCreated={load} />
      )}
    </div>
  );
}
