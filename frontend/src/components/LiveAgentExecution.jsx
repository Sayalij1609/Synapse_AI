import React from 'react';
import Icon from './shared/Icon';
import StatusBadge from './shared/StatusBadge';

const LIVE_AGENTS = [
  { key: 'Planner',      icon: 'planner', name: 'Planner',    desc: 'Research Decomposition' },
  { key: 'Search',       icon: 'search',  name: 'Search',     desc: 'Live Web Discovery' },
  { key: 'Reader',       icon: 'reader',  name: 'Reader',     desc: 'Content Extraction' },
  { key: 'Retrieval',    icon: 'brain',   name: 'Retrieval',  desc: 'Vector Indexing' },
  { key: 'Writer',       icon: 'writer',  name: 'Writer',     desc: 'Report Synthesis' },
  { key: 'Verification', icon: 'shield',  name: 'Verifier',   desc: 'Claim Audit' },
];

function getElapsed(agent) {
  if (!agent?.startTime) return null;
  const end = agent.endTime || Date.now();
  return ((end - agent.startTime) / 1000).toFixed(1);
}

export default function LiveAgentExecution({ liveAgents, agentStatuses, verificationState }) {
  const getEffectiveStatus = (key) => {
    if (liveAgents[key]?.status) return liveAgents[key].status;
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
  const completedCount = LIVE_AGENTS.filter(a => getEffectiveStatus(a.key) === 'completed').length;
  const progress = (completedCount / LIVE_AGENTS.length) * 100;

  return (
    <div className="pipeline-container">
      <div className="pipeline-header">
        <div className="pipeline-header-left">
          <div className="section-icon accent">
            <Icon name="bolt" size={18} />
          </div>
          <div>
            <div className="pipeline-title">Multi-Agent Execution Pipeline</div>
            <div className="pipeline-subtitle">
              {anyRunning
                ? 'Pipeline execution active…'
                : completedCount > 0 && completedCount === LIVE_AGENTS.length
                ? 'Pipeline run complete'
                : 'Ready for query'}
            </div>
          </div>
        </div>

        {verificationState && verificationState.currentIteration > 0 && (
          <div className="cycle-badge">
            <Icon name="refresh" size={12} />
            Cycle {verificationState.currentIteration}/{verificationState.maxIterations}
          </div>
        )}
      </div>

      <div className="agent-track">
        {LIVE_AGENTS.map((agent, idx) => {
          const status = getEffectiveStatus(agent.key);
          const agentData = liveAgents[agent.key] || {};
          const elapsed = getElapsed(agentData);

          // Determine connector status
          const prevStatus = idx > 0 ? getEffectiveStatus(LIVE_AGENTS[idx - 1].key) : null;
          const connectorClass = prevStatus === 'completed'
            ? (status === 'running' ? 'active' : status === 'completed' ? 'complete' : '')
            : '';

          return (
            <React.Fragment key={agent.key}>
              {idx > 0 && (
                <div className={`flow-connector ${connectorClass} connector-step-${idx}`}>
                  <div className="flow-line" />
                  <span className="flow-arrow">→</span>
                </div>
              )}
              <div className={`agent-node ${status} agent-node-${agent.key.toLowerCase()}`} data-agent={agent.key.toLowerCase()}>
                <div className="agent-node-icon">
                  {status === 'completed' ? (
                    <Icon name="check" size={20} strokeWidth={2.5} />
                  ) : (
                    <Icon name={agent.icon} size={20} />
                  )}
                  {status === 'running' && <div className="agent-pulse-ring" />}
                </div>
                <div className="agent-node-name">{agent.name}</div>
                <div className="agent-node-desc">{agent.desc}</div>
                {elapsed && <div className="agent-elapsed">{elapsed}s</div>}
                <StatusBadge status={status} />
              </div>
            </React.Fragment>
          );
        })}
      </div>

      {progress > 0 && (
        <div className="pipeline-progress">
          <div className="pipeline-progress-bar" style={{ width: `${progress}%` }} />
        </div>
      )}
    </div>
  );
}
