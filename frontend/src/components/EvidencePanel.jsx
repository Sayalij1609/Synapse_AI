import React, { useState } from 'react';

/**
 * EvidencePanel — Shows structured evidence lineage for every claim:
 * Claim → Evidence → Source → URL
 *
 * Includes confidence indicators from the backend verification system.
 * Data is entirely from backend — no business logic here.
 */
export default function EvidencePanel({ evidenceClaims, sourceProfiles }) {
  const [filter, setFilter] = useState('all'); // all | grounded | unsupported | insufficient

  if (!evidenceClaims || evidenceClaims.totalClaims === 0) return null;

  const { grounded, unsupported, insufficient, citationTrace } = evidenceClaims;

  const allClaims = [
    ...grounded.map(c => ({ ...c, _type: 'grounded' })),
    ...insufficient.map(c => ({ ...c, _type: 'insufficient' })),
    ...unsupported.map(c => ({ ...c, _type: 'unsupported' })),
  ];

  const filteredClaims = filter === 'all'
    ? allClaims
    : allClaims.filter(c => c._type === filter);

  const getConfidenceClass = (confidence) => {
    if (confidence >= 0.8) return 'confidence-high';
    if (confidence >= 0.5) return 'confidence-medium';
    return 'confidence-low';
  };

  const getConfidenceLabel = (confidence) => {
    if (confidence >= 0.8) return 'High';
    if (confidence >= 0.5) return 'Medium';
    return 'Low';
  };

  const getStatusIcon = (type) => {
    switch (type) {
      case 'grounded': return '✅';
      case 'insufficient': return '⚠️';
      case 'unsupported': return '❌';
      default: return '—';
    }
  };

  // Build a source lookup from profiles
  const sourceMap = {};
  (sourceProfiles || []).forEach(sp => {
    const key = sp.source_id || sp.url;
    if (key) sourceMap[key] = sp;
  });

  return (
    <div className="evidence-panel-container">
      <div className="evidence-panel-header">
        <div className="evidence-header-left">
          <span className="evidence-icon">🔬</span>
          <div>
            <h3 className="evidence-title">Evidence & Claim Lineage</h3>
            <span className="evidence-subtitle">
              {grounded.length} grounded · {insufficient.length} insufficient · {unsupported.length} unsupported
            </span>
          </div>
        </div>

        <div className="evidence-filter-group">
          {[
            { key: 'all', label: 'All', count: allClaims.length },
            { key: 'grounded', label: 'Grounded', count: grounded.length },
            { key: 'insufficient', label: 'Insufficient', count: insufficient.length },
            { key: 'unsupported', label: 'Unsupported', count: unsupported.length },
          ].map(f => (
            <button
              key={f.key}
              className={`evidence-filter-btn ${filter === f.key ? 'active' : ''} ${f.key}`}
              onClick={() => setFilter(f.key)}
            >
              {f.label} ({f.count})
            </button>
          ))}
        </div>
      </div>

      <div className="evidence-claims-list">
        {filteredClaims.length === 0 && (
          <div className="evidence-empty">No claims match this filter.</div>
        )}

        {filteredClaims.map((claim, idx) => {
          const claimId = claim.claim_id || `claim-${idx}`;
          const srcIds = claim.supporting_source_ids || [];
          const chunkIds = claim.evidence_chunk_ids || [];
          const confidence = claim.confidence ?? 0.5;
          const trace = citationTrace?.[claimId] || null;

          return (
            <div key={claimId} className={`evidence-claim-card ${claim._type}`}>
              {/* Claim */}
              <div className="claim-lineage-row claim-row">
                <div className="lineage-connector">
                  <span className="lineage-node claim-node">{getStatusIcon(claim._type)}</span>
                  <div className="lineage-line" />
                </div>
                <div className="lineage-content">
                  <div className="lineage-label">Claim</div>
                  <div className="claim-text">{claim.text}</div>
                  <div className="claim-meta-row">
                    <span className={`confidence-badge ${getConfidenceClass(confidence)}`}>
                      {getConfidenceLabel(confidence)} Confidence ({(confidence * 100).toFixed(0)}%)
                    </span>
                    <span className={`verification-tag ${claim._type}`}>
                      {claim._type === 'grounded' ? 'Grounded' : claim._type === 'insufficient' ? 'Insufficient Evidence' : 'Unsupported'}
                    </span>
                  </div>
                  {claim.verification_notes && (
                    <div className="claim-notes">{claim.verification_notes}</div>
                  )}
                </div>
              </div>

              {/* Evidence */}
              {(chunkIds.length > 0 || trace?.evidence_chain) && (
                <div className="claim-lineage-row evidence-row">
                  <div className="lineage-connector">
                    <span className="lineage-node evidence-node">📄</span>
                    <div className="lineage-line" />
                  </div>
                  <div className="lineage-content">
                    <div className="lineage-label">Evidence</div>
                    {trace?.evidence_chain?.slice(0, 2).map((ec, ei) => (
                      <div key={ei} className="evidence-excerpt">
                        <span className="excerpt-text">
                          "{ec.excerpt || 'Evidence chunk referenced'}"
                        </span>
                        {ec.similarity_score && (
                          <span className="similarity-score">
                            {(ec.similarity_score * 100).toFixed(0)}% match
                          </span>
                        )}
                      </div>
                    ))}
                    {!trace?.evidence_chain && chunkIds.length > 0 && (
                      <div className="evidence-excerpt">
                        <span className="excerpt-text">{chunkIds.length} evidence chunk{chunkIds.length > 1 ? 's' : ''} referenced</span>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Source */}
              {srcIds.length > 0 && (
                <div className="claim-lineage-row source-row">
                  <div className="lineage-connector">
                    <span className="lineage-node source-node">📚</span>
                    <div className="lineage-line last" />
                  </div>
                  <div className="lineage-content">
                    <div className="lineage-label">Source</div>
                    {srcIds.map((sid, si) => {
                      const src = sourceMap[sid] || trace?.evidence_chain?.find(e => e.source?.source_id === sid)?.source || {};
                      return (
                        <div key={si} className="source-card-mini">
                          <div className="source-mini-title">{src.title || sid}</div>
                          {src.url && (
                            <a
                              className="source-mini-url"
                              href={src.url}
                              target="_blank"
                              rel="noopener noreferrer"
                            >
                              {src.url}
                            </a>
                          )}
                          <div className="source-mini-meta">
                            {src.domain && <span className="source-meta-chip domain">{src.domain}</span>}
                            {src.source_type && <span className="source-meta-chip type">{src.source_type}</span>}
                            {src.publication_date && src.publication_date !== 'N/A' && (
                              <span className="source-meta-chip date">{src.publication_date}</span>
                            )}
                            {src.freshness && src.freshness !== 'undated' && (
                              <span className={`source-meta-chip freshness ${src.freshness}`}>{src.freshness}</span>
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
