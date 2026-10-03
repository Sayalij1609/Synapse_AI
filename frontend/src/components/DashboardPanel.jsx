import { useState } from 'react';
import Icon from './shared/Icon';
import Hero from './Hero';
import LiveAgentExecution from './LiveAgentExecution';
import ResearchPlannerView from './ResearchPlannerView';
import VerificationStatus from './VerificationStatus';
import Metrics from './Metrics';
import Results from './Results';

/**
 * DashboardPanel — Full-height sidebar + content layout.
 * The sidebar spans from topbar to bottom of the viewport.
 * Search bar sits above the content area (compact once research starts).
 */

const SIDEBAR_TABS = [
  { key: 'pipeline',  label: 'Pipeline',          icon: 'bolt',    group: 'exec' },
  { key: 'planner',   label: 'Research Plan',      icon: 'planner', group: 'exec' },
  { key: 'report',    label: 'Executive Report',   icon: 'writer',  group: 'output' },
  { key: 'evidence',  label: 'Evidence & Claims',  icon: 'shield',  group: 'output' },
  { key: 'sources',   label: 'Web Sources',        icon: 'globe',   group: 'output' },
  { key: 'critic',    label: 'Quality Audit',      icon: 'star',    group: 'output' },
  { key: 'telemetry', label: 'Telemetry',          icon: 'wrench',  group: 'output' },
];

export default function DashboardPanel({
  onStartResearch,
  isRunning,
  error,
  verificationState,
  displayPlan,
  liveAgents,
  displayStatuses,
  displayMetrics,
  displayResults,
  currentTopic,
  displayEvidenceClaims,
  displaySourceProfiles,
}) {
  const [activeTab, setActiveTab] = useState('pipeline');

  const hasResults = displayResults.writer || displayResults.search || displayResults.critic;
  const hasEvidence = displayEvidenceClaims && displayEvidenceClaims.totalClaims > 0;
  const hasStarted = isRunning || hasResults || !!displayPlan;

  const execTabs = SIDEBAR_TABS.filter(t => t.group === 'exec');
  const outputTabs = SIDEBAR_TABS.filter(t => t.group === 'output');

  return (
    <div className="dash-shell">
      {/* ── Fixed Sidebar ── */}
      <aside className="dash-sidebar">
        <div className="dash-sidebar-brand">
          <Icon name="beaker" size={16} />
          <span>Research Lab</span>
        </div>

        <div className="dash-sidebar-group">
          <div className="dash-sidebar-label">Execution</div>
          {execTabs.map(tab => (
            <button
              key={tab.key}
              className={`dash-sidebar-tab ${activeTab === tab.key ? 'active' : ''}`}
              onClick={() => setActiveTab(tab.key)}
            >
              <Icon name={tab.icon} size={16} />
              <span>{tab.label}</span>
              {tab.key === 'pipeline' && isRunning && (
                <span className="sidebar-live-dot" />
              )}
            </button>
          ))}
        </div>

        <div className="dash-sidebar-group">
          <div className="dash-sidebar-label">Research Output</div>
          {outputTabs.map(tab => {
            const disabled = !hasResults && tab.key !== 'report';
            return (
              <button
                key={tab.key}
                className={`dash-sidebar-tab ${activeTab === tab.key ? 'active' : ''} ${disabled ? 'disabled' : ''}`}
                onClick={() => !disabled && setActiveTab(tab.key)}
              >
                <Icon name={tab.icon} size={16} />
                <span>{tab.label}</span>
                {tab.key === 'evidence' && hasEvidence && (
                  <span className="sidebar-count">{displayEvidenceClaims.totalClaims}</span>
                )}
              </button>
            );
          })}
        </div>
      </aside>

      {/* ── Main Content ── */}
      <div className="dash-content">
        {/* Compact search bar at top of content */}
        <div className="dash-search-area">
          <Hero
            onStartResearch={onStartResearch}
            isRunning={isRunning}
            hasStarted={hasStarted}
          />
          {error && <div className="err">{error}</div>}
        </div>

        {/* Scrollable content area */}
        <div className="dash-main">
          {/* PIPELINE TAB */}
          {activeTab === 'pipeline' && (
            <div className="dash-pipeline-view">
              <VerificationStatus verificationState={verificationState} />
              <LiveAgentExecution
                liveAgents={liveAgents}
                agentStatuses={displayStatuses}
                verificationState={verificationState}
              />
              <Metrics metrics={displayMetrics} />
            </div>
          )}

          {/* PLANNER TAB */}
          {activeTab === 'planner' && (
            <div>
              <ResearchPlannerView
                researchPlan={displayPlan}
                isRunning={isRunning}
              />
              {!displayPlan && (
                <div className="tab-pending">
                  <div className="tab-pending-icon">
                    <Icon name="planner" size={24} />
                  </div>
                  <p>Start a research query to see the AI planner decompose it into subtasks.</p>
                </div>
              )}
            </div>
          )}

          {/* RESULTS TABS */}
          {['report', 'evidence', 'sources', 'critic', 'telemetry'].includes(activeTab) && (
            <Results
              results={displayResults}
              topic={currentTopic}
              evidenceClaims={displayEvidenceClaims}
              sourceProfiles={displaySourceProfiles}
              forcedTab={activeTab}
            />
          )}
        </div>
      </div>
    </div>
  );
}
