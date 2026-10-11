/**
 * Frontend unit test for Dashboard counter calculations and safe formatting.
 * Runs via Node test runner: node --test frontend/src/dashboard_counters.test.js
 */
import test from 'node:test';
import assert from 'node:assert/strict';
import { computeDashboardStats, formatCounterValue } from './utils/dashboardStats.js';

test('computeDashboardStats: correctly counts active, paused, revoked agents case-insensitively', () => {
  const agents = [
    { id: 1, name: 'Agent 1', status: 'active' },
    { id: 2, name: 'Agent 2', status: 'ACTIVE' },
    { id: 3, name: 'Agent 3', status: 'paused' },
    { id: 4, name: 'Agent 4', status: 'PAUSED' },
    { id: 5, name: 'Agent 5', status: 'Paused' },
    { id: 6, name: 'Agent 6', status: 'revoked' },
    { id: 7, name: 'Agent 7', status: 'REVOKED' }
  ];

  const stats = computeDashboardStats(agents, { total: 42 }, []);
  assert.strictEqual(stats.activeAgents, 2, 'Should count exactly 2 active agents');
  assert.strictEqual(stats.pausedAgents, 3, 'Should count exactly 3 paused agents');
  assert.strictEqual(stats.revokedAgents, 2, 'Should count exactly 2 revoked agents separately');
  assert.strictEqual(stats.totalAgents, 7, 'Total agents should be 7');
});

test('computeDashboardStats: extracts real ledger total count without infinity', () => {
  // Scenario 1: Object with total field
  const stats1 = computeDashboardStats([], { total: 15420, items: [] }, []);
  assert.strictEqual(stats1.ledgerTotal, 15420);

  // Scenario 2: Object with count field
  const stats2 = computeDashboardStats([], { count: 350 }, []);
  assert.strictEqual(stats2.ledgerTotal, 350);

  // Scenario 3: Array fallback
  const stats3 = computeDashboardStats([], [{}, {}, {}], []);
  assert.strictEqual(stats3.ledgerTotal, 3);
});

test('computeDashboardStats: counts pending approvals case-insensitively', () => {
  const approvals = [
    { id: 1, status: 'PENDING' },
    { id: 2, status: 'pending' },
    { id: 3, status: 'PENDING_APPROVAL' },
    { id: 4, status: 'APPROVED' },
    { id: 5, status: 'REJECTED' },
    { id: 6, status: 'TIMED_OUT' }
  ];

  const stats = computeDashboardStats([], {}, approvals);
  assert.strictEqual(stats.pendingApprovals, 3, 'Should count 3 pending approvals');
});

test('formatCounterValue: never renders Infinity or NaN, formats with thousands separators', () => {
  assert.strictEqual(formatCounterValue(15420), '15,420');
  assert.strictEqual(formatCounterValue(0), '0');
  assert.strictEqual(formatCounterValue(1000000), '1,000,000');
  assert.strictEqual(formatCounterValue(Infinity), '—', 'Infinity must never render');
  assert.strictEqual(formatCounterValue(-Infinity), '—', '-Infinity must never render');
  assert.strictEqual(formatCounterValue(NaN), '—', 'NaN must never render');
  assert.strictEqual(formatCounterValue(null), '—', 'null must render —');
  assert.strictEqual(formatCounterValue(undefined), '—', 'undefined must render —');
  assert.strictEqual(formatCounterValue(''), '—', 'empty string must render —');
  assert.strictEqual(formatCounterValue(5, true), '—', 'loading state must render —');
});
