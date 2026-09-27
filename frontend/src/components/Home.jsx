import React from 'react';

const FEATURED_TOPICS = [
  {
    title: "Autonomous AI Agents & Multi-Agent Intelligence",
    category: "Artificial Intelligence",
    icon: "🤖",
    desc: "Agentic workflows, recursive reasoning systems, memory architectures, and production benchmarks.",
  },
  {
    title: "CRISPR-Cas9 Gene Editing & Clinical Breakthroughs",
    category: "Biotechnology",
    icon: "🧬",
    desc: "Clinical trials, off-target minimization, in-vivo delivery platforms, and regulatory approvals.",
  },
  {
    title: "Commercial Nuclear Fusion Net Energy Milestones",
    category: "Deep Tech",
    icon: "⚛️",
    desc: "Tokamak magnetic confinement, laser inertial ignition, high-temperature superconductors, and funding.",
  },
  {
    title: "Fault-Tolerant Quantum Computing Architectures",
    category: "Quantum Hardware",
    icon: "💻",
    desc: "Logical qubit error correction, topological qubits, and commercial quantum advantage roadmaps.",
  },
];

const AGENT_SQUAD = [
  {
    id: "search",
    name: "Search Agent",
    role: "Web Discovery",
    emoji: "🔍",
    gradient: "linear-gradient(135deg, #7c6cf0, #a855f7)",
    tools: ["Query Intelligence", "Live Web Search", "Source Indexing"],
    description:
      "Formulates targeted search queries from natural language requests, scanning live global web indexes to discover verified sources.",
  },
  {
    id: "reader",
    name: "Reader Agent",
    role: "Content Extraction",
    emoji: "📄",
    gradient: "linear-gradient(135deg, #00b894, #00cec9)",
    tools: ["DOM Parser", "HTML Cleaning", "Content Filtering"],
    description:
      "Selects top web URLs, scrapes full page text structures, eliminates scripts and nav clutter, and extracts rich evidence payload.",
  },
  {
    id: "writer",
    name: "Writer Agent",
    role: "Executive Synthesis",
    emoji: "✍️",
    gradient: "linear-gradient(135deg, #f5a623, #ff7675)",
    tools: ["Neural Synthesis", "Structured Markdown", "Citation Engine"],
    description:
      "Synthesizes raw evidence into rigorous, professional executive reports complete with key findings, introduction, and citations.",
  },
  {
    id: "critic",
    name: "Critic Agent",
    role: "Quality Audit",
    emoji: "⭐",
    gradient: "linear-gradient(135deg, #e84393, #6c5ce7)",
    tools: ["QA Rubric Evaluation", "Fact Verification", "Score Assessment"],
    description:
      "Audits the draft report for accuracy, structure, completeness, and clarity — assigning a score (1-10) and improvement points.",
  },
];

export default function Home({ onLaunchResearch, isAuthenticated }) {
  const scrollToArchitecture = () => {
    document.getElementById('arch-section')?.scrollIntoView({ behavior: 'smooth' });
  };

  return (
    <div className="home-container">
      {/* HERO SECTION */}
      <section className="home-hero">
        <div className="home-badge">
          <span className="home-badge-dot" />
          SYNAPSE · Autonomous AI Research System
        </div>

        <h1 className="home-title">
          Deep Web AI Research,<br />
          <span className="gradient-text">Engineered for Perfection.</span>
        </h1>

        <p className="home-subtitle">
          SYNAPSE orchestrates an autonomous multi-agent pipeline that searches the live web,
          scrapes deep webpage contents, synthesizes executive reports, and performs
          automated quality reviews — complete with downloadable Word & PDF reports.
        </p>

        <div className="home-hero-actions">
          <button
            className="home-btn primary"
            onClick={() => onLaunchResearch()}
          >
            🚀 {isAuthenticated ? 'Launch Research Workspace' : 'Sign In & Start Research'}
          </button>

          <button
            className="home-btn secondary"
            onClick={scrollToArchitecture}
          >
            📐 System Architecture
          </button>
        </div>

        {/* METRICS STATS BANNER */}
        <div className="home-stats-banner">
          <div className="stat-box">
            <div className="stat-val">4</div>
            <div className="stat-label">Autonomous Agents</div>
          </div>
          <div className="stat-divider" />
          <div className="stat-box">
            <div className="stat-val">Real-Time</div>
            <div className="stat-label">Live Web Extraction</div>
          </div>
          <div className="stat-divider" />
          <div className="stat-box">
            <div className="stat-val">100%</div>
            <div className="stat-label">Verified Citations</div>
          </div>
          <div className="stat-divider" />
          <div className="stat-box">
            <div className="stat-val">3</div>
            <div className="stat-label">Formats (Word, PDF, MD)</div>
          </div>
        </div>
      </section>

      {/* AGENT SQUAD SPOTLIGHT */}
      <section className="home-section">
        <div className="section-header-center">
          <span className="subhead">Multi-Agent Architecture</span>
          <h2>Autonomous AI Squad</h2>
          <p>Four specialized AI agents operating in sequence to deliver authoritative intelligence.</p>
        </div>

        <div className="agent-squad-grid">
          {AGENT_SQUAD.map((agent) => (
            <div className="squad-card" key={agent.id}>
              <div
                className="squad-icon"
                style={{ background: agent.gradient }}
              >
                {agent.emoji}
              </div>
              <div className="squad-role">{agent.role}</div>
              <h3>{agent.name}</h3>
              <p>{agent.description}</p>
              <div className="squad-tools">
                {agent.tools.map((t) => (
                  <span className="tool-chip" key={t}>
                    {t}
                  </span>
                ))}
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* SYSTEM ARCHITECTURE FLOW */}
      <section className="home-section" id="arch-section">
        <div className="section-header-center">
          <span className="subhead">Pipeline Blueprint</span>
          <h2>Autonomous Workflow Sequence</h2>
          <p>Transforming raw intent into publication-grade research in seconds.</p>
        </div>

        <div className="arch-flow">
          <div className="arch-step">
            <div className="arch-node">1</div>
            <h4>Research Topic Input</h4>
            <p>Formulates user intent & scope</p>
          </div>
          <div className="arch-arrow">➔</div>

          <div className="arch-step">
            <div className="arch-node purp">2</div>
            <h4>Search Agent</h4>
            <p>Extracts queries & scans live web results</p>
          </div>
          <div className="arch-arrow">➔</div>

          <div className="arch-step">
            <div className="arch-node cyan">3</div>
            <h4>Reader Agent</h4>
            <p>Scrapes DOM & extracts clean page payload</p>
          </div>
          <div className="arch-arrow">➔</div>

          <div className="arch-step">
            <div className="arch-node yellow">4</div>
            <h4>Writer Agent</h4>
            <p>Drafts executive report with findings</p>
          </div>
          <div className="arch-arrow">➔</div>

          <div className="arch-step">
            <div className="arch-node pink">5</div>
            <h4>Critic Audit & Export</h4>
            <p>Evaluates quality score & outputs Word/PDF</p>
          </div>
        </div>
      </section>

      {/* QUICK LAUNCH TOPICS */}
      <section className="home-section">
        <div className="section-header-center">
          <span className="subhead">Instant Research</span>
          <h2>Explore Featured Intelligence Topics</h2>
          <p>Select any deep topic to launch a live autonomous research pipeline.</p>
        </div>

        <div className="topic-grid">
          {FEATURED_TOPICS.map((topic) => (
            <div
              className="topic-card"
              key={topic.title}
              onClick={() => onLaunchResearch(topic.title)}
            >
              <div className="topic-header">
                <span className="topic-icon">{topic.icon}</span>
                <span className="topic-badge">{topic.category}</span>
              </div>
              <h4>{topic.title}</h4>
              <p>{topic.desc}</p>
              <div className="topic-cta">
                Launch Pipeline <span>→</span>
              </div>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
