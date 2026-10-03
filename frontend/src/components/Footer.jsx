import React from 'react';
import Icon from './shared/Icon';

export default function Footer() {
  const currentYear = new Date().getFullYear();

  const AGENT_BADGES = [
    { name: "Planner", color: "#6366F1", icon: "planner" },
    { name: "Search", color: "#00D2FF", icon: "search" },
    { name: "Reader", color: "#0284C7", icon: "reader" },
    { name: "Retrieval", color: "#14B8A6", icon: "brain" },
    { name: "Writer", color: "#10B981", icon: "writer" },
    { name: "Verifier", color: "#F43F5E", icon: "shield" },
  ];

  const TECH_STACK = [
    { label: "React 18", color: "#00D2FF" },
    { label: "FastAPI Core", color: "#14B8A6" },
    { label: "ChromaDB Vectors", color: "#6366F1" },
    { label: "LangGraph Pipeline", color: "#0284C7" },
    { label: "SSE Streaming", color: "#10B981" },
    { label: "Deterministic Audit", color: "#F43F5E" },
  ];

  return (
    <footer className="footer">
      {/* Top Multi-Color Spectrum Border */}
      <div className="footer-spectrum-border" aria-hidden="true" />
      <div className="footer-ambient-glow" aria-hidden="true" />

      <div className="footer-inner">
        {/* Main Brand & Status Column */}
        <div className="footer-top-grid">
          <div className="footer-brand-col">
            <div className="footer-logo-row">
              <div className="footer-logo-badge">
                <Icon name="bolt" size={18} strokeWidth={2.5} />
              </div>
              <div className="footer-brand-text">
                <span className="brand-word">SYNAPSE</span>
                <span className="brand-highlight">AI</span>
              </div>
            </div>
            <p className="footer-description">
              Autonomous multi-agent research intelligence engine. Decomposing complex queries,
              indexing live web evidence, and synthesizing fully grounded executive reports.
            </p>
            <div className="footer-live-status">
              <span className="live-status-pulse" />
              <span className="live-status-label">6 Autonomous Agents Operational</span>
            </div>
          </div>

          {/* Coordinated Multi-Agent Squad */}
          <div className="footer-agents-col">
            <h4 className="footer-col-title">
              <Icon name="brain" size={14} />
              Agent Coordination Squad
            </h4>
            <div className="footer-agents-grid">
              {AGENT_BADGES.map((agent) => (
                <div
                  key={agent.name}
                  className="footer-agent-pill"
                  style={{ '--agent-col': agent.color }}
                >
                  <span className="f-agent-dot" style={{ background: agent.color }} />
                  <Icon name={agent.icon} size={13} style={{ color: agent.color }} />
                  <span>{agent.name}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Architecture & Tech Stack */}
          <div className="footer-tech-col">
            <h4 className="footer-col-title">
              <Icon name="beaker" size={14} />
              Core Architecture
            </h4>
            <div className="footer-tech-chips">
              {TECH_STACK.map((tech) => (
                <span
                  key={tech.label}
                  className="footer-tech-chip"
                  style={{ '--tech-col': tech.color }}
                >
                  <span className="f-tech-dot" style={{ background: tech.color }} />
                  {tech.label}
                </span>
              ))}
            </div>
          </div>
        </div>

        {/* Bottom Attribution & Integrity Row */}
        <div className="footer-bottom-row">
          <div className="footer-copy">
            © {currentYear} SYNAPSE AI · Enterprise Autonomous Intelligence Platform
          </div>

          <div className="footer-badges-row">
            <span className="integrity-badge badge-audit">
              <Icon name="shield" size={12} />
              100% Deterministic Fact Audit
            </span>
            <span className="integrity-badge badge-citations">
              <Icon name="check" size={12} strokeWidth={2.5} />
              Zero-Hallucination Guardrails
            </span>
            <span className="integrity-badge badge-vector">
              <Icon name="brain" size={12} />
              ChromaDB Vector Store
            </span>
          </div>
        </div>
      </div>
    </footer>
  );
}
