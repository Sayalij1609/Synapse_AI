import React from 'react';

/**
 * LiveAgentExecution — Shows the 6-agent pipeline with live status:
 * Planner → Search → Reader → Evidence Retrieval → Writer → Verification
 *
 * Each agent shows: status, duration, outputs count, errors, retries
 * Replaces the old 5-agent Pipeline component with the full autonomous architecture.
 */

const LIVE_AGENTS = [
  { key: 'Planner', emoji: '📋', name: 'Planner', desc: 'Research Decomposition', color: '#6C5CE7' },
  { key: 'Search', emoji: '🔍', name: 'Search', desc: 'Live Web Discovery', color: '#0984E3' },
  { key: 'Reader', emoji: '📖', name: 'Reader', desc: 'Content Extraction', color: '#00B894' },
  { key: 'Retrieval', emoji: '🧠', name: 'Evidence Retrieval', desc: 'Vector Indexing & Semantic Search', color: '#E17055' },
  { key: 'Writer', emoji: '✍️', name: 'Writer', desc: 'Grounded Report Synthesis', color: '#2B2554' },
  { key: 'Verification', emoji: '🛡️', name: 'Verification', desc: 'Autonomous Claim Audit', color: '#D95365' },
];

function getElapsed(agent) {
  if (!agent?.startTime) return null;
  const end = agent.endTime || Date.now();
  return ((end - agent.startTime) / 1000).toFixed(1);
}

function getStatusClass(status) {
  switch (status) {
    case 'running': return 'live-agent-running';
    case 'completed': return 'live-agent-done';
    case 'degraded': return 'live-agent-degraded';
    case 'failed': return 'live-agent-failed';
    default: return 'live-agent-idle';
  }
}

function getStatusLabel(status) {
  switch (status) {
    case 'running': return 'Running';
    case 'completed': return 'Complete';
    case 'degraded': return 'Degraded';
    case 'failed': return 'Failed';
    default: return 'Pending';
  }
}

export default function LiveAgentExecution({ liveAgents, agentStatuses, verificationState }) {
  // Derive status: prefer liveAgents, fallback to legacy agentStatuses
  const getEffectiveStatus = (key) => {
    if (liveAgents[key]?.status) return liveAgents[key].status;
    // Map legacy keys
    const legacyMap = { Planner: 'planner', Search: 'search', Reader: 'reader', Writer: 'writer', Verification: 'critic' };
    const legKey = legacyMap[key];
    if (legKey && agentStatuses[legKey]) {
      const ls = agentStatuses[legKey];
      if (ls === 'done') return 'completed';
      return ls;
    }
    return 'idle';
  };

  const anyRunning = LIVE_AGENTS.some(a => getEffectiveStatus(a.key) === 'running');
  const allDone = LIVE_AGENTS.every(a => ['completed', 'idle'].includes(getEffectiveStatus(a.key)));

  return (
    <div className="live-execution-container">
      <div className="live-exec-header">
        <div className="live-exec-header-left">
          <span className="live-exec-icon">⚡</span>
          <div>
            <h3 className="live-exec-title">Multi-Agent Execution Pipeline</h3>
            <span className="live-exec-subtitle">
              {anyRunning
                ? '● Pipeline Execution Active'
                : allDone && Object.keys(liveAgents).length > 0
                ? '✓ Pipeline Run Complete'
                : 'Ready for Query'}
            </span>
          </div>
        </div>

        {/* Verification Cycle Indicator */}
        {verificationState && verificationState.currentIteration > 0 && (
          <div className="verification-cycle-badge">
            <span className="cycle-icon">🔄</span>
            <span className="cycle-text">
              Verification Cycle {verificationState.currentIteration}/{verificationState.maxIterations}
            </span>
          </div>
        )}
      </div>

      <div className="live-agents-track">
        {LIVE_AGENTS.map((agent, idx) => {
          const status = getEffectiveStatus(agent.key);
          const agentData = liveAgents[agent.key] || {};
          const elapsed = getElapsed(agentData);

          return (
            <React.Fragment key={agent.key}>
              <div className={`live-agent-card ${getStatusClass(status)}`}>
                <div className="live-agent-icon-wrap" style={{ '--agent-color': agent.color }}>
                  <span className="live-agent-emoji">{agent.emoji}</span>
                  {status === 'running' && <div className="live-agent-pulse" />}
                </div>

                <div className="live-agent-info">
                  <div className="live-agent-name">{agent.name}</div>
                  <div className="live-agent-desc">{agent.desc}</div>
                  {elapsed && (
                    <div className="live-agent-elapsed">{elapsed}s</div>
                  )}
                </div>

                <div className={`live-agent-status-tag ${getStatusClass(status)}`}>
                  {status === 'running' && <span className="status-dot-anim" />}
                  {getStatusLabel(status)}
                </div>
              </div>

              {idx < LIVE_AGENTS.length - 1 && (
                <div className={`live-flow-connector ${status === 'completed' ? 'complete' : ''}`}>
                  <div className="live-connector-line" />
                  <span className="live-connector-arrow">→</span>
                </div>
              )}
            </React.Fragment>
          );
        })}
      </div>
    </div>
  );
}
