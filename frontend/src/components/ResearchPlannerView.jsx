import React, { useState } from 'react';
import Icon from './shared/Icon';
import StatusBadge from './shared/StatusBadge';

export default function ResearchPlannerView({ researchPlan, isRunning }) {
  const [open, setOpen] = useState(true);

  if (!researchPlan) return null;

  const { objective, subtasks = [], searchQueries = [], strategy } = researchPlan;
  if (!objective && subtasks.length === 0) return null;

  return (
    <div className="planner-container">
      <div className="planner-header" onClick={() => setOpen(o => !o)}>
        <div className="planner-header-left">
          <div className="planner-icon">
            <Icon name="planner" size={18} />
          </div>
          <div>
            <div className="planner-title">Research Planner</div>
            <div className="planner-subtitle">
              {subtasks.length > 0 ? `${subtasks.length} subtasks generated` : 'Generating plan…'}
            </div>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)' }}>
          {subtasks.length > 0 && (
            <span className="planner-count">{subtasks.length}</span>
          )}
          <span className={`planner-toggle ${open ? 'open' : ''}`}>
            <Icon name="chevronRight" size={16} />
          </span>
        </div>
      </div>

      <div className={`planner-body ${open ? 'open' : ''}`}>
        <div className="planner-content">
          {objective && (
            <div className="planner-objective">{objective}</div>
          )}

          {subtasks.length > 0 && (
            <div className="subtask-grid">
              {subtasks.map((st, idx) => {
                const status = st.status || 'pending';
                return (
                  <div className={`subtask-card ${status}`} key={st.subtask_id || idx}>
                    <div className="subtask-num">
                      {status === 'completed' ? (
                        <Icon name="check" size={14} strokeWidth={2.5} />
                      ) : status === 'running' || status === 'in_progress' ? (
                        <span className="spinner sm" />
                      ) : (
                        idx + 1
                      )}
                    </div>

                    <div className="subtask-info">
                      <div className="subtask-question">
                        {st.question || st.subtask || `Subtask ${idx + 1}`}
                      </div>

                      {st.search_queries && st.search_queries.length > 0 && (
                        <div className="subtask-queries">
                          {st.search_queries.map((q, qi) => (
                            <span className="subtask-query-chip" key={qi}>{q}</span>
                          ))}
                        </div>
                      )}

                      {(st.sources_discovered > 0 || st.docs_extracted > 0) && (
                        <div className="subtask-stats">
                          {st.sources_discovered > 0 && (
                            <span className="subtask-stat discovered">
                              <Icon name="globe" size={10} />
                              {st.sources_discovered} found
                            </span>
                          )}
                          {st.docs_extracted > 0 && (
                            <span className="subtask-stat extracted">
                              <Icon name="document" size={10} />
                              {st.docs_extracted} extracted
                            </span>
                          )}
                        </div>
                      )}
                    </div>

                    <StatusBadge status={status} showDot={false} />
                  </div>
                );
              })}
            </div>
          )}

          {searchQueries && searchQueries.length > 0 && (
            <div className="search-queries-section">
              <h4>Search Queries</h4>
              <div className="search-queries-grid">
                {searchQueries.map((q, i) => (
                  <span className="chip mono" key={i}>{q}</span>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
