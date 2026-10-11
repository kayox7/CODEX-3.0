import React from 'react';
import {
  LayoutDashboard,
  Bot,
  CheckSquare,
  FileCheck2,
  FileSpreadsheet,
  AlertOctagon,
  Sparkles
} from 'lucide-react';

export default function Sidebar({ activeTab, onSelectTab, pendingApprovalsCount = 0 }) {
  const navItems = [
    { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
    { id: 'agents', label: 'Agent Passports', icon: Bot },
    {
      id: 'approvals',
      label: 'Approvals Queue',
      icon: CheckSquare,
      badge: pendingApprovalsCount > 0 ? pendingApprovalsCount : null,
      badgeColor: 'bg-amber-500/20 text-amber-300 border-amber-500/30'
    },
    { id: 'ledger', label: 'Activity Logs', icon: FileCheck2 },
    { id: 'reports', label: 'Audit Reports', icon: FileSpreadsheet },
  ];

  return (
    <aside className="w-64 border-r border-slate-800 bg-[#0c1222] flex flex-col justify-between p-4 shrink-0">
      <div className="space-y-1">
        <div className="px-3 py-2 text-[11px] font-bold tracking-wider text-slate-500 uppercase font-mono">
          Governance Controls
        </div>
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = activeTab === item.id;
          return (
            <button
              key={item.id}
              onClick={() => onSelectTab(item.id)}
              className={`w-full flex items-center justify-between px-3 py-2.5 rounded-lg text-sm font-medium transition ${
                isActive
                  ? 'bg-sky-500/15 text-sky-400 border border-sky-500/30 font-semibold'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60'
              }`}
            >
              <div className="flex items-center space-x-3">
                <Icon className={`w-4 h-4 ${isActive ? 'text-sky-400' : 'text-slate-500'}`} />
                <span>{item.label}</span>
              </div>
              {item.badge && (
                <span className={`text-[10px] font-mono px-2 py-0.5 rounded-full border font-bold ${item.badgeColor}`}>
                  {item.badge}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* Control Layer Footer Card */}
      <div className="p-3.5 rounded-xl bg-slate-900/80 border border-slate-800 text-xs space-y-2">
        <div className="flex items-center space-x-2 text-sky-400 font-semibold">
          <AlertOctagon className="w-4 h-4 text-rose-400" />
          <span>Fail-Closed Engine</span>
        </div>
        <p className="text-slate-400 text-[11px] leading-relaxed">
          Unregistered actions, policy violations, or SLA expirations are permanently denied at runtime.
        </p>
      </div>
    </aside>
  );
}
