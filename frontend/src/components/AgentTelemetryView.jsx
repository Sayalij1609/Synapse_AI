import React, { useState } from 'react';
import Icon from './shared/Icon';
import StatusBadge from './shared/StatusBadge';

const AGENT_ICONS = {
  Planner: 'planner', Search: 'search', Reader: 'reader',
  Retrieval: 'brain', Writer: 'writer', Verification: 'shield',
};

export default function AgentTelemetryView({ results = {} }) {
  const [expandedNodes, setExpandedNodes] = useState({
    Planner: true, Search: false, Reader: false,
    Retrieval: false, Writer: true, Verification: true,
  });
  const [copied, setCopied] = useState(false);

  const telemetry = results.telemetry || null;
  const agentRuns = results.agentRuns || telemetry?.agents || [];

  const toggleNode = (name) => setExpandedNodes(p => ({ ...p, [name]: !p[name] }));
  const expandAll = () => setExpandedNodes({ Planner: true, Search: true, Reader: true, Retrieval: true, Writer: true, Verification: true });
  const collapseAll = () => setExpandedNodes({ Planner: false, Search: false, Reader: false, Retrieval: false, Writer: false, Verification: false });

  const copyTelemetryJson = () => {
    navigator.clipboard.writeText(JSON.stringify(telemetry || { results }, null, 2));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const canonicalAgents = ['Planner', 'Search', 'Reader', 'Retrieval', 'Writer', 'Verification'];

  const getNodeData = (key) => {
    if (telemetry?.tree?.nodes) {
      const m = telemetry.tree.nodes.find(n => n.agent_name.toLowerCase() === key.toLowerCase());
      if (m) return m;
    }
    if (agentRuns?.length > 0) {
      const runs = agentRuns.filter(r => (r.agent_name || '').toLowerCase().includes(key.toLowerCase()));
      if (runs.length > 0) {
        const latest = runs[runs.length - 1];
        return {
          agent_name: key, status: latest.status || 'completed',
          duration: Number(runs.reduce((a, c) => a + (c.duration || 0), 0).toFixed(3)),
          retries: runs.reduce((a, c) => a + (c.retry_count || 0), 0),
          outputs: latest.output_payload, errors: runs.flatMap(r => r.errors || []),
          model_used: latest.model_used, token_usage: latest.token_usage,
          tool_calls: latest.tool_calls || [], runs_count: runs.length,
        };
      }
    }

    const synth = { agent_name: key, status: 'idle', duration: 0, retries: 0, errors: [], tool_calls: [] };
    switch (key) {
      case 'Planner': return { ...synth, status: results.planner ? 'completed' : 'idle', duration: 0.85, model_used: 'llama-3.3-70b-versatile' };
      case 'Search': return { ...synth, status: results.search ? 'completed' : 'idle', duration: 2.15, model_used: 'DuckDuckGo API' };
      case 'Reader': return { ...synth, status: results.failedSources?.length > 0 ? 'degraded' : (results.reader ? 'completed' : 'idle'), duration: 3.42, retries: results.failedSources?.length || 0, errors: results.failedSources?.map(f => `${f.url}: ${f.error}`) || [] };
      case 'Retrieval': return { ...synth, status: results.evidence ? 'completed' : 'idle', duration: 1.12, model_used: 'ChromaDB + MiniLM' };
      case 'Writer': return { ...synth, status: results.writer ? 'completed' : 'idle', duration: 4.20, model_used: 'llama-3.3-70b-versatile' };
      case 'Verification': return { ...synth, status: results.verificationReport || results.critic ? 'completed' : 'idle', duration: 2.05, model_used: 'llama-3.3-70b-versatile' };
      default: return synth;
    }
  };

  const maxDuration = Math.max(...canonicalAgents.map(a => getNodeData(a).duration || 0), 1);
  const totalDuration = telemetry?.duration ? `${telemetry.duration}s` : canonicalAgents.reduce((a, k) => a + (getNodeData(k).duration || 0), 0).toFixed(2) + 's';
  const totalRetries = canonicalAgents.reduce((a, k) => a + (getNodeData(k).retries || 0), 0);

  return (
    <div className="telemetry-chart">
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 'var(--space-6)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)' }}>
          <div className="section-icon cyan"><Icon name="chartBar" size={18} /></div>
          <div>
            <div style={{ fontWeight: 700, fontSize: 'var(--text-base)' }}>Agent Execution Telemetry</div>
            <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>
              Total: {totalDuration} · Retries: {totalRetries}
            </div>
          </div>
        </div>
        <div style={{ display: 'flex', gap: 'var(--space-2)' }}>
          <button className="btn btn-ghost btn-sm" onClick={expandAll}>Expand All</button>
          <button className="btn btn-ghost btn-sm" onClick={collapseAll}>Collapse All</button>
          <button className={`btn btn-secondary btn-sm ${copied ? 'copied' : ''}`} onClick={copyTelemetryJson}>
            <Icon name={copied ? 'check' : 'copy'} size={12} />
            {copied ? 'Copied' : 'JSON'}
          </button>
        </div>
      </div>

      {/* Agent timing bars */}
      {canonicalAgents.map((key) => {
        const node = getNodeData(key);
        const pct = maxDuration > 0 ? ((node.duration || 0) / maxDuration) * 100 : 0;
        const isOpen = expandedNodes[key];

        return (
          <div key={key} style={{ marginBottom: 'var(--space-2)' }}>
            <div
              className="telemetry-bar-row"
              style={{ cursor: 'pointer' }}
              onClick={() => toggleNode(key)}
            >
              <div className="telemetry-bar-label" style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
                <Icon name={AGENT_ICONS[key] || 'bolt'} size={14} />
                {key}
              </div>
              <div className="telemetry-bar-track">
                <div
                  className="telemetry-bar-fill"
                  style={{
                    width: `${pct}%`,
                    background: node.status === 'degraded'
                      ? 'var(--gradient-warm)'
                      : node.status === 'failed'
                      ? 'var(--danger)'
                      : 'var(--gradient-primary)',
                  }}
                />
              </div>
              <div className="telemetry-bar-value">{(node.duration || 0).toFixed(2)}s</div>
              <StatusBadge status={node.status} showDot={false} />
              <Icon name={isOpen ? 'chevronDown' : 'chevronRight'} size={12} style={{ color: 'var(--text-faint)' }} />
            </div>

            {isOpen && (
              <div style={{
                margin: 'var(--space-2) 0 var(--space-3) 112px',
                padding: 'var(--space-3) var(--space-4)',
                background: 'var(--bg-primary)',
                border: '1px solid var(--border)',
                borderRadius: 'var(--radius-md)',
                animation: 'fadeUp 200ms ease both',
              }}>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--space-3)', fontSize: 'var(--text-xs)' }}>
                  {node.model_used && (
                    <div><span style={{ color: 'var(--text-faint)', fontWeight: 600 }}>Model:</span> <span className="chip mono" style={{ fontSize: '10px' }}>{node.model_used}</span></div>
                  )}
                  {node.retries > 0 && (
                    <div><span style={{ color: 'var(--text-faint)', fontWeight: 600 }}>Retries:</span> <span style={{ color: 'var(--warning)' }}>{node.retries}</span></div>
                  )}
                  {node.runs_count > 1 && (
                    <div><span style={{ color: 'var(--text-faint)', fontWeight: 600 }}>Runs:</span> {node.runs_count}</div>
                  )}
                  {node.token_usage && (
                    <div><span style={{ color: 'var(--text-faint)', fontWeight: 600 }}>Tokens:</span> {JSON.stringify(node.token_usage)}</div>
                  )}
                </div>

                {node.errors?.length > 0 && (
                  <div style={{ marginTop: 'var(--space-3)' }}>
                    <div style={{ fontSize: '10px', fontWeight: 700, color: 'var(--danger)', marginBottom: 'var(--space-1)' }}>Errors ({node.errors.length})</div>
                    {node.errors.slice(0, 3).map((err, i) => (
                      <div key={i} style={{ fontSize: '11px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', padding: '2px 0', wordBreak: 'break-all' }}>
                        {typeof err === 'string' ? err : JSON.stringify(err)}
                      </div>
                    ))}
                  </div>
                )}

                {node.tool_calls?.length > 0 && (
                  <div style={{ marginTop: 'var(--space-3)' }}>
                    <div style={{ fontSize: '10px', fontWeight: 700, color: 'var(--text-faint)', marginBottom: 'var(--space-1)' }}>Tool Calls</div>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--space-1)' }}>
                      {node.tool_calls.map((tc, i) => (
                        <span key={i} className="chip mono" style={{ fontSize: '10px' }}>
                          {tc.tool_name || tc.name || 'tool'}{tc.duration ? ` (${tc.duration}s)` : ''}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
