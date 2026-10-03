import React from 'react';
import Icon from './shared/Icon';

const VERIFICATION_STAGES = [
  { key: 'researching',        label: 'Researching',      desc: 'Gathering evidence from web sources' },
  { key: 'verifying',          label: 'Verifying',        desc: 'Auditing claims against evidence' },
  { key: 'additional_research', label: 'Add\'l Research', desc: 'Filling evidence gaps' },
  { key: 'verified',           label: 'Verified',         desc: 'All claims grounded in evidence' },
  { key: 'completed',          label: 'Completed',        desc: 'Report finalized and ready' },
];

function getStageIndex(status) {
  const idx = VERIFICATION_STAGES.findIndex(s => s.key === status);
  return idx >= 0 ? idx : 0;
}

export default function VerificationStatus({ verificationState }) {
  if (!verificationState || verificationState.status === 'idle') return null;

  const currentIdx = getStageIndex(verificationState.status);
  const isFinished = verificationState.status === 'completed' || verificationState.status === 'verified';

  return (
    <div className="verification-container">
      <div className="verification-header">
        <div className="section-icon rose">
          <Icon name="shield" size={18} />
        </div>
        <span className="verification-title">Verification Pipeline</span>
        {verificationState.currentIteration > 0 && (
          <span className="iteration-badge">
            Cycle {verificationState.currentIteration}/{verificationState.maxIterations}
          </span>
        )}
      </div>

      <div className="verification-track">
        {VERIFICATION_STAGES.map((stage, idx) => {
          const isActive = idx === currentIdx;
          const isPassed = idx < currentIdx;
          // "completed" is the terminal state — show check, not spinner
          const showCheck = isPassed || (isActive && isFinished);
          const showSpinner = isActive && !isFinished;

          return (
            <React.Fragment key={stage.key}>
              <div className={`vs-step ${isActive ? 'active' : ''} ${isPassed ? 'passed' : ''}`}>
                <div className={`vs-dot ${showCheck ? 'passed' : ''} ${isActive ? 'active' : ''}`}>
                  {showCheck ? (
                    <Icon name="check" size={14} strokeWidth={2.5} />
                  ) : showSpinner ? (
                    <span className="spinner sm" />
                  ) : (
                    idx + 1
                  )}
                </div>
                <div className="vs-label">{stage.label}</div>
                {isActive && <div className="vs-desc">{stage.desc}</div>}
              </div>
              {idx < VERIFICATION_STAGES.length - 1 && (
                <div className={`vs-line ${isPassed ? 'passed' : ''}`} />
              )}
            </React.Fragment>
          );
        })}
      </div>

      {verificationState.history && verificationState.history.length > 0 && (
        <div className="verification-history">
          {verificationState.history.map((h, idx) => (
            <div key={idx} className={`vh-entry ${h.decision}`}>
              <span className="vh-iteration">Cycle {h.iteration}</span>
              <span className={`vh-decision ${h.decision}`}>
                {h.decision === 'verified' ? '✓ Verified' : h.decision === 'needs_research' ? '↻ Needs Research' : h.decision}
              </span>
              {h.result?.unresolved_count > 0 && (
                <span className="vh-unresolved">{h.result.unresolved_count} unresolved</span>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
