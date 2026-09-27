import { useState, useEffect, useCallback, useRef } from 'react';
import './App.css';

import Topbar from './components/Topbar';
import Home from './components/Home';
import Hero from './components/Hero';
import LiveAgentExecution from './components/LiveAgentExecution';
import ResearchPlannerView from './components/ResearchPlannerView';
import VerificationStatus from './components/VerificationStatus';
import Metrics from './components/Metrics';
import Results from './components/Results';
import Footer from './components/Footer';
import HistoryModal from './components/HistoryModal';
import AuthModal from './components/AuthModal';
import UserWorkspace from './components/UserWorkspace';

import useResearch from './hooks/useResearch';
import { fetchHistoryEntry, fetchCurrentUser, logout as apiLogout } from './api';

const AGENTS = ['planner', 'search', 'reader', 'writer', 'critic'];

export default function App() {
  /* ── View State: 'home' | 'dashboard' | 'workspace' ── */
  const [currentView, setCurrentView] = useState('home');

  /* ── Authentication State ── */
  const [currentUser, setCurrentUser] = useState(null);
  const [authModalOpen, setAuthModalOpen] = useState(false);
  const [pendingResearch, setPendingResearch] = useState(null);

  useEffect(() => {
    // Check existing session
    fetchCurrentUser().then((user) => {
      if (user) setCurrentUser(user);
    });
  }, []);

  const handleAuthSuccess = (user) => {
    setCurrentUser(user);
    setRefreshSignal((s) => s + 1);
    // Launch deferred research if auth was triggered by a research attempt
    if (pendingResearch) {
      const { topic, projectId } = pendingResearch;
      setPendingResearch(null);
      if (topic) {
        setCurrentView('dashboard');
        setCurrentTopic(topic);
        start(topic, projectId);
      } else {
        setCurrentView('dashboard');
      }
    }
  };

  const handleLogout = async () => {
    await apiLogout();
    setCurrentUser(null);
    setRefreshSignal((s) => s + 1);
    if (currentView === 'workspace') {
      setCurrentView('home');
    }
  };

  /* ── Lock to Light Theme ── */
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', 'light');
    localStorage.setItem('syn-t', 'light');
  }, []);

  /* ── History Modal ── */
  const [historyOpen, setHistoryOpen] = useState(false);
  const openHistory = () => setHistoryOpen(true);
  const closeHistory = () => setHistoryOpen(false);

  /* ── Research pipeline (enhanced) ── */
  const {
    start,
    reset,
    agentStatuses,
    results,
    metrics,
    isRunning,
    error,
    researchPlan,
    liveAgents,
    verificationState,
    evidenceClaims,
    sourceProfiles,
  } = useResearch();

  const [currentTopic, setCurrentTopic] = useState('');
  const [refreshSignal, setRefreshSignal] = useState(0);

  // Refresh history on completion
  const prevMetrics = useRef(null);
  useEffect(() => {
    if (metrics && metrics !== prevMetrics.current) {
      prevMetrics.current = metrics;
      setRefreshSignal((s) => s + 1);
    }
  }, [metrics]);

  const handleStartResearch = useCallback(
    (topic, projectId = null) => {
      // Gate: Require authentication before research
      if (!currentUser) {
        setPendingResearch({ topic, projectId });
        setAuthModalOpen(true);
        return;
      }
      setCurrentView('dashboard');
      setCurrentTopic(topic);
      start(topic, projectId);
    },
    [start, currentUser]
  );

  const handleSwitchView = useCallback(
    (viewName) => {
      setCurrentView(viewName);
      window.scrollTo({ top: 0, behavior: 'smooth' });
    },
    []
  );

  /* ── Load a history or workspace session entry ── */
  const [historyResults, setHistoryResults] = useState(null);
  const [historyStatuses, setHistoryStatuses] = useState(null);
  const [historyMetrics, setHistoryMetrics] = useState(null);
  const [historyEvidenceClaims, setHistoryEvidenceClaims] = useState(null);
  const [historySourceProfiles, setHistorySourceProfiles] = useState(null);
  const [historyPlan, setHistoryPlan] = useState(null);

  const handleSelectEntry = useCallback(
    async (id) => {
      try {
        const h = await fetchHistoryEntry(id);
        if (h.error) return;

        reset();
        setCurrentView('dashboard');
        setCurrentTopic(h.topic);

        // Set all agents to done
        setHistoryStatuses(
          Object.fromEntries(AGENTS.map((k) => [k, 'done']))
        );

        // Build results from history / DB session
        const r = {};
        if (h.plan_markdown) r.planner = h.plan_markdown;
        else if (h.plan) r.planner = typeof h.plan === 'object' ? JSON.stringify(h.plan, null, 2) : String(h.plan);
        if (h.search_results) r.search = h.search_results;
        if (h.scraped_content) r.reader = h.scraped_content;
        if (h.report) r.writer = h.report;
        if (h.feedback) r.critic = h.feedback;
        if (h.source_quality_profiles) r.sourceQualityProfiles = h.source_quality_profiles;
        if (h.source_quality_report) r.sourceQualitySummary = h.source_quality_report;
        if (h.failed_sources) r.failedSources = h.failed_sources;
        if (h.degraded_modes) r.degradedModes = h.degraded_modes;
        if (h.telemetry) r.telemetry = h.telemetry;
        if (h.agent_runs) r.agentRuns = h.agent_runs;
        if (h.evidence_summary) {
          r.evidence = typeof h.evidence_summary === 'object'
            ? JSON.stringify(h.evidence_summary, null, 2)
            : String(h.evidence_summary);
        }
        setHistoryResults(r);

        // Restore plan from history
        if (h.plan) {
          const plan = typeof h.plan === 'object' ? h.plan : {};
          setHistoryPlan({
            objective: plan.research_objective || plan.objective || h.topic,
            subtasks: plan.subtasks || h.subtasks || [],
            searchQueries: plan.search_queries || [],
            strategy: plan.strategy || '',
            planMarkdown: h.plan_markdown || '',
          });
        } else {
          setHistoryPlan(null);
        }

        // Restore evidence claims from history
        if (h.grounded_claims || h.unsupported_claims || h.insufficient_claims) {
          setHistoryEvidenceClaims({
            grounded: h.grounded_claims || [],
            unsupported: h.unsupported_claims || [],
            insufficient: h.insufficient_claims || [],
            citationTrace: h.citation_trace || {},
            totalClaims: (h.grounded_claims?.length || 0) + (h.unsupported_claims?.length || 0) + (h.insufficient_claims?.length || 0),
          });
        } else {
          setHistoryEvidenceClaims(null);
        }

        // Restore source profiles
        setHistorySourceProfiles(h.source_quality_profiles || null);

        // Compute metrics from history
        const words = h.report ? h.report.split(/\s+/).filter(Boolean).length : 0;
        const urls = h.report ? (h.report.match(/https?:\/\/[^\s)]+/g) || []) : [];
        let score = '—';
        if (h.feedback) {
          const m = h.feedback.match(/Score:\s*(\d+\/\d+)/i);
          if (m) score = m[1];
        }
        setHistoryMetrics({
          sources: urls.length || (h.sources ? h.sources.length : '—'),
          words: words.toLocaleString(),
          duration: '—',
          score,
        });

        setTimeout(
          () =>
            document
              .getElementById('results-section')
              ?.scrollIntoView({ behavior: 'smooth', block: 'start' }),
          150
        );
      } catch (err) {
        console.error('Load failed:', err);
      }
    },
    [reset]
  );

  // Clear history overrides when a live research starts
  useEffect(() => {
    if (isRunning) {
      setHistoryResults(null);
      setHistoryStatuses(null);
      setHistoryMetrics(null);
      setHistoryEvidenceClaims(null);
      setHistorySourceProfiles(null);
      setHistoryPlan(null);
    }
  }, [isRunning]);

  // Merge live + history state
  const displayStatuses = historyStatuses || agentStatuses;
  const displayResults = historyResults || results;
  const displayMetrics = historyMetrics || metrics;
  const displayPlan = historyPlan || researchPlan;
  const displayEvidenceClaims = historyEvidenceClaims || evidenceClaims;
  const displaySourceProfiles = historySourceProfiles || sourceProfiles;

  return (
    <>
      <AuthModal
        isOpen={authModalOpen}
        onClose={() => setAuthModalOpen(false)}
        onAuthSuccess={handleAuthSuccess}
      />

      <HistoryModal
        isOpen={historyOpen}
        onClose={closeHistory}
        onSelectEntry={handleSelectEntry}
        refreshSignal={refreshSignal}
      />

      <div className="main full-width-main">
        <Topbar
          currentView={currentView}
          onSwitchView={handleSwitchView}
          onOpenHistory={openHistory}
          currentUser={currentUser}
          onOpenAuth={() => setAuthModalOpen(true)}
          onLogout={handleLogout}
        />

        <div className="content">
          {currentView === 'home' && (
            <Home
              isAuthenticated={!!currentUser}
              onLaunchResearch={(topic) => {
                if (topic) {
                  handleStartResearch(topic);
                } else {
                  // Navigate to dashboard requires auth
                  if (!currentUser) {
                    setPendingResearch({ topic: null, projectId: null });
                    setAuthModalOpen(true);
                    return;
                  }
                  handleSwitchView('dashboard');
                }
              }}
            />
          )}

          {currentView === 'dashboard' && (
            <div className="dashboard-view">
              <Hero
                onStartResearch={(topic) => handleStartResearch(topic)}
                isRunning={isRunning}
              />

              {error && <div className="err">{error}</div>}

              {/* Verification Status Banner */}
              <VerificationStatus verificationState={verificationState} />

              {/* Research Planner View */}
              <ResearchPlannerView
                researchPlan={displayPlan}
                isRunning={isRunning}
              />

              {/* Live 6-Agent Pipeline */}
              <LiveAgentExecution
                liveAgents={liveAgents}
                agentStatuses={displayStatuses}
                verificationState={verificationState}
              />

              <Metrics metrics={displayMetrics} />

              <div id="results-section">
                <Results
                  results={displayResults}
                  topic={currentTopic}
                  evidenceClaims={displayEvidenceClaims}
                  sourceProfiles={displaySourceProfiles}
                />
              </div>
            </div>
          )}

          {currentView === 'workspace' && (
            <UserWorkspace
              currentUser={currentUser}
              onOpenAuth={() => setAuthModalOpen(true)}
              onLogout={handleLogout}
              onLaunchResearchInProject={(topic, projId) => handleStartResearch(topic, projId)}
              onLoadSessionInDashboard={handleSelectEntry}
            />
          )}
        </div>

        <Footer />
      </div>
    </>
  );
}
