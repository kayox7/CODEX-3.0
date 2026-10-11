import React, { useEffect, useState } from 'react';
import { api } from '../api';
import {
  Bot, CheckSquare, FileCheck2, ShieldX, TrendingUp,
  Activity, Clock, AlertTriangle, Loader2
} from 'lucide-react';

function StatCard({ icon: Icon, label, value, color = 'text-sky-400', sub }) {
  return (
    <div className="glass-panel rounded-xl p-5 flex items-start space-x-4">
      <div className={`p-2.5 rounded-lg bg-slate-800/80 ${color}`}>
        <Icon className="w-5 h-5" />
      </div>
      <div>
        <p className="text-xs text-slate-500 uppercase tracking-wider font-mono">{label}</p>
        <p className={`text-2xl font-bold mt-0.5 ${color}`}>{value ?? '—'}</p>
        {sub && <p className="text-xs text-slate-500 mt-0.5">{sub}</p>}
      </div>
    </div>
  );
}

function DecisionBadge({ outcome }) {
  const map = {
    ALLOW: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30',
    PENDING_APPROVAL: 'bg-amber-500/15 text-amber-400 border-amber-500/30',
    DENY: 'bg-rose-500/15 text-rose-400 border-rose-500/30',
    HUMAN_ONLY: 'bg-violet-500/15 text-violet-400 border-violet-500/30',
    APPROVED: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30',
    REJECTED: 'bg-rose-500/15 text-rose-400 border-rose-500/30',
  };
  return (
    <span className={`text-[10px] font-mono font-bold px-2 py-0.5 rounded-full border ${map[outcome] || 'bg-slate-700 text-slate-300 border-slate-600'}`}>
      {outcome}
    </span>
  );
}

export default function Dashboard({ user, onSelectTab }) {
  const [agents, setAgents] = useState([]);
  const [ledger, setLedger] = useState([]);
  const [approvals, setApprovals] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      try {
        const [a, l, ap] = await Promise.all([
          api.getAgents(),
          api.getLedger(10),
          api.getApprovals({ status: 'PENDING_APPROVAL' }),
        ]);
        setAgents(Array.isArray(a) ? a : []);
        setLedger(Array.isArray(l) ? l : (l.items ?? []));
        setApprovals(Array.isArray(ap) ? ap : (ap.items ?? []));
      } catch (e) {
        console.error(e);
      } finally {
        setLoading(false);
      }
    };
    load();
    const iv = setInterval(load, 20000);
    return () => clearInterval(iv);
  }, []);

  const activeAgents = agents.filter(a => a.status === 'ACTIVE').length;
  const pausedAgents = agents.filter(a => a.status === 'PAUSED').length;
  const pendingApprovals = approvals.length;

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-8 h-8 text-sky-400 animate-spin" />
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-extrabold text-white">Governance Dashboard</h2>
          <p className="text-slate-500 text-sm mt-0.5">
            Logged in as <span className="text-sky-400 font-mono">{user?.username}</span>
            {' '}· <span className="text-amber-400 font-mono uppercase">{user?.role}</span>
          </p>
        </div>
        <div className="flex items-center space-x-2 text-xs text-emerald-400 font-mono bg-emerald-500/10 border border-emerald-500/20 px-3 py-1.5 rounded-full">
          <Activity className="w-3 h-3" />
          <span>SYSTEM OPERATIONAL</span>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard icon={Bot} label="Active Agents" value={activeAgents} color="text-sky-400" />
        <StatCard icon={ShieldX} label="Paused Agents" value={pausedAgents} color="text-rose-400" />
        <StatCard
          icon={CheckSquare}
          label="Pending Approvals"
          value={pendingApprovals}
          color="text-amber-400"
          sub={pendingApprovals > 0 ? 'Require human review' : 'Queue clear'}
        />
        <StatCard icon={FileCheck2} label="Ledger Entries" value={ledger.length > 0 ? '∞' : '0'} color="text-violet-400" sub="Append-only chain" />
      </div>

      {/* Quick actions */}
      {pendingApprovals > 0 && (
        <div className="flex items-center space-x-4 bg-amber-500/10 border border-amber-500/20 rounded-xl p-4">
          <AlertTriangle className="w-5 h-5 text-amber-400 shrink-0" />
          <div className="flex-1">
            <p className="text-amber-300 font-semibold text-sm">
              {pendingApprovals} approval{pendingApprovals > 1 ? 's' : ''} awaiting human review
            </p>
            <p className="text-amber-400/60 text-xs">SLA countdown active. Unreviewed actions will be denied automatically.</p>
          </div>
          <button
            onClick={() => onSelectTab('approvals')}
            className="px-4 py-2 text-xs font-bold rounded-lg bg-amber-500/20 text-amber-300 hover:bg-amber-500/30 border border-amber-500/30 transition"
          >
            Review Now →
          </button>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Recent Ledger */}
        <div className="glass-panel rounded-xl p-5">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-bold text-sm text-white">Recent Ledger Events</h3>
            <button onClick={() => onSelectTab('ledger')} className="text-xs text-sky-400 hover:text-sky-300">View all →</button>
          </div>
          <div className="space-y-2">
            {ledger.slice(0, 6).map(entry => (
              <div key={entry.id} className="flex items-center justify-between py-2 border-b border-slate-800/60 last:border-0">
                <div className="min-w-0 flex-1">
                  <p className="text-xs text-slate-300 font-mono truncate">{entry.event_type}</p>
                  <p className="text-[10px] text-slate-500 truncate">{entry.agent_id || 'system'}</p>
                </div>
                <DecisionBadge outcome={entry.outcome || entry.event_type} />
              </div>
            ))}
            {ledger.length === 0 && <p className="text-xs text-slate-500 text-center py-4">No ledger entries yet</p>}
          </div>
        </div>

        {/* Agent Status */}
        <div className="glass-panel rounded-xl p-5">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-bold text-sm text-white">Agent Passports</h3>
            <button onClick={() => onSelectTab('agents')} className="text-xs text-sky-400 hover:text-sky-300">Manage →</button>
          </div>
          <div className="space-y-2">
            {agents.slice(0, 6).map(agent => (
              <div key={agent.id} className="flex items-center justify-between py-2 border-b border-slate-800/60 last:border-0">
                <div className="min-w-0 flex-1">
                  <p className="text-xs text-slate-200 font-semibold truncate">{agent.name}</p>
                  <p className="text-[10px] text-slate-500 font-mono truncate">{agent.id}</p>
                </div>
                <span className={`text-[10px] font-mono font-bold px-2 py-0.5 rounded-full border ${
                  agent.status === 'ACTIVE'
                    ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30'
                    : agent.status === 'PAUSED'
                    ? 'bg-rose-500/15 text-rose-400 border-rose-500/30'
                    : 'bg-slate-700 text-slate-400 border-slate-600'
                }`}>
                  {agent.status}
                </span>
              </div>
            ))}
            {agents.length === 0 && <p className="text-xs text-slate-500 text-center py-4">No agents registered</p>}
          </div>
        </div>
      </div>
    </div>
  );
}
