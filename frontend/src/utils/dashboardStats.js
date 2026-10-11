/**
 * Pure dashboard metrics calculation and safe number formatting utilities.
 */

/**
 * Compute dashboard stats from agents array, ledger data, and approvals array.
 */
export function computeDashboardStats(agents = [], ledgerData = {}, approvals = []) {
  const agentList = Array.isArray(agents) ? agents : (agents?.items || []);
  const approvalList = Array.isArray(approvals) ? approvals : (approvals?.items || []);

  const activeAgents = agentList.filter(
    a => String(a?.status || '').trim().toLowerCase() === 'active'
  ).length;

  const pausedAgents = agentList.filter(
    a => String(a?.status || '').trim().toLowerCase() === 'paused'
  ).length;

  const revokedAgents = agentList.filter(
    a => String(a?.status || '').trim().toLowerCase() === 'revoked'
  ).length;

  let ledgerTotal = 0;
  if (typeof ledgerData?.total === 'number' && Number.isFinite(ledgerData.total)) {
    ledgerTotal = ledgerData.total;
  } else if (typeof ledgerData?.count === 'number' && Number.isFinite(ledgerData.count)) {
    ledgerTotal = ledgerData.count;
  } else if (Array.isArray(ledgerData)) {
    ledgerTotal = ledgerData.length;
  } else if (Array.isArray(ledgerData?.items)) {
    ledgerTotal = ledgerData.items.length;
  }

  const pendingApprovals = approvalList.filter(a => {
    const s = String(a?.status || '').trim().toLowerCase();
    return s === 'pending' || s === 'pending_approval';
  }).length;

  return {
    activeAgents,
    pausedAgents,
    revokedAgents,
    totalAgents: agentList.length,
    ledgerTotal,
    pendingApprovals
  };
}

/**
 * Safe counter formatting: never returns Infinity or NaN.
 * Shows '-' if invalid/empty, formats large numbers with thousands separators.
 */
export function formatCounterValue(val, isLoading = false) {
  if (isLoading) return '—';
  if (val === null || val === undefined || val === '') return '—';
  const num = Number(val);
  if (!Number.isFinite(num)) return '—';
  return num.toLocaleString('en-US');
}
