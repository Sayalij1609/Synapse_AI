import React, { useState } from 'react';

/**
 * ResearchPlannerView — Shows the Research Planner Agent's structured output:
 * - Research Objective
 * - Subtasks
 * - Search Queries
 * - Research Strategy
 *
 * Data comes from the backend via SSE; no business logic in this component.
 */
function statusLabel(status) {
  switch (status) {
    case 'completed':
      return 'Completed';
    case 'running':
    case 'in_progress':
      return 'In Progress';
    case 'failed':
      return 'Failed';
    case 'degraded':
      return 'Degraded';
    case 'pending':
    default:
      return 'Pending';
  }
}

export default function ResearchPlannerView({ researchPlan, isRunning }) {
  const [expanded, setExpanded] = useState(true);

  if (!researchPlan && !isRunning) return null;

  const subtasks = researchPlan?.subtasks || [];
  const searchQueries = researchPlan?.searchQueries || [];

  return (
    <div className="planner-view-container">
      <div
        className={`planner-header ${expanded ? 'open' : ''}`}
        onClick={() => setExpanded(e => !e)}
      >
        <div className="planner-header-left">
          <span className="planner-icon">📋</span>
          <div>
            <h3 className="planner-title">Research Planner</h3>
            <span className="planner-subtitle">
              {researchPlan
                ? `${subtasks.length} subtask${subtasks.length !== 1 ? 's' : ''} · ${searchQueries.length} quer${searchQueries.length !== 1 ? 'ies' : 'y'}`
                : 'Decomposing research objective…'}
            </span>
          </div>
        </div>
        <span className="planner-toggle">{expanded ? '▲' : '▼'}</span>
      </div>

      {expanded && (
        <div className="planner-body">
          {/* Pending state */}
          {!researchPlan && isRunning && (
            <div className="planner-pending">
              <div className="planner-spinner" />
              <p>Planner Agent is decomposing your research query into actionable subtasks…</p>
            </div>
          )}

          {researchPlan && (
            <>
              {/* Research Objective */}
              <div className="planner-section">
                <div className="planner-section-label">
                  <span className="section-dot objective" />
                  Research Objective
                </div>
                <div className="planner-objective-text">
                  {researchPlan.objective}
                </div>
              </div>

              {/* Research Strategy */}
              {researchPlan.strategy && (
                <div className="planner-section">
                  <div className="planner-section-label">
                    <span className="section-dot strategy" />
                    Research Strategy
                  </div>
                  <div className="planner-strategy-text">
                    {researchPlan.strategy}
                  </div>
                </div>
              )}

              {/* Subtasks */}
              {subtasks.length > 0 && (
                <div className="planner-section">
                  <div className="planner-section-label">
                    <span className="section-dot subtasks" />
                    Subtasks ({subtasks.length})
                  </div>
                  <div className="planner-subtask-list">
                    {subtasks.map((st, idx) => (
                      <div key={st.subtask_id || idx} className={`planner-subtask-card ${st.status || 'pending'}`}>
                        <div className="subtask-index">{idx + 1}</div>
                        <div className="subtask-content">
                          <div className="subtask-question">
                            {st.question || st.title || `Subtask ${idx + 1}`}
                          </div>
                          {st.search_queries && st.search_queries.length > 0 && (
                            <div className="subtask-queries">
                              {st.search_queries.map((q, qi) => (
                                <span key={qi} className="query-chip">{q}</span>
                              ))}
                            </div>
                          )}
                          {/* Live stats when running or completed */}
                          {(st.discovered_count > 0 || st.extracted_count > 0) && (
                            <div className="subtask-live-stats">
                              {st.discovered_count > 0 && (
                                <span className="stat-chip discovered">🔗 {st.discovered_count} sources</span>
                              )}
                              {st.extracted_count > 0 && (
                                <span className="stat-chip extracted">📄 {st.extracted_count} docs</span>
                              )}
                            </div>
                          )}
                        </div>
                        <div className={`subtask-status-badge ${st.status || 'pending'}`}>
                          {(st.status === 'running' || st.status === 'in_progress') && <span className="status-spinner" />}
                          {statusLabel(st.status)}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Search Queries */}
              {searchQueries.length > 0 && (
                <div className="planner-section">
                  <div className="planner-section-label">
                    <span className="section-dot queries" />
                    Search Queries ({searchQueries.length})
                  </div>
                  <div className="planner-query-grid">
                    {searchQueries.map((q, idx) => (
                      <div key={idx} className="planner-query-item">
                        <span className="query-num">{idx + 1}</span>
                        <span className="query-text">{q}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}
