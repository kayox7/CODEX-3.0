import React, { useEffect, useState, useCallback, useMemo, useRef } from 'react';
import { api } from '../api';
import {
  ShieldCheck, ShieldAlert, RefreshCw, Loader2, Search,
  Download, Filter, X, ChevronRight, Copy, Check, ExternalLink,
  AlertTriangle, Zap, Ban, Clock, CheckCircle2, XCircle, ArrowUpRight,
  Bot, Hash, User, Calendar, SlidersHorizontal, Terminal, Info,
  ChevronLeft, FileText, ChevronDown, Wrench, Shield, CheckSquare
} from 'lucide-react';

// --- Utility Helpers ---

function formatRelativeTime(isoString) {
  if (!isoString) return '—';
  try {
    const date = new Date(isoString);
    const now = new Date();
    const diffSec = Math.floor((now - date) / 1000);
    if (diffSec < 10) return 'Just now';
    if (diffSec < 60) return `${diffSec}s ago`;
    const diffMin = Math.floor(diffSec / 60);
    if (diffMin < 60) return `${diffMin}m ago`;
    const diffHour = Math.floor(diffMin / 60);
    if (diffHour < 24) return `${diffHour}h ago`;
    const diffDays = Math.floor(diffHour / 24);
    if (diffDays === 1) return 'Yesterday';
    if (diffDays < 7) return `${diffDays}d ago`;
    return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
  } catch {
    return isoString;
  }
}

function formatFullTime(isoString) {
  if (!isoString) return '—';
  try {
    const d = new Date(isoString);
    return `${d.toISOString().replace('T', ' ').slice(0, 19)} UTC`;
  } catch {
    return isoString;
  }
}

function formatCurrency(amount) {
  if (amount === undefined || amount === null || amount === '') return null;
  const num = Number(amount);
  if (isNaN(num)) return null;
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: num % 1 === 0 ? 0 : 2,
    maximumFractionDigits: 2
  }).format(num);
}

export function getEntryDecision(entry) {
  const p = entry.payload || {};
  const et = (entry.event_type || '').toUpperCase();
  
  if (p.kill_switch_activated || et === 'KILL_SWITCH_TRIGGERED') return 'KILL_SWITCH';
  if (p.decision) {
    const d = p.decision.toUpperCase();
    if (d === 'DENY' || d === 'BLOCKED') return 'BLOCKED';
    return d;
  }
  if (et === 'ACTION_ALLOWED') return 'ALLOW';
  if (et === 'ACTION_APPROVED') return 'APPROVED';
  if (et === 'ACTION_BLOCKED') return 'BLOCKED';
  if (et === 'ACTION_REJECTED') return 'REJECTED';
  if (et === 'APPROVAL_REQUESTED') return 'PENDING_APPROVAL';
  if (et === 'APPROVAL_ESCALATED') return 'ESCALATED';
  if (et === 'APPROVAL_TIMEOUT' || p.status === 'TIMED_OUT') return 'TIMEOUT';
  if (et.startsWith('AGENT_') || et === 'GENESIS') return 'SYSTEM';
  return 'SYSTEM';
}

export function getEntryExplanation(entry) {
  const p = entry.payload || {};
  if (p.explanation) return p.explanation;
  if (p.reason) return p.reason;
  if (p.message) return p.message;
  if (Array.isArray(p.violations) && p.violations.length > 0) {
    return `Blocked: ${p.violations.join('; ')}`;
  }
  if (entry.event_type === 'ACTION_ALLOWED') {
    return `Approved automatically: action '${p.action || 'unknown'}' in policy parameters`;
  }
  if (entry.event_type === 'APPROVAL_REQUESTED') {
    return `Pending Human Approval: action '${p.action || 'unknown'}' requires sign-off`;
  }
  if (entry.event_type === 'GENESIS') {
    return 'Tamper-evident cryptographically chained ledger initialized';
  }
  return `${entry.event_type} event recorded by ${entry.actor}`;
}

export function getRiskBreakdown(entry) {
  const p = entry.payload || {};
  if (p.risk_breakdown && typeof p.risk_breakdown === 'object') {
    const rb = p.risk_breakdown;
    return {
      score: rb.score !== undefined ? rb.score : (p.risk_score || 0),
      risk_level: rb.risk_level || p.risk_level || 'LOW',
      money_factor: rb.money_factor !== undefined ? rb.money_factor : 0,
      records_factor: rb.records_factor !== undefined ? rb.records_factor : 0,
      irreversibility_factor: rb.irreversibility_factor !== undefined ? rb.irreversibility_factor : 0.5,
      explanation: rb.explanation || p.explanation
    };
  }
  const amount = parseFloat(p.amount || 0);
  const records = parseInt(p.records_affected || (amount > 0 ? 1 : 0), 10);
  const rev = (p.reversibility || 'partially').toLowerCase();
  const revWeight = rev === 'reversible' ? 0.0 : rev === 'irreversible' ? 1.0 : 0.5;
  const moneyFactor = Math.min(amount / 100000, 1.0);
  const recordsFactor = Math.min(records / 10000, 1.0);
  const score = p.risk_score !== undefined ? p.risk_score : (0.4 * moneyFactor + 0.3 * recordsFactor + 0.3 * revWeight);

  return {
    score: round4(score),
    risk_level: p.risk_level || (score > 0.6 ? 'HIGH' : score >= 0.25 ? 'MEDIUM' : 'LOW'),
    money_factor: round4(moneyFactor),
    records_factor: round4(recordsFactor),
    irreversibility_factor: revWeight,
    amount,
    records,
    reversibility: rev
  };
}

function round4(val) {
  return Math.round(val * 10000) / 10000;
}

// Color schemes matching design spec:
// green=allow/approved, amber=pending/escalated, red=blocked/kill switch, purple=human only, gray=system
function getDecisionBadge(decision) {
  const dec = (decision || '').toUpperCase();
  switch (dec) {
    case 'ALLOW':
    case 'APPROVED':
      return {
        bg: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30',
        dot: 'bg-emerald-400',
        label: dec
      };
    case 'PENDING_APPROVAL':
      return {
        bg: 'bg-amber-500/15 text-amber-400 border-amber-500/30',
        dot: 'bg-amber-400',
        label: 'PENDING'
      };
    case 'ESCALATED':
      return {
        bg: 'bg-amber-500/15 text-amber-300 border-amber-500/40',
        dot: 'bg-amber-300',
        label: 'ESCALATED'
      };
    case 'BLOCKED':
      return {
        bg: 'bg-rose-500/15 text-rose-400 border-rose-500/30',
        dot: 'bg-rose-400',
        label: 'BLOCKED'
      };
    case 'KILL_SWITCH':
      return {
        bg: 'bg-rose-500/20 text-rose-300 border-rose-500/50 animate-pulse',
        dot: 'bg-rose-400',
        label: 'KILL SWITCH'
      };
    case 'REJECTED':
      return {
        bg: 'bg-rose-500/15 text-rose-400 border-rose-500/30',
        dot: 'bg-rose-400',
        label: 'REJECTED'
      };
    case 'TIMEOUT':
      return {
        bg: 'bg-rose-500/15 text-rose-400 border-rose-500/30',
        dot: 'bg-rose-400',
        label: 'TIMEOUT'
      };
    case 'HUMAN_ONLY':
      return {
        bg: 'bg-purple-500/15 text-purple-400 border-purple-500/30',
        dot: 'bg-purple-400',
        label: 'HUMAN ONLY'
      };
    default:
      return {
        bg: 'bg-slate-700/40 text-slate-400 border-slate-700',
        dot: 'bg-slate-400',
        label: dec || 'SYSTEM'
      };
  }
}

function getEventBadge(eventType) {
  const et = (eventType || '').toUpperCase();
  if (et === 'ACTION_ALLOWED') {
    return { icon: ShieldCheck, color: 'text-emerald-400', bg: 'bg-emerald-500/10 border-emerald-500/20' };
  }
  if (et === 'ACTION_APPROVED') {
    return { icon: CheckCircle2, color: 'text-emerald-400', bg: 'bg-emerald-500/10 border-emerald-500/20' };
  }
  if (et === 'APPROVAL_REQUESTED') {
    return { icon: Clock, color: 'text-amber-400', bg: 'bg-amber-500/10 border-amber-500/20' };
  }
  if (et === 'APPROVAL_ESCALATED') {
    return { icon: ArrowUpRight, color: 'text-amber-400', bg: 'bg-amber-500/10 border-amber-500/20' };
  }
  if (et === 'ACTION_BLOCKED') {
    return { icon: Ban, color: 'text-rose-400', bg: 'bg-rose-500/10 border-rose-500/20' };
  }
  if (et === 'ACTION_REJECTED') {
    return { icon: XCircle, color: 'text-rose-400', bg: 'bg-rose-500/10 border-rose-500/20' };
  }
  if (et === 'KILL_SWITCH_TRIGGERED') {
    return { icon: Zap, color: 'text-rose-400', bg: 'bg-rose-500/20 border-rose-500/40' };
  }
  if (et === 'APPROVAL_TIMEOUT') {
    return { icon: AlertTriangle, color: 'text-rose-400', bg: 'bg-rose-500/10 border-rose-500/20' };
  }
  return { icon: Hash, color: 'text-slate-400', bg: 'bg-slate-800 border-slate-700' };
}

function getRiskPill(riskLevel, riskScore) {
  const level = (riskLevel || '').toUpperCase();
  const scoreText = riskScore !== undefined && riskScore !== null ? Number(riskScore).toFixed(2) : null;
  if (level === 'LOW') {
    return {
      label: scoreText ? `${scoreText} Low` : 'Low',
      classes: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
    };
  }
  if (level === 'MEDIUM') {
    return {
      label: scoreText ? `${scoreText} Med` : 'Medium',
      classes: 'bg-amber-500/10 text-amber-400 border-amber-500/20'
    };
  }
  if (level === 'HIGH') {
    return {
      label: scoreText ? `${scoreText} High` : 'High',
      classes: 'bg-rose-500/10 text-rose-400 border-rose-500/20'
    };
  }
  if (level === 'RESTRICTED') {
    return {
      label: 'Restricted',
      classes: 'bg-purple-500/10 text-purple-400 border-purple-500/20'
    };
  }
  return {
    label: scoreText ? `${scoreText}` : '—',
    classes: 'bg-slate-800 text-slate-400 border-slate-700'
  };
}

// --- Component: Drawer ---
function LogDetailDrawer({ entry, previousEntry, onClose, onCopyHash }) {
  const [copiedKey, setCopiedKey] = useState(null);
  const [proofLoading, setProofLoading] = useState(false);
  const [proof, setProof] = useState(null);
  const [evidenceOpen, setEvidenceOpen] = useState(false);

  useEffect(() => {
    if (!entry) return;
    let isMounted = true;
    setProofLoading(true);
    setProof(null);

    api.getLedgerProof(entry.id)
      .then(p => {
        if (isMounted) setProof(p);
      })
      .catch(() => {
        // Fallback to client-computed link verification
        if (isMounted && previousEntry) {
          const isLinkValid = entry.prev_hash === previousEntry.hash;
          setProof({
            id: entry.id,
            prev_hash: entry.prev_hash,
            hash: entry.hash,
            expected_prev_hash: previousEntry.hash,
            is_link_valid: isLinkValid,
            is_hash_valid: true,
            is_valid: isLinkValid,
            message: isLinkValid
              ? `Entry #${entry.id} links correctly to prior block hash.`
              : `Link broken: prev_hash does not match prior block hash.`
          });
        }
      })
      .finally(() => {
        if (isMounted) setProofLoading(false);
      });

    return () => { isMounted = false; };
  }, [entry, previousEntry]);

  // Handle ESC key to close
  useEffect(() => {
    const onKeyDown = (e) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [onClose]);

  if (!entry) return null;

  const payload = entry.payload || {};
  const decision = getEntryDecision(entry);
  const decisionBadge = getDecisionBadge(decision);
  const explanation = getEntryExplanation(entry);
  const risk = getRiskBreakdown(entry);
  const violations = payload.violations || payload.policy_evaluation?.violations || [];
  const evidencePack = payload.evidence_pack || payload;

  const handleCopy = (text, key) => {
    navigator.clipboard.writeText(text);
    setCopiedKey(key);
    setTimeout(() => setCopiedKey(null), 2000);
  };

  return (
    <div className="fixed inset-0 z-50 overflow-hidden flex justify-end">
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-slate-950/70 backdrop-blur-sm transition-opacity"
        onClick={onClose}
      />

      {/* Drawer content */}
      <div className="relative w-full max-w-xl bg-[#0c1222] border-l border-slate-800 shadow-2xl flex flex-col h-full z-10 overflow-y-auto">
        {/* Drawer Header */}
        <div className="sticky top-0 bg-[#0c1222]/95 backdrop-blur border-b border-slate-800 p-5 flex items-center justify-between z-20">
          <div className="flex items-center space-x-3">
            <span className="font-mono text-xs px-2.5 py-1 rounded-md bg-slate-800 text-slate-300 font-bold border border-slate-700">
              #{entry.id}
            </span>
            <div>
              <div className="flex items-center space-x-2">
                <h3 className="text-base font-bold text-white">{entry.event_type}</h3>
                <span className={`text-[10px] font-mono font-bold px-2 py-0.5 rounded-full border ${decisionBadge.bg}`}>
                  {decisionBadge.label}
                </span>
              </div>
              <p className="text-xs text-slate-400 font-mono mt-0.5" title={formatFullTime(entry.timestamp)}>
                {formatRelativeTime(entry.timestamp)} · {formatFullTime(entry.timestamp)}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg border border-slate-700 text-slate-400 hover:text-white hover:bg-slate-800 transition"
            aria-label="Close drawer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Drawer Body */}
        <div className="p-5 space-y-5 flex-1">
          {/* Explanation Callout */}
          <div className="rounded-xl p-4 bg-slate-900/90 border border-slate-800 space-y-1.5">
            <div className="text-[11px] font-bold tracking-wider text-slate-400 uppercase font-mono flex items-center space-x-1.5">
              <Info className="w-3.5 h-3.5 text-sky-400" />
              <span>Explanation</span>
            </div>
            <p className="text-sm text-slate-200 leading-relaxed font-medium">
              {explanation}
            </p>
          </div>

          {/* Policy Violations (if present) */}
          {violations.length > 0 && (
            <div className="rounded-xl p-4 bg-rose-500/10 border border-rose-500/30 space-y-2">
              <div className="text-[11px] font-bold tracking-wider text-rose-400 uppercase font-mono flex items-center space-x-1.5">
                <AlertTriangle className="w-3.5 h-3.5 text-rose-400" />
                <span>Policy Violations ({violations.length})</span>
              </div>
              <ul className="space-y-1.5 text-xs text-rose-200">
                {violations.map((v, i) => (
                  <li key={i} className="flex items-start space-x-2">
                    <span className="text-rose-400 font-bold mt-0.5">•</span>
                    <span>{v}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Action & Agent Context */}
          <div className="grid grid-cols-2 gap-3">
            <div className="p-3.5 rounded-xl bg-slate-900/60 border border-slate-800">
              <span className="text-[10px] text-slate-500 uppercase font-mono">Agent</span>
              <p className="text-sm font-semibold text-slate-200 mt-0.5 flex items-center space-x-1.5">
                <Bot className="w-4 h-4 text-sky-400 shrink-0" />
                <span className="truncate">{payload.agent_id || entry.actor}</span>
              </p>
            </div>
            <div className="p-3.5 rounded-xl bg-slate-900/60 border border-slate-800">
              <span className="text-[10px] text-slate-500 uppercase font-mono">Action & Amount</span>
              <p className="text-sm font-semibold text-slate-200 mt-0.5 font-mono truncate">
                {payload.action || '—'}
                {payload.amount !== undefined && payload.amount > 0 && (
                  <span className="ml-1.5 text-emerald-400">({formatCurrency(payload.amount)})</span>
                )}
              </p>
            </div>
          </div>

          {/* Risk Score Breakdown */}
          <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-bold tracking-wider text-slate-400 uppercase font-mono">
                Risk Score Breakdown
              </span>
              <span className="text-xs font-mono font-bold text-sky-400">
                Score: {risk.score !== undefined ? risk.score : '0.00'} · {risk.risk_level}
              </span>
            </div>

            <div className="space-y-2.5 text-xs">
              {/* Money Factor */}
              <div>
                <div className="flex justify-between text-slate-400 mb-1">
                  <span>Financial Exposure</span>
                  <span className="font-mono text-slate-300">
                    {Math.round((risk.money_factor || 0) * 100)}% {payload.amount ? `(${formatCurrency(payload.amount)})` : ''}
                  </span>
                </div>
                <div className="w-full bg-slate-800 rounded-full h-1.5 overflow-hidden">
                  <div
                    className="bg-emerald-400 h-1.5 rounded-full transition-all duration-300"
                    style={{ width: `${Math.min(Math.max((risk.money_factor || 0) * 100, 2), 100)}%` }}
                  />
                </div>
              </div>

              {/* Records Factor */}
              <div>
                <div className="flex justify-between text-slate-400 mb-1">
                  <span>Affected Records</span>
                  <span className="font-mono text-slate-300">
                    {Math.round((risk.records_factor || 0) * 100)}% {payload.records_affected ? `(${payload.records_affected} recs)` : ''}
                  </span>
                </div>
                <div className="w-full bg-slate-800 rounded-full h-1.5 overflow-hidden">
                  <div
                    className="bg-sky-400 h-1.5 rounded-full transition-all duration-300"
                    style={{ width: `${Math.min(Math.max((risk.records_factor || 0) * 100, 2), 100)}%` }}
                  />
                </div>
              </div>

              {/* Irreversibility */}
              <div>
                <div className="flex justify-between text-slate-400 mb-1">
                  <span>Irreversibility</span>
                  <span className="font-mono text-slate-300">
                    {Math.round((risk.irreversibility_factor || 0) * 100)}% ({payload.reversibility || 'partially'})
                  </span>
                </div>
                <div className="w-full bg-slate-800 rounded-full h-1.5 overflow-hidden">
                  <div
                    className="bg-amber-400 h-1.5 rounded-full transition-all duration-300"
                    style={{ width: `${Math.min(Math.max((risk.irreversibility_factor || 0) * 100, 2), 100)}%` }}
                  />
                </div>
              </div>
            </div>
          </div>

          {/* Cryptographic Chain Proof */}
          <div className="p-4 rounded-xl bg-slate-900/90 border border-slate-800 space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-bold tracking-wider text-slate-400 uppercase font-mono flex items-center space-x-1.5">
                <ShieldCheck className="w-4 h-4 text-emerald-400" />
                <span>Cryptographic Chain Proof</span>
              </span>
              {proofLoading ? (
                <Loader2 className="w-3.5 h-3.5 text-slate-500 animate-spin" />
              ) : proof && (
                <span className={`text-[10px] font-mono font-bold px-2 py-0.5 rounded-full border ${
                  proof.is_valid
                    ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30'
                    : 'bg-rose-500/15 text-rose-400 border-rose-500/30'
                }`}>
                  {proof.is_valid ? 'Chain Link Valid' : 'Integrity Broken'}
                </span>
              )}
            </div>

            <div className="space-y-2 text-xs">
              {/* Current Hash */}
              <div className="p-2.5 rounded-lg bg-slate-950/80 border border-slate-800 flex items-center justify-between">
                <div className="min-w-0 mr-2">
                  <span className="text-[10px] text-slate-500 uppercase font-mono block">Entry Hash (SHA-256)</span>
                  <code className="text-[11px] text-sky-400 font-mono truncate block" title={entry.hash}>
                    {entry.hash?.slice(0, 20)}...{entry.hash?.slice(-8)}
                  </code>
                </div>
                <button
                  onClick={() => handleCopy(entry.hash, 'hash')}
                  className="p-1.5 rounded text-slate-400 hover:text-white hover:bg-slate-800 transition shrink-0"
                  title="Copy full hash"
                >
                  {copiedKey === 'hash' ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                </button>
              </div>

              {/* Prev Hash */}
              <div className="p-2.5 rounded-lg bg-slate-950/80 border border-slate-800 flex items-center justify-between">
                <div className="min-w-0 mr-2">
                  <span className="text-[10px] text-slate-500 uppercase font-mono block">Previous Hash (Parent Link)</span>
                  <code className="text-[11px] text-slate-400 font-mono truncate block" title={entry.prev_hash}>
                    {entry.prev_hash === '0'.repeat(64)
                      ? '00000000000000000000 (GENESIS)'
                      : `${entry.prev_hash?.slice(0, 20)}...${entry.prev_hash?.slice(-8)}`}
                  </code>
                </div>
                <button
                  onClick={() => handleCopy(entry.prev_hash, 'prev_hash')}
                  className="p-1.5 rounded text-slate-400 hover:text-white hover:bg-slate-800 transition shrink-0"
                  title="Copy previous hash"
                >
                  {copiedKey === 'prev_hash' ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                </button>
              </div>

              {/* Link validation text */}
              {proof && (
                <div className={`p-2.5 rounded-lg border text-[11px] ${
                  proof.is_valid
                    ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400'
                    : 'bg-rose-500/10 border-rose-500/20 text-rose-400'
                }`}>
                  <p className="font-semibold">{proof.message}</p>
                </div>
              )}
            </div>
          </div>

          {/* Evidence Pack Collapsible Code */}
          <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 space-y-2">
            <div className="flex items-center justify-between">
              <button
                onClick={() => setEvidenceOpen(o => !o)}
                className="flex items-center space-x-2 text-xs font-bold text-slate-300 hover:text-white transition"
              >
                <ChevronDown className={`w-4 h-4 transition-transform ${evidenceOpen ? 'rotate-180' : ''}`} />
                <span>Evidence Pack & Payload JSON</span>
              </button>
              <button
                onClick={() => handleCopy(JSON.stringify(evidencePack, null, 2), 'evidence')}
                className="p-1.5 rounded text-slate-400 hover:text-white hover:bg-slate-800 transition flex items-center space-x-1 text-xs"
              >
                {copiedKey === 'evidence' ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                <span>{copiedKey === 'evidence' ? 'Copied' : 'Copy'}</span>
              </button>
            </div>

            {evidenceOpen && (
              <pre className="text-[11px] font-mono text-slate-300 bg-slate-950 rounded-lg p-3 overflow-x-auto max-h-64 border border-slate-800">
                {JSON.stringify(evidencePack, null, 2)}
              </pre>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

// --- Component: Tamper Simulation Modal ---
function TamperConfirmModal({ isOpen, onClose, onTamper, currentEntries }) {
  const [targetId, setTargetId] = useState('');
  const [note, setNote] = useState('Simulated unauthorized modification for audit testing');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (isOpen && currentEntries && currentEntries.length > 0) {
      // Pick first non-genesis entry or entry #2
      const candidate = currentEntries.find(e => e.id > 1) || currentEntries[0];
      setTargetId(String(candidate.id));
      setError('');
    }
  }, [isOpen, currentEntries]);

  if (!isOpen) return null;

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!targetId) return;
    setError('');
    setLoading(true);
    try {
      await onTamper(targetId, note);
      onClose();
    } catch (err) {
      setError(err.message || 'Tamper simulation failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="fixed inset-0 bg-slate-950/80 backdrop-blur-sm" onClick={onClose} />
      <div className="relative bg-[#0c1222] border border-rose-500/40 rounded-2xl p-6 max-w-md w-full shadow-2xl z-10 space-y-4 glow-rose">
        <div className="flex items-center space-x-3 text-rose-400 font-bold">
          <div className="p-2 rounded-lg bg-rose-500/15 border border-rose-500/30">
            <AlertTriangle className="w-5 h-5 text-rose-400" />
          </div>
          <div>
            <h3 className="text-base text-white font-bold">Simulate Ledger Tampering</h3>
            <p className="text-xs text-rose-400 font-normal">Dev-Only Audit Demonstration</p>
          </div>
        </div>

        <p className="text-xs text-slate-300 leading-relaxed">
          This test intentionally modifies a database record in-place without recomputing the SHA-256 hash.
          When you click <strong className="text-white">Verify Chain</strong> afterwards, WARDEN will detect the exact tampered entry.
        </p>

        <form onSubmit={handleSubmit} className="space-y-3">
          <div>
            <label className="text-[11px] font-mono text-slate-400 uppercase block mb-1">Target Entry ID</label>
            <input
              type="number"
              value={targetId}
              onChange={e => {
                setTargetId(e.target.value);
                setError('');
              }}
              className={`w-full text-xs font-mono bg-slate-900 border rounded-lg px-3 py-2 text-white placeholder-slate-600 focus:outline-none transition ${
                error ? 'border-rose-500' : 'border-slate-700 focus:border-rose-500'
              }`}
              required
            />
            {error && (
              <p className="text-xs text-rose-400 mt-1 flex items-center space-x-1 font-medium">
                <AlertCircle className="w-3.5 h-3.5 shrink-0" />
                <span>{error}</span>
              </p>
            )}
          </div>
          <div>
            <label className="text-[11px] font-mono text-slate-400 uppercase block mb-1">Tamper Note</label>
            <input
              type="text"
              value={note}
              onChange={e => setNote(e.target.value)}
              className="w-full text-xs bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-white placeholder-slate-600 focus:outline-none focus:border-rose-500"
              required
            />
          </div>

          <div className="flex items-center justify-end space-x-2 pt-2">
            <button
              type="button"
              onClick={onClose}
              disabled={loading}
              className="px-4 py-2 rounded-lg text-xs font-semibold text-slate-400 hover:text-white hover:bg-slate-800 transition"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading || !targetId}
              className="px-4 py-2 rounded-lg text-xs font-semibold bg-rose-600 hover:bg-rose-500 disabled:opacity-50 text-white transition flex items-center space-x-1.5"
            >
              {loading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Ban className="w-3.5 h-3.5" />}
              <span>{loading ? 'Injecting...' : 'Inject Tamper'}</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// --- Main Page: Activity Logs (LedgerExplorer) ---
export default function LedgerExplorer() {
  const [entries, setEntries] = useState([]);
  const [totalCount, setTotalCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Verification state
  const [verifying, setVerifying] = useState(false);
  const [verifyResult, setVerifyResult] = useState(null);

  // Live toggle
  const [isLive, setIsLive] = useState(true);

  // Dev mode & tamper modal
  const [devMode, setDevMode] = useState(false);
  const [devMenuOpen, setDevMenuOpen] = useState(false);
  const [tamperModalOpen, setTamperModalOpen] = useState(false);

  // Drawer state
  const [selectedEntry, setSelectedEntry] = useState(null);

  // Available agents list for dropdown
  const [agentsList, setAgentsList] = useState([]);

  // Pagination
  const [page, setPage] = useState(1);
  const pageSize = 50;

  // Filters
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedDecisions, setSelectedDecisions] = useState([]);
  const [selectedAgent, setSelectedAgent] = useState('ALL');
  const [selectedRisk, setSelectedRisk] = useState('ALL');
  const [dateRange, setDateRange] = useState('ALL'); // ALL, 1H, TODAY, 7D, CUSTOM
  const [customFrom, setCustomFrom] = useState('');
  const [customTo, setCustomTo] = useState('');

  // Dropdown open states
  const [decisionDropdownOpen, setDecisionDropdownOpen] = useState(false);

  // Multi-select decision choices
  const DECISION_CHOICES = [
    'ALLOW', 'PENDING_APPROVAL', 'BLOCKED', 'HUMAN_ONLY',
    'APPROVED', 'REJECTED', 'ESCALATED', 'TIMEOUT', 'KILL_SWITCH'
  ];

  // Fetch health to check dev_mode
  useEffect(() => {
    api.getHealth()
      .then(h => {
        if (h && (h.dev_mode || h.environment === 'development')) {
          setDevMode(true);
        }
      })
      .catch(() => {
        // Fallback: check if local dev hostname
        if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
          setDevMode(true);
        }
      });
  }, []);

  // Fetch agents list for filter dropdown
  useEffect(() => {
    api.getAgents()
      .then(data => {
        const list = Array.isArray(data) ? data : (data.items || []);
        setAgentsList(list);
      })
      .catch(() => {});
  }, []);

  // Compute date from/to query params based on dateRange preset
  const computedDateRange = useMemo(() => {
    const now = new Date();
    if (dateRange === '1H') {
      const from = new Date(now.getTime() - 60 * 60 * 1000).toISOString();
      return { from, to: null };
    }
    if (dateRange === 'TODAY') {
      const startOfDay = new Date(now.getFullYear(), now.getMonth(), now.getDate()).toISOString();
      return { from: startOfDay, to: null };
    }
    if (dateRange === '7D') {
      const from = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000).toISOString();
      return { from, to: null };
    }
    if (dateRange === 'CUSTOM') {
      return {
        from: customFrom ? new Date(customFrom).toISOString() : null,
        to: customTo ? new Date(customTo).toISOString() : null
      };
    }
    return { from: null, to: null };
  }, [dateRange, customFrom, customTo]);

  // Load activity logs
  const loadData = useCallback(async (isPolling = false) => {
    if (!isPolling) setLoading(true);
    setError(null);
    try {
      const offset = (page - 1) * pageSize;
      const params = {
        limit: pageSize,
        offset,
        q: searchQuery.trim() || undefined,
        event_type: selectedDecisions.length > 0 ? selectedDecisions.join(',') : undefined,
        agent_id: selectedAgent !== 'ALL' ? selectedAgent : undefined,
        risk_level: selectedRisk !== 'ALL' ? selectedRisk : undefined,
        from: computedDateRange.from || undefined,
        to: computedDateRange.to || undefined
      };

      const res = await api.getLedger(params);
      if (Array.isArray(res)) {
        setEntries(res);
        setTotalCount(res.length);
      } else {
        setEntries(res.items || []);
        setTotalCount(res.total || 0);
      }
    } catch (err) {
      console.error(err);
      if (!isPolling) setError(err.message || 'Failed to load activity logs');
    } finally {
      if (!isPolling) setLoading(false);
    }
  }, [page, pageSize, searchQuery, selectedDecisions, selectedAgent, selectedRisk, computedDateRange]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Live auto-refresh every 5s
  useEffect(() => {
    if (!isLive) return;
    const interval = setInterval(() => {
      loadData(true);
    }, 5000);
    return () => clearInterval(interval);
  }, [isLive, loadData]);

  // Verify chain handler
  const handleVerifyChain = async () => {
    setVerifying(true);
    try {
      const res = await api.verifyLedger();
      setVerifyResult(res);
    } catch (e) {
      setVerifyResult({ valid: false, message: e.message || 'Verification request failed' });
    } finally {
      setVerifying(false);
    }
  };

  // Simulate Tamper handler
  const handleTamper = async (id, note) => {
    try {
      await api.tamperLedger(id, note);
      await loadData();
      // Auto-trigger verification to reveal the tamper
      handleVerifyChain();
    } catch (e) {
      alert(`Tamper simulation failed: ${e.message}`);
    }
  };

  // Export CSV handler
  const handleExportCSV = () => {
    if (entries.length === 0) return;
    const headers = [
      'ID', 'Timestamp', 'Event Type', 'Decision', 'Agent', 'Action',
      'Amount', 'Risk Score', 'Risk Level', 'Actor', 'Hash', 'Prev Hash', 'Explanation'
    ];
    const rows = entries.map(e => {
      const p = e.payload || {};
      const dec = getEntryDecision(e);
      const exp = getEntryExplanation(e);
      const agent = p.agent_id || e.actor;
      const action = p.action || '';
      const amount = p.amount !== undefined ? p.amount : '';
      const riskScore = p.risk_score !== undefined ? p.risk_score : '';
      const riskLevel = p.risk_level || '';
      return [
        e.id,
        `"${e.timestamp}"`,
        `"${e.event_type}"`,
        `"${dec}"`,
        `"${agent}"`,
        `"${action}"`,
        amount,
        riskScore,
        `"${riskLevel}"`,
        `"${e.actor}"`,
        `"${e.hash}"`,
        `"${e.prev_hash}"`,
        `"${exp.replace(/"/g, '""')}"`
      ];
    });
    const csvContent = [headers.join(','), ...rows.map(r => r.join(','))].join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `warden_activity_logs_${new Date().toISOString().slice(0, 10)}.csv`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  // Summary Metrics computed from real data
  const summaryMetrics = useMemo(() => {
    let allowed = 0;
    let pending = 0;
    let blocked = 0;
    let killSwitch = 0;

    entries.forEach(e => {
      const dec = getEntryDecision(e);
      if (dec === 'ALLOW' || dec === 'APPROVED') allowed++;
      else if (dec === 'PENDING_APPROVAL') pending++;
      else if (dec === 'BLOCKED' || dec === 'REJECTED' || dec === 'TIMEOUT') blocked++;
      else if (dec === 'KILL_SWITCH') killSwitch++;
    });

    return {
      total: totalCount || entries.length,
      allowed,
      pending,
      blocked,
      killSwitch
    };
  }, [entries, totalCount]);

  // Summary Card Click to filter
  const handleSummaryCardClick = (type) => {
    setPage(1);
    if (type === 'ALL') {
      setSelectedDecisions([]);
    } else if (type === 'ALLOWED') {
      if (selectedDecisions.includes('ALLOW')) {
        setSelectedDecisions([]);
      } else {
        setSelectedDecisions(['ALLOW', 'APPROVED']);
      }
    } else if (type === 'PENDING') {
      if (selectedDecisions.includes('PENDING_APPROVAL')) {
        setSelectedDecisions([]);
      } else {
        setSelectedDecisions(['PENDING_APPROVAL']);
      }
    } else if (type === 'BLOCKED') {
      if (selectedDecisions.includes('BLOCKED')) {
        setSelectedDecisions([]);
      } else {
        setSelectedDecisions(['BLOCKED']);
      }
    } else if (type === 'KILL_SWITCH') {
      if (selectedDecisions.includes('KILL_SWITCH')) {
        setSelectedDecisions([]);
      } else {
        setSelectedDecisions(['KILL_SWITCH']);
      }
    }
  };

  const isCardActive = (type) => {
    if (type === 'ALL') return selectedDecisions.length === 0;
    if (type === 'ALLOWED') return selectedDecisions.includes('ALLOW');
    if (type === 'PENDING') return selectedDecisions.includes('PENDING_APPROVAL');
    if (type === 'BLOCKED') return selectedDecisions.includes('BLOCKED');
    if (type === 'KILL_SWITCH') return selectedDecisions.includes('KILL_SWITCH');
    return false;
  };

  // Clear all filters
  const handleClearAllFilters = () => {
    setSearchQuery('');
    setSelectedDecisions([]);
    setSelectedAgent('ALL');
    setSelectedRisk('ALL');
    setDateRange('ALL');
    setCustomFrom('');
    setCustomTo('');
    setPage(1);
  };

  const hasActiveFilters = searchQuery || selectedDecisions.length > 0 || selectedAgent !== 'ALL' || selectedRisk !== 'ALL' || dateRange !== 'ALL';

  const totalPages = Math.max(1, Math.ceil(totalCount / pageSize));

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto min-h-full">
      {/* 1. Header */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-extrabold text-white tracking-tight">Activity Logs</h1>
          <p className="text-slate-400 text-sm mt-0.5">
            Every AI action decision, tamper-evident
          </p>
        </div>

        {/* Header Actions */}
        <div className="flex items-center flex-wrap gap-2.5">
          {/* Verify Chain Button & Result Badge */}
          <div className="flex items-center space-x-2">
            <button
              onClick={handleVerifyChain}
              disabled={verifying}
              className={`px-3 py-2 rounded-xl text-xs font-semibold flex items-center space-x-2 border transition ${
                verifyResult && !verifyResult.valid
                  ? 'bg-rose-500/20 text-rose-300 border-rose-500/40 hover:bg-rose-500/30 glow-rose'
                  : verifyResult && verifyResult.valid
                  ? 'bg-emerald-500/15 text-emerald-300 border-emerald-500/40 hover:bg-emerald-500/25 glow-emerald'
                  : 'bg-slate-900 border-slate-700 text-slate-200 hover:bg-slate-800 hover:border-slate-600'
              }`}
            >
              {verifying ? (
                <Loader2 className="w-4 h-4 animate-spin text-sky-400" />
              ) : verifyResult && !verifyResult.valid ? (
                <ShieldAlert className="w-4 h-4 text-rose-400" />
              ) : (
                <ShieldCheck className="w-4 h-4 text-emerald-400" />
              )}
              <span>
                {verifying
                  ? 'Verifying...'
                  : verifyResult && verifyResult.valid
                  ? `Chain valid · ${verifyResult.total_entries} entries`
                  : verifyResult && !verifyResult.valid
                  ? `Broken at entry #${verifyResult.broken_entry_id ?? verifyResult.broken_index}`
                  : 'Verify Chain'}
              </span>
            </button>
          </div>

          {/* Live Toggle */}
          <button
            onClick={() => setIsLive(l => !l)}
            className={`px-3 py-2 rounded-xl text-xs font-semibold flex items-center space-x-2 border transition ${
              isLive
                ? 'bg-slate-900 border-emerald-500/40 text-slate-200'
                : 'bg-slate-900 border-slate-700 text-slate-400 hover:text-slate-200'
            }`}
            title={isLive ? 'Live refresh active (every 5s)' : 'Live refresh paused'}
          >
            <span className="relative flex h-2 w-2">
              {isLive && (
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
              )}
              <span className={`relative inline-flex rounded-full h-2 w-2 ${isLive ? 'bg-emerald-500' : 'bg-slate-500'}`} />
            </span>
            <span>Live</span>
          </button>

          {/* Export CSV Button */}
          <button
            onClick={handleExportCSV}
            disabled={entries.length === 0}
            className="px-3 py-2 rounded-xl text-xs font-semibold bg-slate-900 border border-slate-700 text-slate-200 hover:bg-slate-800 hover:border-slate-600 transition flex items-center space-x-2 disabled:opacity-50"
          >
            <Download className="w-4 h-4 text-slate-400" />
            <span>Export CSV</span>
          </button>

          {/* Dev Tools Dropdown (Visible only if DEV_MODE) */}
          {devMode && (
            <div className="relative">
              <button
                onClick={() => setDevMenuOpen(o => !o)}
                className="px-3 py-2 rounded-xl text-xs font-semibold bg-rose-500/10 border border-rose-500/30 text-rose-300 hover:bg-rose-500/20 transition flex items-center space-x-1.5"
              >
                <Wrench className="w-3.5 h-3.5" />
                <span>Dev Tools</span>
                <ChevronDown className="w-3.5 h-3.5 ml-0.5" />
              </button>

              {devMenuOpen && (
                <>
                  <div className="fixed inset-0 z-30" onClick={() => setDevMenuOpen(false)} />
                  <div className="absolute right-0 mt-2 w-48 rounded-xl bg-slate-900 border border-slate-700 shadow-xl py-1.5 z-40">
                    <button
                      onClick={() => {
                        setDevMenuOpen(false);
                        setTamperModalOpen(true);
                      }}
                      className="w-full text-left px-3 py-2 text-xs text-rose-300 hover:bg-rose-500/15 flex items-center space-x-2 transition"
                    >
                      <AlertTriangle className="w-3.5 h-3.5 text-rose-400" />
                      <span>Simulate Tamper</span>
                    </button>
                  </div>
                </>
              )}
            </div>
          )}
        </div>
      </div>

      {/* 2. Summary Cards (Computed from real data) */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3.5">
        {/* Total Events */}
        <button
          onClick={() => handleSummaryCardClick('ALL')}
          className={`glass-panel p-4 rounded-xl text-left transition hover:border-slate-600 ${
            isCardActive('ALL') ? 'border-sky-500/60 ring-1 ring-sky-500/40 bg-sky-500/5' : ''
          }`}
        >
          <div className="flex items-center justify-between text-slate-400 mb-1">
            <span className="text-[11px] font-mono uppercase font-bold tracking-wider">Total Events</span>
            <Hash className="w-4 h-4 text-slate-500" />
          </div>
          <p className="text-2xl font-extrabold text-white mt-1">
            {summaryMetrics.total}
          </p>
          <span className="text-[10px] text-slate-500 mt-0.5 block">Recorded in chain</span>
        </button>

        {/* Allowed */}
        <button
          onClick={() => handleSummaryCardClick('ALLOWED')}
          className={`glass-panel p-4 rounded-xl text-left transition hover:border-emerald-500/40 ${
            isCardActive('ALLOWED') ? 'border-emerald-500/60 ring-1 ring-emerald-500/40 bg-emerald-500/5' : ''
          }`}
        >
          <div className="flex items-center justify-between text-emerald-400 mb-1">
            <span className="text-[11px] font-mono uppercase font-bold tracking-wider text-slate-400">Allowed</span>
            <ShieldCheck className="w-4 h-4 text-emerald-400" />
          </div>
          <p className="text-2xl font-extrabold text-emerald-400 mt-1">
            {summaryMetrics.allowed}
          </p>
          <span className="text-[10px] text-slate-500 mt-0.5 block">Approved / executed</span>
        </button>

        {/* Pending Approval */}
        <button
          onClick={() => handleSummaryCardClick('PENDING')}
          className={`glass-panel p-4 rounded-xl text-left transition hover:border-amber-500/40 ${
            isCardActive('PENDING') ? 'border-amber-500/60 ring-1 ring-amber-500/40 bg-amber-500/5' : ''
          }`}
        >
          <div className="flex items-center justify-between text-amber-400 mb-1">
            <span className="text-[11px] font-mono uppercase font-bold tracking-wider text-slate-400">Pending Review</span>
            <Clock className="w-4 h-4 text-amber-400" />
          </div>
          <p className="text-2xl font-extrabold text-amber-400 mt-1">
            {summaryMetrics.pending}
          </p>
          <span className="text-[10px] text-slate-500 mt-0.5 block">Awaiting sign-off</span>
        </button>

        {/* Blocked */}
        <button
          onClick={() => handleSummaryCardClick('BLOCKED')}
          className={`glass-panel p-4 rounded-xl text-left transition hover:border-rose-500/40 ${
            isCardActive('BLOCKED') ? 'border-rose-500/60 ring-1 ring-rose-500/40 bg-rose-500/5' : ''
          }`}
        >
          <div className="flex items-center justify-between text-rose-400 mb-1">
            <span className="text-[11px] font-mono uppercase font-bold tracking-wider text-slate-400">Blocked</span>
            <Ban className="w-4 h-4 text-rose-400" />
          </div>
          <p className="text-2xl font-extrabold text-rose-400 mt-1">
            {summaryMetrics.blocked}
          </p>
          <span className="text-[10px] text-slate-500 mt-0.5 block">Policy denied</span>
        </button>

        {/* Kill-Switch Triggers */}
        <button
          onClick={() => handleSummaryCardClick('KILL_SWITCH')}
          className={`glass-panel p-4 rounded-xl text-left transition hover:border-rose-500/40 ${
            isCardActive('KILL_SWITCH') ? 'border-rose-500/60 ring-1 ring-rose-500/40 bg-rose-500/5' : ''
          }`}
        >
          <div className="flex items-center justify-between text-rose-400 mb-1">
            <span className="text-[11px] font-mono uppercase font-bold tracking-wider text-slate-400">Kill Switches</span>
            <Zap className="w-4 h-4 text-rose-400" />
          </div>
          <p className="text-2xl font-extrabold text-rose-400 mt-1">
            {summaryMetrics.killSwitch}
          </p>
          <span className="text-[10px] text-slate-500 mt-0.5 block">Circuit breaker</span>
        </button>
      </div>

      {/* 3. Filter Bar */}
      <div className="glass-panel rounded-2xl p-4 space-y-3">
        <div className="flex flex-col md:flex-row items-stretch md:items-center gap-3">
          {/* Search box */}
          <div className="relative flex-1">
            <Search className="w-4 h-4 text-slate-500 absolute left-3.5 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="Search agent, action, decision ID, actor..."
              value={searchQuery}
              onChange={e => {
                setSearchQuery(e.target.value);
                setPage(1);
              }}
              className="w-full text-xs bg-slate-900 border border-slate-700 rounded-xl pl-9 pr-8 py-2.5 text-slate-200 placeholder-slate-500 focus:outline-none focus:border-sky-500 transition"
            />
            {searchQuery && (
              <button
                onClick={() => setSearchQuery('')}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            )}
          </div>

          {/* Decision Type Multi-Select Dropdown */}
          <div className="relative">
            <button
              onClick={() => setDecisionDropdownOpen(o => !o)}
              className={`px-3.5 py-2.5 rounded-xl text-xs font-semibold border flex items-center justify-between space-x-2 transition min-w-[140px] ${
                selectedDecisions.length > 0
                  ? 'bg-sky-500/15 border-sky-500/40 text-sky-300'
                  : 'bg-slate-900 border-slate-700 text-slate-300 hover:border-slate-600'
              }`}
            >
              <div className="flex items-center space-x-1.5 truncate">
                <SlidersHorizontal className="w-3.5 h-3.5" />
                <span>
                  {selectedDecisions.length === 0
                    ? 'All Decisions'
                    : `Decisions (${selectedDecisions.length})`}
                </span>
              </div>
              <ChevronDown className="w-3.5 h-3.5 shrink-0" />
            </button>

            {decisionDropdownOpen && (
              <>
                <div className="fixed inset-0 z-30" onClick={() => setDecisionDropdownOpen(false)} />
                <div className="absolute left-0 md:right-0 md:left-auto mt-2 w-56 rounded-xl bg-slate-900 border border-slate-700 shadow-2xl p-2 z-40 space-y-1 max-h-64 overflow-y-auto">
                  <div className="flex items-center justify-between px-2 py-1 border-b border-slate-800 text-[10px] text-slate-500 font-mono">
                    <span>Filter Decision Types</span>
                    {selectedDecisions.length > 0 && (
                      <button
                        onClick={() => setSelectedDecisions([])}
                        className="text-sky-400 hover:underline"
                      >
                        Reset
                      </button>
                    )}
                  </div>
                  {DECISION_CHOICES.map(dec => {
                    const checked = selectedDecisions.includes(dec);
                    return (
                      <label
                        key={dec}
                        className="flex items-center space-x-2.5 px-2 py-1.5 rounded-lg text-xs hover:bg-slate-800/80 cursor-pointer text-slate-300"
                      >
                        <input
                          type="checkbox"
                          checked={checked}
                          onChange={() => {
                            setPage(1);
                            if (checked) {
                              setSelectedDecisions(selectedDecisions.filter(d => d !== dec));
                            } else {
                              setSelectedDecisions([...selectedDecisions, dec]);
                            }
                          }}
                          className="rounded border-slate-700 text-sky-500 focus:ring-0 bg-slate-950"
                        />
                        <span className="font-mono text-[11px]">{dec}</span>
                      </label>
                    );
                  })}
                </div>
              </>
            )}
          </div>

          {/* Agent Dropdown */}
          <select
            value={selectedAgent}
            onChange={e => {
              setSelectedAgent(e.target.value);
              setPage(1);
            }}
            className="text-xs bg-slate-900 border border-slate-700 rounded-xl px-3 py-2.5 text-slate-300 focus:outline-none focus:border-sky-500 transition cursor-pointer"
          >
            <option value="ALL">All Agents</option>
            {agentsList.map(a => (
              <option key={a.agent_id} value={a.agent_id}>
                {a.name || a.agent_id}
              </option>
            ))}
          </select>

          {/* Risk Level Dropdown */}
          <select
            value={selectedRisk}
            onChange={e => {
              setSelectedRisk(e.target.value);
              setPage(1);
            }}
            className="text-xs bg-slate-900 border border-slate-700 rounded-xl px-3 py-2.5 text-slate-300 focus:outline-none focus:border-sky-500 transition cursor-pointer"
          >
            <option value="ALL">All Risk Levels</option>
            <option value="LOW">Low Risk</option>
            <option value="MEDIUM">Medium Risk</option>
            <option value="HIGH">High Risk</option>
            <option value="RESTRICTED">Restricted</option>
          </select>

          {/* Date Range Presets */}
          <select
            value={dateRange}
            onChange={e => {
              setDateRange(e.target.value);
              setPage(1);
            }}
            className="text-xs bg-slate-900 border border-slate-700 rounded-xl px-3 py-2.5 text-slate-300 focus:outline-none focus:border-sky-500 transition cursor-pointer"
          >
            <option value="ALL">All Time</option>
            <option value="1H">Last Hour</option>
            <option value="TODAY">Today</option>
            <option value="7D">Last 7 Days</option>
            <option value="CUSTOM">Custom Range</option>
          </select>
        </div>

        {/* Custom Date Pickers (if CUSTOM selected) */}
        {dateRange === 'CUSTOM' && (
          <div className="flex flex-wrap items-center gap-3 pt-2 border-t border-slate-800 text-xs">
            <div className="flex items-center space-x-2">
              <span className="text-slate-400 font-mono text-[11px]">From:</span>
              <input
                type="datetime-local"
                value={customFrom}
                onChange={e => {
                  setCustomFrom(e.target.value);
                  setPage(1);
                }}
                className="bg-slate-900 border border-slate-700 rounded-lg px-2.5 py-1.5 text-slate-200 text-xs focus:outline-none focus:border-sky-500"
              />
            </div>
            <div className="flex items-center space-x-2">
              <span className="text-slate-400 font-mono text-[11px]">To:</span>
              <input
                type="datetime-local"
                value={customTo}
                onChange={e => {
                  setCustomTo(e.target.value);
                  setPage(1);
                }}
                className="bg-slate-900 border border-slate-700 rounded-lg px-2.5 py-1.5 text-slate-200 text-xs focus:outline-none focus:border-sky-500"
              />
            </div>
          </div>
        )}

        {/* Active Filter Chips & Clear All */}
        {hasActiveFilters && (
          <div className="flex flex-wrap items-center gap-2 pt-2 border-t border-slate-800/80 text-xs">
            <span className="text-slate-500 text-[11px] font-mono uppercase">Active Filters:</span>

            {searchQuery && (
              <span className="inline-flex items-center space-x-1.5 px-2.5 py-1 rounded-full bg-slate-800 text-slate-200 border border-slate-700 text-[11px]">
                <span>Query: &ldquo;{searchQuery}&rdquo;</span>
                <button onClick={() => setSearchQuery('')} className="hover:text-rose-400">
                  <X className="w-3 h-3" />
                </button>
              </span>
            )}

            {selectedDecisions.map(d => (
              <span key={d} className="inline-flex items-center space-x-1.5 px-2.5 py-1 rounded-full bg-sky-500/15 text-sky-300 border border-sky-500/30 text-[11px]">
                <span>{d}</span>
                <button
                  onClick={() => setSelectedDecisions(selectedDecisions.filter(x => x !== d))}
                  className="hover:text-rose-400"
                >
                  <X className="w-3 h-3" />
                </button>
              </span>
            ))}

            {selectedAgent !== 'ALL' && (
              <span className="inline-flex items-center space-x-1.5 px-2.5 py-1 rounded-full bg-slate-800 text-slate-200 border border-slate-700 text-[11px]">
                <span>Agent: {selectedAgent}</span>
                <button onClick={() => setSelectedAgent('ALL')} className="hover:text-rose-400">
                  <X className="w-3 h-3" />
                </button>
              </span>
            )}

            {selectedRisk !== 'ALL' && (
              <span className="inline-flex items-center space-x-1.5 px-2.5 py-1 rounded-full bg-slate-800 text-slate-200 border border-slate-700 text-[11px]">
                <span>Risk: {selectedRisk}</span>
                <button onClick={() => setSelectedRisk('ALL')} className="hover:text-rose-400">
                  <X className="w-3 h-3" />
                </button>
              </span>
            )}

            {dateRange !== 'ALL' && (
              <span className="inline-flex items-center space-x-1.5 px-2.5 py-1 rounded-full bg-slate-800 text-slate-200 border border-slate-700 text-[11px]">
                <span>Time: {dateRange}</span>
                <button onClick={() => setDateRange('ALL')} className="hover:text-rose-400">
                  <X className="w-3 h-3" />
                </button>
              </span>
            )}

            <button
              onClick={handleClearAllFilters}
              className="text-[11px] font-semibold text-rose-400 hover:text-rose-300 underline ml-2"
            >
              Clear all
            </button>
          </div>
        )}
      </div>

      {/* 4. Error Banner */}
      {error && (
        <div className="rounded-xl p-4 bg-rose-500/15 border border-rose-500/30 flex items-center justify-between text-xs text-rose-300">
          <div className="flex items-center space-x-2">
            <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0" />
            <span>{error}</span>
          </div>
          <button
            onClick={() => loadData()}
            className="px-3 py-1.5 rounded-lg bg-rose-600 text-white font-semibold hover:bg-rose-500 transition"
          >
            Retry
          </button>
        </div>
      )}

      {/* 5. Timeline Table */}
      <div className="glass-panel rounded-2xl overflow-hidden border border-slate-800">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse min-w-[760px]">
            {/* Sticky Table Header */}
            <thead>
              <tr className="sticky top-0 bg-[#0c1222]/95 backdrop-blur z-10 border-b border-slate-800 text-[11px] font-mono uppercase text-slate-400">
                <th className="py-3.5 px-4 font-bold">Time</th>
                <th className="py-3.5 px-4 font-bold">Event</th>
                <th className="py-3.5 px-4 font-bold">Agent</th>
                <th className="py-3.5 px-4 font-bold">Action / Amount</th>
                <th className="py-3.5 px-4 font-bold">Risk</th>
                <th className="py-3.5 px-4 font-bold">Decision</th>
                <th className="py-3.5 px-4 font-bold">Actor</th>
              </tr>
            </thead>

            {/* Table Body */}
            <tbody className="divide-y divide-slate-800/60 text-xs">
              {loading ? (
                // Skeleton Rows
                Array.from({ length: 6 }).map((_, i) => (
                  <tr key={i} className="animate-pulse">
                    <td className="py-4 px-4"><div className="h-3.5 bg-slate-800 rounded w-16" /></td>
                    <td className="py-4 px-4"><div className="h-5 bg-slate-800 rounded-full w-28" /></td>
                    <td className="py-4 px-4"><div className="h-3.5 bg-slate-800 rounded w-24" /></td>
                    <td className="py-4 px-4"><div className="h-3.5 bg-slate-800 rounded w-32" /></td>
                    <td className="py-4 px-4"><div className="h-4 bg-slate-800 rounded-full w-14" /></td>
                    <td className="py-4 px-4"><div className="h-4 bg-slate-800 rounded-full w-16" /></td>
                    <td className="py-4 px-4"><div className="h-3.5 bg-slate-800 rounded w-20" /></td>
                  </tr>
                ))
              ) : entries.length === 0 ? (
                // Friendly Empty State
                <tr>
                  <td colSpan={7} className="py-16 text-center">
                    <div className="max-w-xs mx-auto space-y-3">
                      <div className="w-12 h-12 rounded-2xl bg-slate-800/80 border border-slate-700 flex items-center justify-center mx-auto text-slate-400">
                        <Filter className="w-6 h-6" />
                      </div>
                      <h3 className="text-sm font-bold text-white">No events match your filters</h3>
                      <p className="text-xs text-slate-500">
                        Try adjusting your search terms, date range, or decision type filters to view more activity.
                      </p>
                      {hasActiveFilters && (
                        <button
                          onClick={handleClearAllFilters}
                          className="px-3.5 py-1.5 rounded-lg bg-sky-600/80 hover:bg-sky-600 text-white text-xs font-semibold transition"
                        >
                          Reset All Filters
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ) : (
                // Rows
                entries.map((entry, idx) => {
                  const payload = entry.payload || {};
                  const decision = getEntryDecision(entry);
                  const decisionBadge = getDecisionBadge(decision);
                  const eventBadge = getEventBadge(entry.event_type);
                  const EventIcon = eventBadge.icon;
                  const riskPill = getRiskPill(payload.risk_level, payload.risk_score);
                  const isSelected = selectedEntry?.id === entry.id;

                  // Check if this entry is flagged in tamper result
                  const isBrokenEntry = verifyResult && !verifyResult.valid && (
                    entry.id === verifyResult.broken_entry_id ||
                    (verifyResult.broken_index !== undefined && idx === verifyResult.broken_index)
                  );

                  return (
                    <tr
                      key={entry.id}
                      onClick={() => setSelectedEntry(entry)}
                      className={`cursor-pointer transition-colors hover:bg-slate-800/50 ${
                        isSelected ? 'bg-sky-500/10' : isBrokenEntry ? 'bg-rose-500/15' : ''
                      }`}
                    >
                      {/* Time (relative + full on hover) */}
                      <td className="py-3 px-4 font-mono text-[11px] text-slate-400 whitespace-nowrap">
                        <span title={formatFullTime(entry.timestamp)}>
                          {formatRelativeTime(entry.timestamp)}
                        </span>
                      </td>

                      {/* Event badge with icon */}
                      <td className="py-3 px-4 whitespace-nowrap">
                        <span className={`inline-flex items-center space-x-1.5 px-2.5 py-1 rounded-full border text-[11px] font-semibold ${eventBadge.bg} ${eventBadge.color}`}>
                          <EventIcon className="w-3 h-3 shrink-0" />
                          <span>{entry.event_type}</span>
                        </span>
                      </td>

                      {/* Agent */}
                      <td className="py-3 px-4 whitespace-nowrap font-medium text-slate-200">
                        <div className="flex items-center space-x-1.5">
                          <Bot className="w-3.5 h-3.5 text-slate-500" />
                          <span>{payload.agent_id || entry.actor}</span>
                        </div>
                      </td>

                      {/* Action + amount */}
                      <td className="py-3 px-4 whitespace-nowrap font-mono text-[11px] text-slate-300">
                        <span>{payload.action || '—'}</span>
                        {payload.amount !== undefined && payload.amount > 0 && (
                          <span className="ml-2 font-bold text-emerald-400 font-sans">
                            {formatCurrency(payload.amount)}
                          </span>
                        )}
                      </td>

                      {/* Risk */}
                      <td className="py-3 px-4 whitespace-nowrap">
                        <span className={`inline-block px-2 py-0.5 rounded-full border text-[10px] font-mono font-bold ${riskPill.classes}`}>
                          {riskPill.label}
                        </span>
                      </td>

                      {/* Decision */}
                      <td className="py-3 px-4 whitespace-nowrap">
                        <span className={`inline-flex items-center space-x-1 px-2.5 py-0.5 rounded-full border text-[10px] font-mono font-bold ${decisionBadge.bg}`}>
                          <span className={`w-1.5 h-1.5 rounded-full ${decisionBadge.dot}`} />
                          <span>{decisionBadge.label}</span>
                        </span>
                      </td>

                      {/* Actor */}
                      <td className="py-3 px-4 whitespace-nowrap font-mono text-[11px] text-slate-400">
                        {entry.actor}
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        {/* 6. Pagination Footer */}
        <div className="px-5 py-3.5 border-t border-slate-800 bg-[#0c1222]/80 flex flex-col sm:flex-row items-center justify-between gap-3 text-xs text-slate-400">
          <div className="font-mono text-[11px]">
            Showing{' '}
            <span className="text-white font-bold">
              {entries.length === 0 ? 0 : (page - 1) * pageSize + 1}
            </span>
            {' '}-{' '}
            <span className="text-white font-bold">
              {Math.min(page * pageSize, totalCount || entries.length)}
            </span>
            {' '}of{' '}
            <span className="text-white font-bold">{totalCount || entries.length}</span> entries
          </div>

          <div className="flex items-center space-x-2">
            <button
              onClick={() => setPage(p => Math.max(p - 1, 1))}
              disabled={page <= 1 || loading}
              className="px-3 py-1.5 rounded-lg border border-slate-700 hover:border-slate-600 disabled:opacity-40 text-slate-300 font-medium transition flex items-center space-x-1"
            >
              <ChevronLeft className="w-3.5 h-3.5" />
              <span>Previous</span>
            </button>

            <span className="font-mono text-[11px] px-2 text-slate-400">
              Page {page} of {totalPages}
            </span>

            <button
              onClick={() => setPage(p => Math.min(p + 1, totalPages))}
              disabled={page >= totalPages || loading}
              className="px-3 py-1.5 rounded-lg border border-slate-700 hover:border-slate-600 disabled:opacity-40 text-slate-300 font-medium transition flex items-center space-x-1"
            >
              <span>Next</span>
              <ChevronRight className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </div>

      {/* 7. Drawer (Slide-Over Panel on row click) */}
      {selectedEntry && (
        <LogDetailDrawer
          entry={selectedEntry}
          previousEntry={entries.find(e => e.id === selectedEntry.id - 1)}
          onClose={() => setSelectedEntry(null)}
          onCopyHash={(hash) => navigator.clipboard.writeText(hash)}
        />
      )}

      {/* 8. Tamper Simulation Modal */}
      <TamperConfirmModal
        isOpen={tamperModalOpen}
        onClose={() => setTamperModalOpen(false)}
        onTamper={handleTamper}
        currentEntries={entries}
      />
    </div>
  );
}
