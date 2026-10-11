import React from 'react';
import { Shield, ShieldAlert, LogOut, User, RefreshCw } from 'lucide-react';

export default function Navbar({ user, onLogout }) {
  const getRoleBadge = (role) => {
    switch (role) {
      case 'admin':
        return 'bg-purple-900/60 text-purple-300 border-purple-500/40';
      case 'risk_lead':
        return 'bg-rose-900/60 text-rose-300 border-rose-500/40';
      case 'executive':
        return 'bg-amber-900/60 text-amber-300 border-amber-500/40';
      case 'approver':
        return 'bg-sky-900/60 text-sky-300 border-sky-500/40';
      case 'auditor':
        return 'bg-emerald-900/60 text-emerald-300 border-emerald-500/40';
      default:
        return 'bg-slate-800 text-slate-300 border-slate-700';
    }
  };

  return (
    <header className="h-16 border-b border-slate-800 bg-[#0b1324]/90 backdrop-blur sticky top-0 z-40 px-6 flex items-center justify-between">
      <div className="flex items-center space-x-3">
        <div className="p-2 rounded-lg bg-sky-500/10 border border-sky-500/30 text-sky-400">
          <Shield className="w-6 h-6" />
        </div>
        <div>
          <div className="flex items-center space-x-2">
            <span className="font-extrabold text-lg tracking-wider bg-gradient-to-r from-sky-400 via-indigo-300 to-purple-400 bg-clip-text text-transparent">
              WARDEN
            </span>
            <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-sky-500/20 text-sky-300 font-semibold uppercase tracking-wider">
              Control OS
            </span>
          </div>
          <p className="text-xs text-slate-400 -mt-0.5">AI Agent Pre-Execution Control & Accountability</p>
        </div>
      </div>

      <div className="flex items-center space-x-4">
        {/* Backend Status indicator */}
        <div className="flex items-center space-x-2 px-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs font-mono">
          <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
          <span>PRE-EXECUTION ACTIVE</span>
        </div>

        {/* User Badge */}
        {user && (
          <div className="flex items-center space-x-3 pl-2 border-l border-slate-800">
            <div className="flex items-center space-x-2">
              <div className="w-8 h-8 rounded-full bg-slate-800 border border-slate-700 flex items-center justify-center text-slate-300">
                <User className="w-4 h-4" />
              </div>
              <div className="text-left hidden sm:block">
                <div className="text-xs font-semibold text-slate-200">{user.full_name || user.username}</div>
                <div className="text-[10px] text-slate-400 font-mono">@{user.username}</div>
              </div>
            </div>

            <span className={`text-[11px] font-mono uppercase font-bold px-2 py-0.5 rounded border ${getRoleBadge(user.role)}`}>
              {user.role}
            </span>

            <button
              onClick={onLogout}
              title="Sign Out"
              className="p-1.5 text-slate-400 hover:text-rose-400 hover:bg-rose-500/10 rounded-lg transition"
            >
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        )}
      </div>
    </header>
  );
}
