import React, { useEffect, useState, useCallback } from 'react';
import { api } from '../api';
import {
  FileCheck2, ShieldCheck, ShieldX, RefreshCw,
  Loader2, Hash, AlertTriangle, ChevronDown, ChevronUp
} from 'lucide-react';

function EntryRow({ entry, tampered }) {
  const [expanded, setExpanded] = useState(false);
  const isBroken = tampered && tampered.first_broken_index !== undefined &&
    entry.index >= tampered.first_broken_index;

  return (
    <div className={`border-b border-slate-800/60 last:border-0 ${isBroken ? 'bg-rose-500/5' : ''}`}>
      <button
        onClick={() => setExpanded(e => !e)}
        className="w-full flex items-center justify-between py-3 px-4 hover:bg-slate-800/30 transition text-left"
      >
        <div className="flex items-center space-x-4 min-w-0">
          <span className="font-mono text-[11px] text-slate-500 w-10 shrink-0">#{entry.index ?? entry.id}</span>
          {isBroken
            ? <AlertTriangle className="w-3.5 h-3.5 text-rose-400 shrink-0" />
            : <div className="w-3.5 h-3.5 rounded-full bg-emerald-500/30 border border-emerald-500/50 shrink-0" />
          }
          <div className="min-w-0">
            <span className="text-xs font-semibold text-slate-200">{entry.event_type}</span>
            <span className="ml-2 text-[10px] font-mono text-slate-500 truncate">{entry.agent_id}</span>
          </div>
        </div>
        <div className="flex items-center space-x-3 shrink-0">
          <span className="text-[10px] font-mono text-slate-600 hidden sm:block">
            {entry.hash?.slice(0, 12)}…
          </span>
          {expanded ? <ChevronUp className="w-3.5 h-3.5 text-slate-500" /> : <ChevronDown className="w-3.5 h-3.5 text-slate-500" />}
        </div>
      </button>
      {expanded && (
        <div className="px-4 pb-4">
          <pre className="text-[10px] font-mono text-slate-400 bg-slate-950/60 rounded-lg p-3 overflow-x-auto">
            {JSON.stringify(entry, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}

export default function LedgerExplorer() {
  const [entries, setEntries] = useState([]);
  const [loading, setLoading] = useState(true);
  const [verifyResult, setVerifyResult] = useState(null);
  const [verifying, setVerifying] = useState(false);
  const [tampering, setTampering] = useState(false);
  const [tamperTarget, setTamperTarget] = useState('');
  const [tamperNote, setTamperNote] = useState('Simulated tamper via console');
  const [tampered, setTampered] = useState(null);

  const load = useCallback(async () => {
    try {
      const data = await api.getLedger(100);
      setEntries(Array.isArray(data) ? data : (data.items ?? []));
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleVerify = async () => {
    setVerifying(true);
    setTampered(null);
    try {
      const res = await api.verifyLedger();
      setVerifyResult(res);
      if (res.valid === false) {
        setTampered(res);
      }
    } catch (e) {
      setVerifyResult({ error: e.message });
    } finally {
      setVerifying(false);
    }
  };

  const handleTamper = async () => {
    if (!tamperTarget) return;
    setTampering(true);
    setVerifyResult(null);
    setTampered(null);
    try {
      await api.tamperLedger(tamperTarget, tamperNote);
      await load();
    } catch (e) {
      alert(e.message);
    } finally {
      setTampering(false);
    }
  };

  return (
    <div className="p-6 space-y-5 max-w-5xl mx-auto">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h2 className="text-2xl font-extrabold text-white">Ledger Explorer</h2>
          <p className="text-slate-500 text-sm mt-0.5">Cryptographic append-only audit chain</p>
        </div>
        <button onClick={load} className="p-2 rounded-lg border border-slate-700 text-slate-400 hover:text-white hover:border-slate-600 transition">
          <RefreshCw className="w-4 h-4" />
        </button>
      </div>

      {/* Controls */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Verify */}
        <div className="glass-panel rounded-xl p-5 space-y-3">
          <h3 className="font-bold text-sm text-white flex items-center space-x-2">
            <ShieldCheck className="w-4 h-4 text-emerald-400" />
            <span>Verify Chain Integrity</span>
          </h3>
          <p className="text-xs text-slate-500">Checks SHA-256 hash chain from genesis to HEAD.</p>
          <button
            id="verify-chain-btn"
            onClick={handleVerify}
            disabled={verifying}
            className="w-full py-2.5 bg-emerald-600/80 hover:bg-emerald-600 disabled:opacity-50 text-white font-semibold rounded-lg text-sm transition flex items-center justify-center space-x-2"
          >
            {verifying ? <Loader2 className="w-4 h-4 animate-spin" /> : <ShieldCheck className="w-4 h-4" />}
            <span>{verifying ? 'Verifying...' : 'Verify Chain'}</span>
          </button>

          {verifyResult && (
            <div className={`rounded-lg p-3 border text-xs ${
              verifyResult.valid
                ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400'
                : 'bg-rose-500/10 border-rose-500/20 text-rose-400'
            }`}>
              <div className="flex items-center space-x-2 font-bold mb-1">
                {verifyResult.valid ? <ShieldCheck className="w-4 h-4" /> : <ShieldX className="w-4 h-4" />}
                <span>{verifyResult.valid ? 'Chain VALID' : 'Chain COMPROMISED'}</span>
              </div>
              {!verifyResult.valid && verifyResult.first_broken_index !== undefined && (
                <p className="font-mono">First broken at index: <strong>{verifyResult.first_broken_index}</strong></p>
              )}
              {verifyResult.error && <p>{verifyResult.error}</p>}
            </div>
          )}
        </div>

        {/* Tamper Simulation */}
        <div className="glass-panel rounded-xl p-5 space-y-3">
          <h3 className="font-bold text-sm text-white flex items-center space-x-2">
            <ShieldX className="w-4 h-4 text-rose-400" />
            <span>Simulate Tamper (Dev)</span>
          </h3>
          <p className="text-xs text-slate-500">Injects a hash mutation into an entry to test detection.</p>
          <div className="space-y-2">
            <input
              type="text"
              placeholder="Entry ID (e.g. 3)"
              value={tamperTarget}
              onChange={e => setTamperTarget(e.target.value)}
              className="w-full text-xs bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-slate-300 placeholder-slate-600 focus:outline-none focus:border-rose-500 transition"
            />
            <input
              type="text"
              placeholder="Tamper note"
              value={tamperNote}
              onChange={e => setTamperNote(e.target.value)}
              className="w-full text-xs bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-slate-300 placeholder-slate-600 focus:outline-none focus:border-rose-500 transition"
            />
          </div>
          <button
            id="tamper-btn"
            onClick={handleTamper}
            disabled={tampering || !tamperTarget}
            className="w-full py-2.5 bg-rose-600/70 hover:bg-rose-600/90 disabled:opacity-50 text-white font-semibold rounded-lg text-sm transition flex items-center justify-center space-x-2"
          >
            {tampering ? <Loader2 className="w-4 h-4 animate-spin" /> : <AlertTriangle className="w-4 h-4" />}
            <span>{tampering ? 'Injecting...' : 'Inject Tamper'}</span>
          </button>
        </div>
      </div>

      {/* Ledger Table */}
      <div className="glass-panel rounded-xl overflow-hidden">
        <div className="px-4 py-3 border-b border-slate-800 flex items-center justify-between">
          <h3 className="text-sm font-bold text-white flex items-center space-x-2">
            <Hash className="w-4 h-4 text-sky-400" />
            <span>Ledger Entries</span>
          </h3>
          <span className="text-xs text-slate-500 font-mono">{entries.length} entries</span>
        </div>
        {loading ? (
          <div className="flex items-center justify-center h-32">
            <Loader2 className="w-6 h-6 text-sky-400 animate-spin" />
          </div>
        ) : entries.length === 0 ? (
          <div className="text-center py-12 text-slate-500 text-sm">No ledger entries yet</div>
        ) : (
          <div className="divide-y divide-slate-800/40 max-h-[500px] overflow-y-auto">
            {[...entries].reverse().map(e => (
              <EntryRow key={e.id} entry={e} tampered={tampered} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
