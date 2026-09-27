import React from 'react';

const AGENTS = [
  { key: 'planner', emoji: '📋', name: 'Planner Agent', desc: 'Research Decomposition' },
  { key: 'search', emoji: '🔍', name: 'Search Agent', desc: 'Live Web Discovery' },
  { key: 'reader', emoji: '📄', name: 'Reader Agent', desc: 'Content Extraction' },
  { key: 'writer', emoji: '✍️', name: 'Writer Agent', desc: 'Executive Synthesis' },
  { key: 'critic', emoji: '⭐', name: 'Critic Agent', desc: 'Quality Audit' },
];

function getTagClass(status) {
  if (status === 'running') return 'agent-tag running';
  if (status === 'done') return 'agent-tag done-tag';
  return 'agent-tag idle';
}

function getCardClass(status) {
  let cls = 'pipeline-node-card';
  if (status === 'running') cls += ' active';
  if (status === 'done') cls += ' done';
  return cls;
}

export default function Pipeline({ agentStatuses }) {
  return (
    <div className="pipeline-console">
      <div className="console-header">
        <span className="console-title">⚡ Multi-Agent Execution Pipeline</span>
        <span className="console-status">
          {Object.values(agentStatuses).includes('running')
            ? '● Pipeline Execution Active'
            : Object.values(agentStatuses).every((s) => s === 'done')
            ? '✓ Pipeline Run Complete'
            : 'Ready for Query'}
        </span>
      </div>

      <div className="pipeline-flow-track">
        {AGENTS.map(({ key, emoji, name, desc }, idx) => (
          <React.Fragment key={key}>
            <div className={getCardClass(agentStatuses[key])}>
              <div className="node-icon-wrapper">
                <span className="node-emoji">{emoji}</span>
              </div>
              <div className="node-details">
                <div className="node-name">{name}</div>
                <div className="node-desc">{desc}</div>
              </div>
              <span className={getTagClass(agentStatuses[key])}>
                {agentStatuses[key] || 'idle'}
              </span>
            </div>
            {idx < AGENTS.length - 1 && (
              <div className={`flow-connector${agentStatuses[key] === 'done' ? ' complete' : ''}`}>
                <div className="connector-line" />
                <span className="connector-arrow">➔</span>
              </div>
            )}
          </React.Fragment>
        ))}
      </div>
    </div>
  );
}
