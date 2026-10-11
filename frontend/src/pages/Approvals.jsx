import React, { useEffect, useState, useCallback } from 'react';
import { api } from '../api';
import {
  CheckSquare, XCircle, Clock, Loader2, ChevronDown,
  ChevronUp, AlertTriangle, RefreshCw, FileText, User
} from 'lucide-react';

function SlaCountdown({ expiresAt }) {
  const [remaining, setRemaining] = useState(null);

  useEffect(() => {
    if (!expiresAt) return;
    const calc = () => {
      const diff = Math.floor((new Date(expiresAt) - Date.now()) / 1000);
      setRemaining(diff);
    };
    calc();
    const iv = setInterval(calc, 1000);
    return () => clearInterval(iv);
  }, [expiresAt]);

  if (remaining === null) return null;

  const isUrgent = remaining < 60;
  const isExpired = remaining <= 0;

  const fmt = (s) => {
    if (s <= 0) return 'EXPIRED';
    const m = Math.floor(s / 60);
    const sec = s % 60;
    return m > 0 ? `${m}m ${sec}s` : `${sec}s`;
  };

  return (
    <span className={`flex items-center space-x-1 text-xs font-mono font-bold ${
      isExpired ? 'text-rose-400' : isUrgent ? 'text-amber-400 animate-pulse' : 'text-slate-400'
    }`}>
      <Clock className="w-3 h-3" />
      <span>{fmt(remaining)}</span>
    </span>
  );
}

function OutcomeBadge({ status }) {
  const map = {
    PENDING_APPROVAL: 'bg-amber-500/15 text-amber-400 border-amber-500/30',
    APPROVED: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30',
    REJECTED: 'bg-rose-500/15 text-rose-400 border-rose-500/30',
    ESCALATED: 'bg-violet-500/15 text-violet-400 border-violet-500/30',
    TIMED_OUT: 'bg-slate-700 text-slate-400 border-slate-600',
  };
  return (
    <span className={`text-[10px] font-mono font-bold px-2 py-0.5 rounded-full border ${map[status] || 'bg-slate-700 text-slate-400 border-slate-600'}`}>
      {status}
    </span>
  );
}

function ApprovalCard({ approval, user, onAction }) {
  const [expanded, setExpanded] = useState(false);
  const [reason, setReason] = useState('');
  const [loading, setLoading] = useState(null);
  const [actionError, setActionError] = useState('');

  const canAct = user?.role !== 'auditor';

  const isPending = approval.status === 'PENDING_APPROVAL' || approval.status === 'ESCALATED';

  const handleApprove = async () => {
    setActionError('');
    setLoading('approve');
    try {
      await api.approve(approval.id, reason || 'Approved from console');
      onAction();
    } catch (e) {
      setActionError(e.message || 'Failed to approve request');
    } finally {
      setLoading(null);
    }
  };

  const handleReject = async () => {
    setActionError('');
    if (!reason.trim()) {
      setActionError('Rejection reason is required');
      return;
    }
    setLoading('reject');
    try {
      await api.reject(approval.id, reason.trim());
      onAction();
    } catch (e) {
      setActionError(e.message || 'Failed to reject request');
    } finally {
      setLoading(null);
    }
  };

  const evidence = approval.evidence_pack || {};
  const riskScore = evidence.risk_score;

  return (
    <div className={`glass-panel rounded-xl overflow-hidden transition ${isPending ? '' : 'opacity-70'}`}>
      <div className="p-5">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0 flex-1">
            <div className="flex items-center space-x-2 flex-wrap gap-1">
              <OutcomeBadge status={approval.status} />
              {isPending && <SlaCountdown expiresAt={approval.expires_at} />}
              {approval.tier && (
                <span className="text-[10px] font-mono text-violet-400 bg-violet-500/10 border border-violet-500/20 px-1.5 py-0.5 rounded">
                  Tier {approval.tier}
                </span>
              )}
            </div>
            <p className="font-bold text-white mt-1.5 truncate">{approval.action_type}</p>
            <p className="text-xs text-slate-500 font-mono mt-0.5 truncate">Agent: {approval.agent_id}</p>
          </div>
          <button
            onClick={() => setExpanded(e => !e)}
            className="text-slate-500 hover:text-slate-300 transition mt-1"
          >
            {expanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          </button>
        </div>

        {/* Risk bar */}
        {riskScore !== undefined && (
          <div className="mt-3">
            <div className="flex justify-between text-[10px] text-slate-500 mb-1">
              <span>Blast Radius Score</span>
              <span className={`font-bold font-mono ${riskScore >= 0.6 ? 'text-rose-400' : riskScore >= 0.25 ? 'text-amber-400' : 'text-emerald-400'}`}>
                {(riskScore * 100).toFixed(0)}%
              </span>
            </div>
            <div className="h-1.5 bg-slate-800 rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full transition-all ${riskScore >= 0.6 ? 'bg-rose-500' : riskScore >= 0.25 ? 'bg-amber-500' : 'bg-emerald-500'}`}
                style={{ width: `${Math.min(100, riskScore * 100)}%` }}
              />
            </div>
          </div>
        )}
      </div>

      {/* Evidence pack expansion */}
      {expanded && (
        <div className="px-5 pb-5 space-y-3 border-t border-slate-800/60 pt-4">
          <div className="flex items-center space-x-2 text-xs text-slate-400 font-semibold">
            <FileText className="w-3.5 h-3.5" />
            <span>Evidence Pack</span>
          </div>
          <pre className="text-[10px] font-mono text-slate-400 bg-slate-950/60 rounded-lg p-3 overflow-x-auto max-h-48">
            {JSON.stringify(evidence, null, 2)}
          </pre>
          {approval.reviewer_id && (
            <div className="flex items-center space-x-2 text-xs text-slate-500">
              <User className="w-3 h-3" />
              <span>Reviewed by: <span className="text-sky-400 font-mono">{approval.reviewer_id}</span></span>
              {approval.reviewer_reason && <span>— {approval.reviewer_reason}</span>}
            </div>
          )}
        </div>
      )}

      {/* Action bar for pending */}
      {isPending && canAct && (
        <div className="px-5 pb-5 space-y-2">
          <div>
            <input
              type="text"
              placeholder="Reason for decision..."
              value={reason}
              onChange={e => {
                setReason(e.target.value);
                setActionError('');
              }}
              className={`w-full text-xs bg-slate-900 border rounded-lg px-3 py-2 text-slate-300 placeholder-slate-600 focus:outline-none transition ${
                actionError ? 'border-rose-500' : 'border-slate-700 focus:border-slate-500'
              }`}
            />
            {actionError && (
              <p className="text-[11px] text-rose-400 mt-1 flex items-center space-x-1 font-medium">
                <AlertCircle className="w-3.5 h-3.5 shrink-0" />
                <span>{actionError}</span>
              </p>
            )}
          </div>
          <div className="flex space-x-2">
            <button
              id={`reject-${approval.id}`}
              onClick={handleReject}
              disabled={!!loading}
              className="flex-1 flex items-center justify-center space-x-1.5 py-2 bg-rose-500/15 hover:bg-rose-500/25 text-rose-400 border border-rose-500/30 rounded-lg text-xs font-bold transition disabled:opacity-50"
            >
              {loading === 'reject' ? <Loader2 className="w-3 h-3 animate-spin" /> : <XCircle className="w-3 h-3" />}
              <span>Reject</span>
            </button>
            <button
              id={`approve-${approval.id}`}
              onClick={handleApprove}
              disabled={!!loading}
              className="flex-1 flex items-center justify-center space-x-1.5 py-2 bg-emerald-500/15 hover:bg-emerald-500/25 text-emerald-400 border border-emerald-500/30 rounded-lg text-xs font-bold transition disabled:opacity-50"
            >
              {loading === 'approve' ? <Loader2 className="w-3 h-3 animate-spin" /> : <CheckSquare className="w-3 h-3" />}
              <span>Approve</span>
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export default function Approvals({ user }) {
  const [approvals, setApprovals] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('PENDING_APPROVAL');

  const load = useCallback(async () => {
    try {
      const data = await api.getApprovals(filter !== 'ALL' ? { status: filter } : {});
      setApprovals(Array.isArray(data) ? data : (data.items ?? []));
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }, [filter]);

  useEffect(() => {
    setLoading(true);
    load();
    const iv = setInterval(load, 10000);
    return () => clearInterval(iv);
  }, [load]);

  const pendingCount = approvals.filter(a => a.status === 'PENDING_APPROVAL' || a.status === 'ESCALATED').length;

  return (
    <div className="p-6 space-y-5 max-w-5xl mx-auto">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h2 className="text-2xl font-extrabold text-white">Approvals Queue</h2>
          <p className="text-slate-500 text-sm mt-0.5">Human-in-the-loop review with SLA countdowns</p>
        </div>
        <div className="flex items-center space-x-2">
          {pendingCount > 0 && (
            <div className="flex items-center space-x-1.5 text-xs text-amber-400 bg-amber-500/10 border border-amber-500/20 px-3 py-1.5 rounded-full font-mono animate-pulse">
              <AlertTriangle className="w-3 h-3" />
              <span>{pendingCount} pending</span>
            </div>
          )}
          <button onClick={load} className="p-2 rounded-lg border border-slate-700 text-slate-400 hover:text-white hover:border-slate-600 transition">
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-2">
        {['PENDING_APPROVAL', 'ESCALATED', 'APPROVED', 'REJECTED', 'TIMED_OUT', 'ALL'].map(s => (
          <button
            key={s}
            onClick={() => setFilter(s)}
            className={`px-3 py-1.5 text-xs font-mono font-bold rounded-lg border transition ${
              filter === s
                ? 'bg-sky-500/15 text-sky-400 border-sky-500/30'
                : 'text-slate-500 border-slate-800 hover:border-slate-700 hover:text-slate-400'
            }`}
          >
            {s}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-40">
          <Loader2 className="w-8 h-8 text-sky-400 animate-spin" />
        </div>
      ) : approvals.length === 0 ? (
        <div className="text-center py-16 text-slate-500">
          <CheckSquare className="w-10 h-10 mx-auto mb-3 opacity-40" />
          <p>No approvals in this queue</p>
        </div>
      ) : (
        <div className="space-y-4">
          {approvals.map(a => (
            <ApprovalCard key={a.id} approval={a} user={user} onAction={load} />
          ))}
        </div>
      )}
    </div>
  );
}
