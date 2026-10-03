import { useState } from 'react';
import Icon from './shared/Icon';

const SUGGESTIONS = [
  'Autonomous AI Agents 2026',
  'CRISPR Gene Editing Breakthroughs',
  'Nuclear Fusion Net Energy Gains',
  'Quantum Error Correction Milestones',
  'AI in Diagnostic Healthcare',
];

export default function Hero({ onStartResearch, isRunning, hasStarted }) {
  const [query, setQuery] = useState('');
  const [error, setError] = useState(null);

  const handleRun = () => {
    const q = query.trim();
    if (!q) {
      setError('Please enter a research topic.');
      return;
    }
    setError(null);
    onStartResearch(q);
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !isRunning) handleRun();
  };

  // Compact mode: after research starts, shrink to a single-line bar
  const compact = isRunning || hasStarted;

  return (
    <div className={`search-panel ${compact ? 'compact' : ''}`}>
      {!compact && (
        <div className="search-panel-header">
          <h2>
            <Icon name="beaker" size={22} />
            Autonomous Research Lab
          </h2>
          <p>Query live web intelligence, scrape detailed content, and generate executive reports.</p>
        </div>
      )}

      <div className="search-input-wrap">
        <Icon name="search" size={compact ? 16 : 18} />
        <input
          type="text"
          id="q"
          className="search-input"
          placeholder={compact ? "New research topic..." : "Enter a research topic, market trend, or scientific question..."}
          autoComplete="off"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={handleKeyDown}
        />
        <button
          className="search-run-btn"
          id="go"
          onClick={handleRun}
          disabled={isRunning}
        >
          {isRunning ? (
            <>
              <span className="spinner sm" style={{ borderTopColor: '#fff' }} />
              Synthesizing…
            </>
          ) : (
            <>
              Run Pipeline
              <Icon name="arrowRight" size={14} strokeWidth={2.5} />
            </>
          )}
        </button>
      </div>

      {!compact && (
        <div className="search-suggestions">
          <span className="sug-label">Trending:</span>
          {SUGGESTIONS.map((s) => (
            <span className="sug-chip" key={s} onClick={() => setQuery(s)}>
              {s}
            </span>
          ))}
        </div>
      )}

      {error && <div className="err" style={{ marginTop: 'var(--space-3)' }}>{error}</div>}
    </div>
  );
}
