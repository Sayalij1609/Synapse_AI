import React, { useState, useEffect } from 'react';
import Icon from './shared/Icon';

const AGENT_SQUAD = [
  {
    id: "planner", name: "Planner Agent", role: "Research Decomposition",
    icon: "planner", gradient: "linear-gradient(135deg, #6C5CE7, #a29bfe)",
    delay: 0,
    tools: ["Query Analysis", "Subtask Generation", "Strategy Planning"],
    description: "Breaks complex queries into 5–8 focused subtasks with targeted search queries.",
  },
  {
    id: "search", name: "Search Agent", role: "Web Discovery",
    icon: "search", gradient: "linear-gradient(135deg, #0984e3, #74b9ff)",
    delay: 1,
    tools: ["Query Intelligence", "Live Web Search", "Source Indexing"],
    description: "Scans live global web indexes to discover verified sources in real-time.",
  },
  {
    id: "reader", name: "Reader Agent", role: "Content Extraction",
    icon: "reader", gradient: "linear-gradient(135deg, #00b894, #55efc4)",
    delay: 2,
    tools: ["DOM Parser", "HTML Cleaning", "Content Filtering"],
    description: "Scrapes full page text, eliminates clutter, and extracts rich evidence payloads.",
  },
  {
    id: "retrieval", name: "Retrieval Agent", role: "Vector Indexing",
    icon: "brain", gradient: "linear-gradient(135deg, #e17055, #fab1a0)",
    delay: 3,
    tools: ["ChromaDB Indexing", "Semantic Search", "Evidence Ranking"],
    description: "Embeds content into a vector store and retrieves semantically relevant evidence.",
  },
  {
    id: "writer", name: "Writer Agent", role: "Executive Synthesis",
    icon: "writer", gradient: "linear-gradient(135deg, #2B2554, #6c5ce7)",
    delay: 4,
    tools: ["Neural Synthesis", "Structured Markdown", "Citation Engine"],
    description: "Synthesizes raw evidence into rigorous executive reports with inline citations.",
  },
  {
    id: "verifier", name: "Verifier Agent", role: "Autonomous Audit",
    icon: "shield", gradient: "linear-gradient(135deg, #d63031, #ff7675)",
    delay: 5,
    tools: ["Claim Verification", "Fact Checking", "Score Assessment"],
    description: "Audits every claim for evidence grounding and triggers additional research cycles.",
  },
];

const PIPELINE_STEPS = [
  { step: 1, title: 'Query Input', icon: 'bolt', desc: 'Natural language intent', color: '#10B981' },
  { step: 2, title: 'Decompose', icon: 'planner', desc: 'Split into subtasks', color: '#6C5CE7' },
  { step: 3, title: 'Search', icon: 'search', desc: 'Live web discovery', color: '#0984e3' },
  { step: 4, title: 'Extract', icon: 'reader', desc: 'Clean content', color: '#00b894' },
  { step: 5, title: 'Index', icon: 'brain', desc: 'Vector embedding', color: '#e17055' },
  { step: 6, title: 'Synthesize', icon: 'writer', desc: 'Build report', color: '#6C5CE7' },
  { step: 7, title: 'Verify', icon: 'shield', desc: 'Audit & export', color: '#d63031' },
];

const FEATURED_TOPICS = [
  { title: "Autonomous AI Agents & Multi-Agent Intelligence", category: "Artificial Intelligence", icon: "brain", desc: "Agentic workflows, recursive reasoning systems, and production benchmarks." },
  { title: "CRISPR-Cas9 Gene Editing Breakthroughs", category: "Biotechnology", icon: "sparkles", desc: "Clinical trials, off-target minimization, and regulatory approvals." },
  { title: "Commercial Nuclear Fusion Energy Milestones", category: "Deep Tech", icon: "bolt", desc: "Tokamak confinement, laser ignition, and high-temperature superconductors." },
  { title: "Fault-Tolerant Quantum Computing", category: "Quantum Hardware", icon: "chartBar", desc: "Logical qubit error correction and commercial quantum advantage roadmaps." },
];

function AnimatedPipeline() {
  const [activeStep, setActiveStep] = useState(0);

  useEffect(() => {
    const timer = setInterval(() => {
      setActiveStep(prev => (prev + 1) % PIPELINE_STEPS.length);
    }, 2000);
    return () => clearInterval(timer);
  }, []);

  return (
    <div className="pipeline-animation">
      <div className="pipeline-track-anim">
        {PIPELINE_STEPS.map((node, idx) => {
          const isActive = idx === activeStep;
          const isPassed = idx < activeStep;
          return (
            <React.Fragment key={node.step}>
              <div className={`pipeline-node ${isActive ? 'active' : ''} ${isPassed ? 'passed' : ''}`}>
                <div
                  className="pipeline-node-circle"
                  style={{
                    '--node-color': node.color,
                    background: isActive || isPassed ? node.color : 'var(--bg-elevated)',
                    boxShadow: isActive ? `0 0 24px ${node.color}50, 0 0 48px ${node.color}20` : 'none',
                  }}
                >
                  <Icon name={node.icon} size={16} strokeWidth={2} style={{ color: isActive || isPassed ? '#fff' : 'var(--text-faint)' }} />
                  {isActive && <div className="node-pulse" style={{ borderColor: node.color }} />}
                </div>
                <div className="pipeline-node-label" style={{ color: isActive ? 'var(--text-primary)' : 'var(--text-muted)' }}>
                  {node.title}
                </div>
                <div className="pipeline-node-desc">{node.desc}</div>
              </div>
              {idx < PIPELINE_STEPS.length - 1 && (
                <div className={`pipeline-connector-anim ${isPassed ? 'active' : ''}`}>
                  <div className="connector-line" style={{ background: isPassed ? node.color : 'var(--border)' }} />
                  {isPassed && <div className="data-particle" style={{ background: PIPELINE_STEPS[idx + 1].color }} />}
                </div>
              )}
            </React.Fragment>
          );
        })}
      </div>
    </div>
  );
}

export default function Home({ onLaunchResearch, isAuthenticated }) {
  const [hoveredAgent, setHoveredAgent] = useState(null);

  const scrollToArchitecture = () => {
    document.getElementById('arch-section')?.scrollIntoView({ behavior: 'smooth' });
  };

  return (
    <div className="landing">
      {/* ── HERO ── */}
      <section className="landing-hero">
        {/* Animated background orbs */}
        <div className="hero-orbs" aria-hidden="true">
          <div className="orb orb-1" />
          <div className="orb orb-2" />
          <div className="orb orb-3" />
        </div>

        <div className="hero-content">
          <div className="hero-badge">
            <span className="hero-badge-dot" />
            <span>SYNAPSE</span>
            <span className="hero-badge-sep">·</span>
            <span>Autonomous AI Research System</span>
          </div>

          <h1 className="hero-title">
            Deep Research Intelligence,<br />
            <span className="gradient-text-hero">Engineered for Perfection.</span>
          </h1>

          <p className="hero-subtitle">
            6 autonomous AI agents orchestrate a full research pipeline — decomposing queries,
            searching the live web, extracting content, indexing evidence, synthesizing
            citation-grounded reports, and performing automated verification.
          </p>

          <div className="hero-actions">
            <button className="hero-primary-btn" onClick={() => onLaunchResearch()}>
              <Icon name="bolt" size={18} strokeWidth={2.5} />
              {isAuthenticated ? 'Launch Research Lab' : 'Start Research'}
            </button>
            <button className="hero-secondary-btn" onClick={scrollToArchitecture}>
              <Icon name="play" size={16} />
              Watch Pipeline
            </button>
          </div>

          <div className="stats-banner">
            {[
              { value: '6', label: 'AI Agents' },
              { value: 'Real-Time', label: 'SSE Streaming' },
              { value: '100%', label: 'Citation Coverage' },
              { value: '3', label: 'Export Formats' },
            ].map((s) => (
              <div className="stat-item" key={s.label}>
                <div className="stat-value">{s.value}</div>
                <div className="stat-label">{s.label}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── ANIMATED PIPELINE SECTION ── */}
      <section className="landing-section" id="arch-section">
        <div className="landing-section-header">
          <span className="overline">Live Pipeline Preview</span>
          <h2>Autonomous Workflow in Motion</h2>
          <p>Watch how SYNAPSE AI transforms a raw query into a verified executive report.</p>
        </div>
        <AnimatedPipeline />
      </section>

      {/* ── AGENT SHOWCASE ── */}
      <section className="landing-section">
        <div className="landing-section-header">
          <span className="overline">Multi-Agent Architecture</span>
          <h2>6 Specialized AI Agents</h2>
          <p>Each agent operates autonomously within a coordinated intelligence pipeline.</p>
        </div>

        <div className="agent-grid">
          {AGENT_SQUAD.map((agent) => (
            <div
              className={`agent-card ${hoveredAgent === agent.id ? 'hovered' : ''}`}
              key={agent.id}
              style={{ '--agent-gradient': agent.gradient, '--anim-delay': `${agent.delay * 0.1}s` }}
              onMouseEnter={() => setHoveredAgent(agent.id)}
              onMouseLeave={() => setHoveredAgent(null)}
            >
              <div className="agent-card-icon" style={{ background: agent.gradient }}>
                <Icon name={agent.icon} size={20} strokeWidth={2} />
              </div>
              <div className="agent-card-role">{agent.role}</div>
              <h3>{agent.name}</h3>
              <p>{agent.description}</p>
              <div className="agent-tools">
                {agent.tools.map((t) => (
                  <span className="chip" key={t}>{t}</span>
                ))}
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* ── FEATURED TOPICS ── */}
      <section className="landing-section">
        <div className="landing-section-header">
          <span className="overline">Instant Research</span>
          <h2>Explore Intelligence Topics</h2>
          <p>Select any topic to launch a live autonomous research pipeline.</p>
        </div>

        <div className="topic-grid">
          {FEATURED_TOPICS.map((topic) => (
            <div className="topic-card" key={topic.title} onClick={() => onLaunchResearch(topic.title)}>
              <div className="topic-card-header">
                <div className="topic-icon">
                  <Icon name={topic.icon} size={18} />
                </div>
                <span className="topic-badge">{topic.category}</span>
              </div>
              <h4>{topic.title}</h4>
              <p>{topic.desc}</p>
              <div className="topic-cta">
                Launch Pipeline <Icon name="arrowRight" size={14} />
              </div>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
