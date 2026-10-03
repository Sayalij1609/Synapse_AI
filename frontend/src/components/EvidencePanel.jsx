import React, { useState } from 'react';
import Icon from './shared/Icon';

export default function EvidencePanel({ evidenceClaims, sourceProfiles }) {
  const [filter, setFilter] = useState('all');

  if (!evidenceClaims || evidenceClaims.totalClaims === 0) return null;

  const { grounded, unsupported, insufficient, citationTrace } = evidenceClaims;
  const allClaims = [
    ...grounded.map(c => ({ ...c, _type: 'grounded' })),
    ...insufficient.map(c => ({ ...c, _type: 'insufficient' })),
    ...unsupported.map(c => ({ ...c, _type: 'unsupported' })),
  ];
  const filteredClaims = filter === 'all' ? allClaims : allClaims.filter(c => c._type === filter);

  const sourceMap = {};
  (sourceProfiles || []).forEach(sp => {
    const key = sp.source_id || sp.url;
    if (key) sourceMap[key] = sp;
  });

  const getConfLevel = (c) => c >= 0.8 ? 'high' : c >= 0.5 ? 'medium' : 'low';

  return (
    <div className="evidence-container">
      <div className="evidence-header">
        <div className="evidence-header-left">
          <div className="section-icon accent">
            <Icon name="shield" size={18} />
          </div>
          <div>
            <div className="evidence-title">Evidence & Claim Lineage</div>
            <div className="evidence-summary-text">
              {grounded.length} grounded · {insufficient.length} insufficient · {unsupported.length} unsupported
            </div>
          </div>
        </div>

        <div className="evidence-filters">
          {[
            { key: 'all', label: 'All', count: allClaims.length },
            { key: 'grounded', label: 'Grounded', count: grounded.length },
            { key: 'insufficient', label: 'Insufficient', count: insufficient.length },
            { key: 'unsupported', label: 'Unsupported', count: unsupported.length },
          ].map(f => (
            <button
              key={f.key}
              className={`filter-btn ${filter === f.key ? 'active' : ''}`}
              onClick={() => setFilter(f.key)}
            >
              {f.label}<span className="filter-count">{f.count}</span>
            </button>
          ))}
        </div>
      </div>

      <div className="claims-list">
        {filteredClaims.length === 0 && (
          <div className="tab-pending">
            <p style={{ fontSize: 'var(--text-sm)' }}>No claims match this filter.</p>
          </div>
        )}

        {filteredClaims.map((claim, idx) => {
          const claimId = claim.claim_id || `claim-${idx}`;
          const srcIds = claim.supporting_source_ids || [];
          const chunkIds = claim.evidence_chunk_ids || [];
          const confidence = claim.confidence ?? 0.5;
          const level = getConfLevel(confidence);
          const trace = citationTrace?.[claimId] || null;

          return (
            <div key={claimId} className={`claim-card ${claim._type}`}>
              <div className="claim-header">
                <div className="claim-text">{claim.text}</div>
                <span className={`status-badge ${claim._type === 'grounded' ? 'completed' : claim._type === 'insufficient' ? 'degraded' : 'failed'}`}>
                  {claim._type === 'grounded' && <Icon name="check" size={10} strokeWidth={3} />}
                  {claim._type === 'insufficient' && '⚠'}
                  {claim._type === 'unsupported' && '✗'}
                  {claim._type}
                </span>
              </div>

              <div className="claim-meta">
                <div className="confidence-bar">
                  <div className="confidence-fill">
                    <div className={`confidence-fill-inner ${level}`} style={{ width: `${confidence * 100}%` }} />
                  </div>
                  <span style={{ color: level === 'high' ? 'var(--success)' : level === 'medium' ? 'var(--warning)' : 'var(--danger)' }}>
                    {(confidence * 100).toFixed(0)}%
                  </span>
                </div>
              </div>

              {claim.verification_notes && (
                <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)', marginTop: 'var(--space-2)', lineHeight: 1.5, fontStyle: 'italic' }}>
                  {claim.verification_notes}
                </div>
              )}

              {(chunkIds.length > 0 || trace?.evidence_chain) && (
                <div style={{ marginTop: 'var(--space-3)', paddingTop: 'var(--space-3)', borderTop: '1px solid var(--border-subtle)' }}>
                  <div style={{ fontSize: '10px', fontWeight: 700, color: 'var(--text-faint)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 'var(--space-2)' }}>
                    Evidence
                  </div>
                  {trace?.evidence_chain?.slice(0, 2).map((ec, ei) => (
                    <div key={ei} style={{ fontSize: 'var(--text-xs)', color: 'var(--text-secondary)', padding: 'var(--space-2) var(--space-3)', background: 'var(--bg-elevated)', borderRadius: 'var(--radius-sm)', marginBottom: 'var(--space-1)', lineHeight: 1.5 }}>
                      "{ec.excerpt || 'Evidence chunk referenced'}"
                      {ec.similarity_score && (
                        <span className="chip accent" style={{ marginLeft: 'var(--space-2)', fontSize: '9px', padding: '0 4px' }}>
                          {(ec.similarity_score * 100).toFixed(0)}% match
                        </span>
                      )}
                    </div>
                  ))}
                  {!trace?.evidence_chain && chunkIds.length > 0 && (
                    <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>
                      {chunkIds.length} evidence chunk{chunkIds.length > 1 ? 's' : ''} referenced
                    </div>
                  )}
                </div>
              )}

              {srcIds.length > 0 && (
                <div className="claim-sources">
                  <div style={{ fontSize: '10px', fontWeight: 700, color: 'var(--text-faint)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 'var(--space-2)' }}>
                    Sources
                  </div>
                  {srcIds.map((sid, si) => {
                    const src = sourceMap[sid] || trace?.evidence_chain?.find(e => e.source?.source_id === sid)?.source || {};
                    return (
                      <div key={si} style={{ marginBottom: 'var(--space-2)' }}>
                        <div style={{ fontSize: 'var(--text-xs)', fontWeight: 600, color: 'var(--text-primary)' }}>
                          {src.title || sid}
                        </div>
                        {src.url && (
                          <a className="claim-source-link" href={src.url} target="_blank" rel="noopener noreferrer">
                            <Icon name="globe" size={10} />
                            {src.domain || src.url}
                          </a>
                        )}
                        <div style={{ display: 'flex', gap: 'var(--space-1)', marginTop: '2px', flexWrap: 'wrap' }}>
                          {src.source_type && <span className="chip" style={{ fontSize: '9px', padding: '0 4px' }}>{src.source_type}</span>}
                          {src.freshness && src.freshness !== 'undated' && (
                            <span className={`chip ${src.freshness === 'fresh' ? 'accent' : src.freshness === 'recent' ? 'cyan' : 'amber'}`} style={{ fontSize: '9px', padding: '0 4px' }}>
                              {src.freshness}
                            </span>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
