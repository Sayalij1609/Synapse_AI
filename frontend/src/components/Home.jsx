import React, { useState, useEffect } from 'react';
import Icon from './shared/Icon';

const AGENT_SQUAD = [
  {
    id: "planner", name: "Planner Agent", role: "Research Decomposition",
    icon: "planner", gradient: "linear-gradient(135deg, #8B5CF6, #6D28D9)",
    delay: 0,
    tools: ["Query Analysis", "Subtask Generation", "Strategy Planning"],
    description: "Breaks complex queries into 5–8 focused subtasks with targeted search queries.",
  },
  {
    id: "search", name: "Search Agent", role: "Web Discovery",
    icon: "search", gradient: "linear-gradient(135deg, #0284C7, #38BDF8)",
    delay: 1,
    tools: ["Query Intelligence", "Live Web Search", "Source Indexing"],
    description: "Scans live global web indexes to discover verified sources in real-time.",
  },
  {
    id: "reader", name: "Reader Agent", role: "Content Extraction",
    icon: "reader", gradient: "linear-gradient(135deg, #06B6D4, #0D9488)",
    delay: 2,
    tools: ["DOM Parser", "HTML Cleaning", "Content Filtering"],
    description: "Scrapes full page text, eliminates clutter, and extracts rich evidence payloads.",
  },
  {
    id: "retrieval", name: "Retrieval Agent", role: "Vector Indexing",
    icon: "brain", gradient: "linear-gradient(135deg, #0D9488, #14B8A6)",
    delay: 3,
    tools: ["ChromaDB Indexing", "Semantic Search", "Evidence Ranking"],
    description: "Embeds content into a vector store and retrieves semantically relevant evidence.",
  },
  {
    id: "writer", name: "Writer Agent", role: "Executive Synthesis",
    icon: "writer", gradient: "linear-gradient(135deg, #059669, #10B981)",
    delay: 4,
    tools: ["Neural Synthesis", "Structured Markdown", "Citation Engine"],
    description: "Synthesizes raw evidence into rigorous executive reports with inline citations.",
  },
  {
    id: "verifier", name: "Verifier Agent", role: "Autonomous Audit",
    icon: "shield", gradient: "linear-gradient(135deg, #E11D48, #F43F5E)",
    delay: 5,
    tools: ["Claim Verification", "Fact Checking", "Score Assessment"],
    description: "Audits every claim for evidence grounding and triggers additional research cycles.",
  },
];

const PIPELINE_STEPS = [
  { step: 1, title: 'Query Input', icon: 'bolt', desc: 'Natural language intent', color: '#6366F1' },
  { step: 2, title: 'Decompose', icon: 'planner', desc: 'Split into subtasks', color: '#8B5CF6' },
  { step: 3, title: 'Search', icon: 'search', desc: 'Live web discovery', color: '#38BDF8' },
  { step: 4, title: 'Extract', icon: 'reader', desc: 'Clean content', color: '#06B6D4' },
  { step: 5, title: 'Index', icon: 'brain', desc: 'Vector embedding', color: '#14B8A6' },
  { step: 6, title: 'Synthesize', icon: 'writer', desc: 'Build report', color: '#10B981' },
  { step: 7, title: 'Verify', icon: 'shield', desc: 'Audit & export', color: '#F43F5E' },
];

const DOMAIN_CATEGORIES = [
  { id: 'all', label: 'All Domains', icon: 'bolt' },
  { id: 'ai', label: 'Autonomous AI', icon: 'brain' },
  { id: 'biotech', label: 'Genomics & CRISPR', icon: 'sparkles' },
  { id: 'energy', label: 'Clean Tech & Fusion', icon: 'bolt' },
  { id: 'quantum', label: 'Quantum & Deep Tech', icon: 'beaker' },
  { id: 'neuro', label: 'Neurotech & BCI', icon: 'reader' },
];

const RESEARCH_TOPICS = [
  {
    id: 1,
    title: "Autonomous AI Agents & Recursive Reasoning Workflows",
    category: "ai",
    categoryLabel: "Autonomous AI",
    color: "#6366F1",
    icon: "brain",
    desc: "Multi-agent coordination, test-time compute scaling, and autonomous self-correction mechanisms in enterprise production.",
    subtasks: ["Agentic workflow benchmarks", "Test-time compute scaling", "Recursive verification patterns"],
    grounding: "arXiv & NeurIPS 2025-2026",
  },
  {
    id: 2,
    title: "SWE-bench Verified: SOTA Agentic Software Engineering",
    category: "ai",
    categoryLabel: "Autonomous AI",
    color: "#00D2FF",
    icon: "planner",
    desc: "Comparing Claude 3.7 Sonnet, DeepSeek R1, and GPT-4.5 on real-world GitHub issue resolution and self-debugging.",
    subtasks: ["Pass@1 issue resolution", "Context window degradation", "Autonomous test verification"],
    grounding: "SWE-bench Leaderboard & Papers",
  },
  {
    id: 3,
    title: "In-Vivo CRISPR-Cas9 Clinical Efficacy & Safety Milestones",
    category: "biotech",
    categoryLabel: "Genomics & CRISPR",
    color: "#06B6D4",
    icon: "sparkles",
    desc: "Phase II/III trials, lipid nanoparticle delivery vectors, and off-target cleaving reduction techniques.",
    subtasks: ["LNP vector biodistribution", "Off-target minimization", "FDA regulatory approval timelines"],
    grounding: "Nature Biotech & ClinicalTrials.gov",
  },
  {
    id: 4,
    title: "Base & Prime Editing Therapeutics for Genetic Cardiomyopathy",
    category: "biotech",
    categoryLabel: "Genomics & CRISPR",
    color: "#14B8A6",
    icon: "shield",
    desc: "Targeted single-nucleotide transversion without double-strand breaks for congenital cardiovascular disorders.",
    subtasks: ["Target gene correction rates", "Immunogenicity assays", "Preclinical primate models"],
    grounding: "Cell & NEJM 2025-2026",
  },
  {
    id: 5,
    title: "Commercial Tokamak Nuclear Fusion & Net Energy Milestones",
    category: "energy",
    categoryLabel: "Clean Tech & Fusion",
    color: "#10B981",
    icon: "bolt",
    desc: "High-temperature superconducting (HTS) magnets, Q > 1 plasma stability, and commercial pilot plant roadmaps.",
    subtasks: ["HTS magnet magnetic confinement", "Triple product metrics", "Tritium breeding viability"],
    grounding: "ITER, CFS, & Nuclear Fusion Journal",
  },
  {
    id: 6,
    title: "Solid-State Sodium-Ion vs Silicon-Anode Battery Paradigms",
    category: "energy",
    categoryLabel: "Clean Tech & Fusion",
    color: "#14B8A6",
    icon: "beaker",
    desc: "Energy density comparisons, dendrite resistance in sulfide electrolytes, and grid-scale manufacturing economics.",
    subtasks: ["Volumetric energy density (Wh/L)", "Cathode interface degradation", "Gigawatt-hour cost curves"],
    grounding: "Journal of Power Sources & DOE Reports",
  },
  {
    id: 7,
    title: "Fault-Tolerant Quantum Computing & Surface Code Scaling",
    category: "quantum",
    categoryLabel: "Quantum & Deep Tech",
    color: "#0284C7",
    icon: "chartBar",
    desc: "Physical-to-logical qubit overhead, neutral atom arrays, and real-time syndrome extraction error correction.",
    subtasks: ["Threshold error rates (<0.1%)", "Logical qubit coherence times", "Commercial quantum advantage"],
    grounding: "Nature Physics & IBM/Google Roadmaps",
  },
  {
    id: 8,
    title: "Topological Superconductivity in Majorana Zero Modes",
    category: "quantum",
    categoryLabel: "Quantum & Deep Tech",
    color: "#6366F1",
    icon: "sparkles",
    desc: "Braiding non-Abelian anyons in nanowire heterostructures for hardware-protected quantum information.",
    subtasks: ["Zero-bias conductance peak", "Nanowire interface purity", "Braiding protocol verification"],
    grounding: "Physical Review Letters & QuTech",
  },
  {
    id: 9,
    title: "High-Density Wireless Brain-Computer Interfaces (BCI)",
    category: "neuro",
    categoryLabel: "Neurotech & BCI",
    color: "#F43F5E",
    icon: "reader",
    desc: "Micro-electrode array biocompatibility, real-time spike sorting algorithms, and closed-loop motor restoration.",
    subtasks: ["Chronic glial scar suppression", "Sub-millisecond latency decoders", "Human clinical trial milestones"],
    grounding: "Nature Neuroscience & FDA IDE Trials",
  },
];

const RANDOM_PROMPTS = [
  "Analyze state-of-the-art agentic reasoning benchmarks and self-correction architectures in 2026",
  "In-vivo CRISPR gene editing breakthroughs: clinical trial milestones and off-target reduction techniques",
  "Commercial nuclear fusion energy: tokamak magnetic confinement vs laser ignition net gain",
  "Fault-tolerant quantum computing: logical qubit scaling and surface code error correction roadmaps",
  "High-density flexible neural probes vs wireless telemetry in brain-computer interfaces",
  "Solid-state battery commercialization: sulfide electrolytes, dendrite suppression, and cost curves",
  "Autonomous software engineering agents: SWE-bench verified performance comparison and failure modes",
  "mRNA vaccine platforms beyond COVID: neoantigen personalized cancer vaccines clinical data",
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
                    boxShadow: isActive ? `0 0 24px ${node.color}60, 0 0 48px ${node.color}30` : 'none',
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
  const [activeCategory, setActiveCategory] = useState('all');
  const [customQuery, setCustomQuery] = useState('');
  const [diceRolling, setDiceRolling] = useState(false);

  const scrollToArchitecture = () => {
    document.getElementById('arch-section')?.scrollIntoView({ behavior: 'smooth' });
  };

  const handleShufflePrompt = () => {
    setDiceRolling(true);
    setTimeout(() => setDiceRolling(false), 500);
    const available = RANDOM_PROMPTS.filter(p => p !== customQuery);
    const chosen = available[Math.floor(Math.random() * available.length)];
    setCustomQuery(chosen);
  };

  const handleLaunchCustom = (e) => {
    if (e) e.preventDefault();
    const query = customQuery.trim() || RANDOM_PROMPTS[0];
    onLaunchResearch(query);
  };

  const filteredTopics = activeCategory === 'all'
    ? RESEARCH_TOPICS
    : RESEARCH_TOPICS.filter(t => t.category === activeCategory);

  return (
    <div className="landing">
      {/* ── HERO ── */}
      <section className="landing-hero">
        {/* Animated background orbs with layered depth */}
        <div className="hero-orbs" aria-hidden="true">
          <div className="orb orb-1" />
          <div className="orb orb-2" />
          <div className="orb orb-3" />
          <div className="orb orb-4" />
          <div className="orb orb-5" />
        </div>
        <div className="hero-grid-mesh" aria-hidden="true" />

        <div className="hero-content">
          <div className="hero-badge">
            <span className="hero-badge-dot" />
            <span className="hero-badge-text">SYNAPSE AI</span>
            <span className="hero-badge-sep">·</span>
            <span>Autonomous Intelligence Engine</span>
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

      {/* ── DYNAMIC RESEARCH STUDIO & TOPIC RADAR ── */}
      <section className="landing-section" id="radar-section">
        <div className="landing-section-header">
          <span className="overline">Intelligence Command</span>
          <h2>Interactive Research Studio & Topic Radar</h2>
          <p>Deploy the 6-agent swarm onto cutting-edge hypotheses, or architect a custom multi-agent investigation.</p>
        </div>

        {/* Interactive Query Architect Bar */}
        <div className="query-architect-wrapper">
          <form className="query-architect-bar" onSubmit={handleLaunchCustom}>
            <div className="qa-icon">
              <Icon name="search" size={18} />
            </div>
            <input
              type="text"
              className="qa-input"
              value={customQuery}
              onChange={(e) => setCustomQuery(e.target.value)}
              placeholder="Enter any complex research objective or click 🎲 for prompt inspiration..."
            />
            {customQuery && (
              <button
                type="button"
                className="qa-clear-btn"
                onClick={() => setCustomQuery('')}
                title="Clear query"
              >
                <Icon name="x" size={14} />
              </button>
            )}
            <button
              type="button"
              className={`qa-shuffle-btn ${diceRolling ? 'rolling' : ''}`}
              onClick={handleShufflePrompt}
              title="Generate random high-impact research prompt"
            >
              <Icon name="sparkles" size={16} />
              <span>Inspiration</span>
            </button>
            <button type="submit" className="qa-launch-btn">
              <Icon name="bolt" size={16} strokeWidth={2.5} />
              <span>Deploy Swarm</span>
            </button>
          </form>
        </div>

        {/* Domain Category Filter Tabs */}
        <div className="domain-filter-tabs">
          {DOMAIN_CATEGORIES.map((cat) => {
            const isActive = activeCategory === cat.id;
            return (
              <button
                key={cat.id}
                className={`domain-tab ${isActive ? 'active' : ''}`}
                onClick={() => setActiveCategory(cat.id)}
              >
                <Icon name={cat.icon} size={15} />
                <span>{cat.label}</span>
                {cat.id !== 'all' && (
                  <span className="domain-count">
                    {RESEARCH_TOPICS.filter(t => t.category === cat.id).length}
                  </span>
                )}
              </button>
            );
          })}
        </div>

        {/* Dynamic Topic Radar Grid */}
        <div className="topic-grid">
          {filteredTopics.map((topic) => (
            <div
              className="topic-card dynamic-topic-card"
              key={topic.id}
              onClick={() => onLaunchResearch(topic.title)}
              style={{ '--topic-color': topic.color }}
            >
              <div className="topic-card-header">
                <div className="topic-icon" style={{ color: topic.color }}>
                  <Icon name={topic.icon} size={18} />
                </div>
                <div className="topic-badge-wrapper">
                  <span className="topic-category-pill">
                    <span className="category-dot" style={{ background: topic.color }} />
                    {topic.categoryLabel}
                  </span>
                </div>
              </div>

              <h4>{topic.title}</h4>
              <p>{topic.desc}</p>

              {/* Decomposition Blueprint Subtasks */}
              <div className="topic-subtasks-preview">
                <div className="subtasks-label">Planned Agent Decompositions:</div>
                <div className="subtasks-list">
                  {topic.subtasks.map((st, idx) => (
                    <div className="subtask-item" key={idx}>
                      <span className="subtask-num">0{idx + 1}</span>
                      <span>{st}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Grounding Target & Launch CTA */}
              <div className="topic-card-footer">
                <span className="grounding-badge">
                  <Icon name="shield" size={12} />
                  {topic.grounding}
                </span>
                <div className="topic-cta">
                  Launch Pipeline <Icon name="arrowRight" size={14} />
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Live Intelligence Provenance Ticker */}
        <div className="intelligence-ticker-wrapper">
          <div className="intelligence-ticker">
            <span className="ticker-item"><Icon name="bolt" size={13} /> 6 Autonomous AI Agents</span>
            <span className="ticker-sep">/</span>
            <span className="ticker-item"><Icon name="search" size={13} /> Real-Time Multi-Engine Web Discovery</span>
            <span className="ticker-sep">/</span>
            <span className="ticker-item"><Icon name="reader" size={13} /> Noise-Free DOM Content Extraction</span>
            <span className="ticker-sep">/</span>
            <span className="ticker-item"><Icon name="brain" size={13} /> ChromaDB Vector Reranking & Evidence Storage</span>
            <span className="ticker-sep">/</span>
            <span className="ticker-item"><Icon name="writer" size={13} /> Rigorous Synthesis with Inline Verifiable Citations</span>
            <span className="ticker-sep">/</span>
            <span className="ticker-item"><Icon name="shield" size={13} /> 100% Deterministic Fact Audit & Fallback Guardrails</span>
          </div>
        </div>
      </section>
    </div>
  );
}
