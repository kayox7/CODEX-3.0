import React, { useState, useEffect } from 'react';
import { api, getToken, getCurrentUser } from './api';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import AgentRegistry from './pages/AgentRegistry';
import Approvals from './pages/Approvals';
import LedgerExplorer from './pages/LedgerExplorer';
import Reports from './pages/Reports';
import Sidebar from './components/Sidebar';
import Navbar from './components/Navbar';

export default function App() {
  const [user, setUser] = useState(getCurrentUser());
  const [activeTab, setActiveTab] = useState('dashboard');
  const [pendingCount, setPendingCount] = useState(0);

  // Listen for session expiry events (401 from api.js)
  useEffect(() => {
    const handler = () => { setUser(null); };
    window.addEventListener('warden_auth_expired', handler);
    return () => window.removeEventListener('warden_auth_expired', handler);
  }, []);

  // Poll pending approvals count for badge
  useEffect(() => {
    if (!user) return;
    const fetchPending = async () => {
      try {
        const data = await api.getApprovals({ status: 'PENDING_APPROVAL' });
        setPendingCount(Array.isArray(data) ? data.length : (data.items?.length ?? 0));
      } catch {
        // silently ignore
      }
    };
    fetchPending();
    const iv = setInterval(fetchPending, 15000);
    return () => clearInterval(iv);
  }, [user]);

  const handleLogin = (userData) => setUser(userData);
  const handleLogout = () => {
    api.logout();
    setUser(null);
  };

  if (!user) {
    return <Login onLogin={handleLogin} />;
  }

  const pages = {
    dashboard: <Dashboard user={user} onSelectTab={setActiveTab} />,
    agents: <AgentRegistry user={user} />,
    approvals: <Approvals user={user} />,
    ledger: <LedgerExplorer />,
    reports: <Reports />,
  };

  return (
    <div className="flex flex-col h-screen overflow-hidden bg-[#090d16]">
      <Navbar user={user} onLogout={handleLogout} />
      <div className="flex flex-1 overflow-hidden">
        <Sidebar
          activeTab={activeTab}
          onSelectTab={setActiveTab}
          pendingApprovalsCount={pendingCount}
        />
        <main className="flex-1 overflow-y-auto">
          {pages[activeTab] || pages.dashboard}
        </main>
      </div>
    </div>
  );
}
