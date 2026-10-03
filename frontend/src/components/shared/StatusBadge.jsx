import React from 'react';

/**
 * StatusBadge — Animated status indicator with dot + label.
 * Statuses: idle, running, completed, degraded, failed, pending
 */
export default function StatusBadge({ status = 'idle', label, showDot = true, className = '' }) {
  const displayLabel = label || defaultLabel(status);

  return (
    <span className={`status-badge ${status} ${className}`}>
      {showDot && <span className={`status-dot ${status}`} />}
      {status === 'running' && <span className="spinner sm" />}
      {displayLabel}
    </span>
  );
}

function defaultLabel(status) {
  switch (status) {
    case 'running':     return 'Running';
    case 'completed':   return 'Complete';
    case 'degraded':    return 'Degraded';
    case 'failed':      return 'Failed';
    case 'pending':     return 'Pending';
    case 'in_progress': return 'In Progress';
    default:            return 'Idle';
  }
}
