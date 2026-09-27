import React from 'react';

/**
 * VerificationStatus — Shows the verification progression status:
 * Researching → Verifying → Additional Research → Verified → Completed
 *
 * All state comes from the backend verification system via SSE.
 */

const VERIFICATION_STAGES = [
  { key: 'researching', label: 'Researching', icon: '🔬', desc: 'Gathering evidence from web sources' },
  { key: 'verifying', label: 'Verifying', icon: '🛡️', desc: 'Auditing claims against evidence' },
  { key: 'additional_research', label: 'Additional Research', icon: '🔄', desc: 'Filling evidence gaps' },
  { key: 'verified', label: 'Verified', icon: '✅', desc: 'All claims grounded in evidence' },
  { key: 'completed', label: 'Completed', icon: '🏁', desc: 'Report finalized and ready' },
];

function getStageIndex(status) {
  const idx = VERIFICATION_STAGES.findIndex(s => s.key === status);
  return idx >= 0 ? idx : 0;
}

export default function VerificationStatus({ verificationState }) {
  if (!verificationState || verificationState.status === 'idle') return null;

  const currentIdx = getStageIndex(verificationState.status);

  return (
    <div className="verification-status-container">
      <div className="verification-status-header">
        <span className="vs-header-icon">🛡️</span>
        <span className="vs-header-title">Verification Pipeline</span>
        {verificationState.currentIteration > 0 && (
          <span className="vs-iteration-badge">
            Cycle {verificationState.currentIteration}/{verificationState.maxIterations}
          </span>
        )}
      </div>

      <div className="verification-stage-track">
        {VERIFICATION_STAGES.map((stage, idx) => {
          const isActive = idx === currentIdx;
          const isPassed = idx < currentIdx;
          // For additional_research, it can cycle, so also show as passed if we went beyond
          const isPassedOrActive = isPassed || isActive;

          return (
            <React.Fragment key={stage.key}>
              <div className={`vs-stage ${isActive ? 'active' : ''} ${isPassed ? 'passed' : ''}`}>
                <div className={`vs-stage-dot ${isActive ? 'active' : ''} ${isPassed ? 'passed' : ''}`}>
                  {isPassed ? '✓' : isActive ? stage.icon : (idx + 1)}
                </div>
                <div className="vs-stage-info">
                  <div className="vs-stage-label">{stage.label}</div>
                  {isActive && <div className="vs-stage-desc">{stage.desc}</div>}
                </div>
              </div>
              {idx < VERIFICATION_STAGES.length - 1 && (
                <div className={`vs-stage-line ${isPassed ? 'passed' : ''}`} />
              )}
            </React.Fragment>
          );
        })}
      </div>

      {/* Verification History */}
      {verificationState.history && verificationState.history.length > 0 && (
        <div className="verification-history">
          {verificationState.history.map((h, idx) => (
            <div key={idx} className={`vh-entry ${h.decision}`}>
              <span className="vh-iteration">Cycle {h.iteration}</span>
              <span className={`vh-decision ${h.decision}`}>
                {h.decision === 'verified' ? '✅ Verified' : h.decision === 'needs_research' ? '🔄 Needs Research' : h.decision}
              </span>
              {h.result?.unresolved_count > 0 && (
                <span className="vh-unresolved">{h.result.unresolved_count} unresolved claims</span>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
