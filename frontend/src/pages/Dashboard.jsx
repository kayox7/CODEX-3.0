import React, { useEffect, useState, useCallback, useRef } from 'react';
import { api } from '../api';
import {
  Bot, CheckSquare, FileCheck2, ShieldX, TrendingUp,
  Activity, Clock, AlertTriangle, Loader2, RefreshCw
} from 'lucide-react';
import { computeDashboardStats, formatCounterValue } from '../utils/dashboardStats';

function StatCard({ icon: Icon, label, value, loading, color = 'text-sky-400', sub }) {
  return (
    <div className="glass-panel rounded-xl p-5 flex items-start space-x-4 border border-slate-800/80 hover:border-slate-700/80 transition-all duration-200">
      <div className={`p-2.5 rounded-lg bg-slate-800/80 ${color} shrink-0`}>
        <Icon className="w-5 h-5" />
      </div>
      <div className="min-w-0 flex-1">
        <p className="text-xs text-slate-500 uppercase tracking-wider font-mono truncate">{label}</p>
        <p className={`text-2xl font-bold mt-0.5 tracking-tight ${color}`}>
          {loading ? (
            <span className="inline-block w-10 h-7 bg-slate-700/50 rounded animate-pulse" />
          ) : (
            formatCounterValue(value)
          )}
        </p>
        {sub && <p className="text-xs text-slate-500 mt-0.5 truncate">{sub}</p>}
      </div>
    </div>
  );
}

function DecisionBadge({ outcome }) {
  const norm = (outcome || '').toUpperCase();
  const map = {
    ALLOW: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30',
    ACTION_ALLOWED: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30',
    PENDING_APPROVAL: 'bg-amber-500/15 text-amber-400 border-amber-500/30',
    APPROVAL_REQUESTED: 'bg-amber-500/15 text-amber-400 border-amber-500/30',
    DENY: 'bg-rose-500/15 text-rose-400 border-rose-500/30',
    BLOCKED: 'bg-rose-500/15 text-rose-400 border-rose-500/30',
    ACTION_BLOCKED: 'bg-rose-500/15 text-rose-400 border-rose-500/30',
    HUMAN_ONLY: 'bg-violet-500/15 text-violet-400 border-violet-500/30',
    APPROVED: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30',
    ACTION_APPROVED: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30',
    REJECTED: 'bg-rose-500/15 text-rose-400 border-rose-500/30',
    ACTION_REJECTED: 'bg-rose-500/15 text-rose-400 border-rose-500/30',
    AGENT_REGISTERED: 'bg-sky-500/15 text-sky-400 border-sky-500/30',
    AGENT_PAUSED: 'bg-rose-500/15 text-rose-400 border-rose-500/30',
    AGENT_RESUMED: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30',
    KILL_SWITCH_TRIGGERED: 'bg-red-500/20 text-red-400 border-red-500/40'
  };

  return (
    <span className={`text-[10px] font-mono font-bold px-2 py-0.5 rounded-full border ${map[norm] || 'bg-slate-700 text-slate-300 border-slate-600'}`}>
      {norm}
    </span>
  );
}

export default function Dashboard({ user, onSelectTab }) {
  const [agents, setAgents] = useState([]);
  const [ledgerEntries, setLedgerEntries] = useState([]);
  const [ledgerTotal, setLedgerTotal] = useState(0);
  const [approvals, setApprovals] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [lastRefreshedAt, setLastRefreshedAt] = useState(null);

  const isMountedRef = useRef(true);

  const loadData = useCallback(async (isManual = false) => {
    if (isManual) setRefreshing(true);
    try {
      // Parallel requests for agents, ledger (items + total count), and approvals
      const [agentsRes, ledgerRes, approvalsRes] = await Promise.all([
        api.getAgents(),
        api.getLedger(10),
        api.getApprovals(),
      ]);

      if (!isMountedRef.current) return;

      const safeAgents = Array.isArray(agentsRes) ? agentsRes : (agentsRes?.items ?? []);
      const safeLedgerItems = Array.isArray(ledgerRes) ? ledgerRes : (ledgerRes?.items ?? []);
      const safeLedgerTotal = typeof ledgerRes?.total === 'number'
        ? ledgerRes.total
        : (Array.isArray(ledgerRes) ? ledgerRes.length : safeLedgerItems.length);
      const safeApprovals = Array.isArray(approvalsRes) ? approvalsRes : (approvalsRes?.items ?? []);

      setAgents(safeAgents);
      setLedgerEntries(safeLedgerItems);
      setLedgerTotal(safeLedgerTotal);
      setApprovals(safeApprovals);
      setLastRefreshedAt(new Date());
    } catch (e) {
      console.error('[WARDEN Dashboard] Error loading dashboard data:', e);
    } finally {
      if (isMountedRef.current) {
        setLoading(false);
        setRefreshing(false);
      }
    }
  }, []);

  useEffect(() => {
    isMountedRef.current = true;
    loadData();

    // 1. Refresh counters every 10 seconds
    const intervalId = setInterval(() => {
      loadData();
    }, 10000);

    // 2. Refresh immediately after pause, resume, approve, or reject
    const handleDataChanged = () => {
      loadData();
    };

    window.addEventListener('warden_data_changed', handleDataChanged);
    document.addEventListener('visibilitychange', () => {
      if (document.visibilityState === 'visible') {
        loadData();
      }
    });

    return () => {
      isMountedRef.current = false;
      clearInterval(intervalId);
      window.removeEventListener('warden_data_changed', handleDataChanged);
    };
  }, [loadData]);

  // Compute live counters from current data
  const stats = computeDashboardStats(agents, { total: ledgerTotal, items: ledgerEntries }, approvals);

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center h-64 space-y-3">
        <Loader2 className="w-8 h-8 text-sky-400 animate-spin" />
        <p className="text-xs text-slate-500 font-mono">Synchronizing governance metrics...</p>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-2xl font-extrabold text-white tracking-tight">Governance Dashboard</h2>
          <p className="text-slate-500 text-sm mt-0.5">
            Logged in as <span className="text-sky-400 font-mono">{user?.username}</span>
            {' '}· <span className="text-amber-400 font-mono uppercase">{user?.role}</span>
          </p>
        </div>
        <div className="flex items-center space-x-3">
          <button
            onClick={() => loadData(true)}
            disabled={refreshing}
            className="flex items-center space-x-1.5 text-xs text-slate-400 hover:text-white bg-slate-800/80 hover:bg-slate-800 border border-slate-700/80 px-3 py-1.5 rounded-lg transition"
            title="Refresh metrics now"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? 'animate-spin text-sky-400' : ''}`} />
            <span>{refreshing ? 'Syncing...' : 'Sync'}</span>
          </button>
          <div className="flex items-center space-x-2 text-xs text-emerald-400 font-mono bg-emerald-500/10 border border-emerald-500/20 px-3 py-1.5 rounded-full">
            <Activity className="w-3 h-3 animate-pulse" />
            <span>SYSTEM OPERATIONAL</span>
          </div>
        </div>
      </div>

      {/* Top Governance Counters */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          icon={Bot}
          label="Active Agents"
          value={stats.activeAgents}
          color="text-sky-400"
          sub={stats.totalAgents > 0 ? `${stats.totalAgents} total registered` : 'No agents'}
        />
        <StatCard
          icon={ShieldX}
          label="Paused Agents"
          value={stats.pausedAgents}
          color="text-rose-400"
          sub={stats.revokedAgents > 0 ? `${stats.revokedAgents} revoked` : (stats.pausedAgents > 0 ? 'Controls enforced' : 'None paused')}
        />
        <StatCard
          icon={CheckSquare}
          label="Pending Approvals"
          value={stats.pendingApprovals}
          color="text-amber-400"
          sub={stats.pendingApprovals > 0 ? 'Require human review' : 'Queue clear'}
        />
        <StatCard
          icon={FileCheck2}
          label="Ledger Entries"
          value={stats.ledgerTotal}
          color="text-violet-400"
          sub="Tamper-evident chain"
        />
      </div>

      {/* Quick Action Banner for Pending Reviews */}
      {stats.pendingApprovals > 0 && (
        <div className="flex items-center space-x-4 bg-amber-500/10 border border-amber-500/20 rounded-xl p-4">
          <AlertTriangle className="w-5 h-5 text-amber-400 shrink-0" />
          <div className="flex-1 min-w-0">
            <p className="text-amber-300 font-semibold text-sm">
              {stats.pendingApprovals} approval{stats.pendingApprovals > 1 ? 's' : ''} awaiting human review
            </p>
            <p className="text-amber-400/70 text-xs mt-0.5">
              Blast radius thresholds exceeded. Unreviewed actions will be denied upon SLA deadline.
            </p>
          </div>
          <button
            onClick={() => onSelectTab('approvals')}
            className="px-4 py-2 text-xs font-bold rounded-lg bg-amber-500/20 text-amber-300 hover:bg-amber-500/30 border border-amber-500/30 transition shrink-0"
          >
            Review Now →
          </button>
        </div>
      )}

      {/* Grid: Recent Ledger & Agent Passports */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Recent Ledger */}
        <div className="glass-panel rounded-xl p-5 border border-slate-800/80">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="font-bold text-sm text-white">Recent Ledger Events</h3>
              <p className="text-[11px] text-slate-500 font-mono">Latest tamper-evident audit trail</p>
            </div>
            <button
              onClick={() => onSelectTab('ledger')}
              className="text-xs text-sky-400 hover:text-sky-300 transition"
            >
              View all →
            </button>
          </div>
          <div className="space-y-2">
            {ledgerEntries.slice(0, 6).map(entry => (
              <div key={entry.id} className="flex items-center justify-between py-2 border-b border-slate-800/60 last:border-0">
                <div className="min-w-0 flex-1 pr-3">
                  <p className="text-xs text-slate-300 font-mono truncate">{entry.event_type}</p>
                  <p className="text-[10px] text-slate-500 truncate font-mono">
                    {entry.actor || entry.payload?.agent_id || 'system'}
                  </p>
                </div>
                <DecisionBadge outcome={entry.payload?.decision || entry.event_type} />
              </div>
            ))}
            {ledgerEntries.length === 0 && (
              <p className="text-xs text-slate-500 text-center py-6">No ledger entries recorded yet</p>
            )}
          </div>
        </div>

        {/* Agent Passports List */}
        <div className="glass-panel rounded-xl p-5 border border-slate-800/80">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="font-bold text-sm text-white">Agent Passports</h3>
              <p className="text-[11px] text-slate-500 font-mono">Registered AI agents ({agents.length})</p>
            </div>
            <button
              onClick={() => onSelectTab('agents')}
              className="text-xs text-sky-400 hover:text-sky-300 transition"
            >
              Manage →
            </button>
          </div>
          <div className="space-y-2">
            {agents.slice(0, 6).map(agent => {
              const statusLower = String(agent.status || '').trim().toLowerCase();
              const statusDisplay = (agent.status || 'UNKNOWN').toUpperCase();

              const badgeColor =
                statusLower === 'active'
                  ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30'
                  : statusLower === 'paused'
                  ? 'bg-rose-500/15 text-rose-400 border-rose-500/30'
                  : statusLower === 'revoked'
                  ? 'bg-amber-500/15 text-amber-400 border-amber-500/30'
                  : 'bg-slate-700 text-slate-400 border-slate-600';

              return (
                <div key={agent.id || agent.agent_id} className="flex items-center justify-between py-2 border-b border-slate-800/60 last:border-0">
                  <div className="min-w-0 flex-1 pr-3">
                    <p className="text-xs text-slate-200 font-semibold truncate">{agent.name}</p>
                    <p className="text-[10px] text-slate-500 font-mono truncate">{agent.agent_id || agent.id}</p>
                  </div>
                  <span className={`text-[10px] font-mono font-bold px-2 py-0.5 rounded-full border ${badgeColor}`}>
                    {statusDisplay}
                  </span>
                </div>
              );
            })}
            {agents.length === 0 && (
              <p className="text-xs text-slate-500 text-center py-6">No agents registered</p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
