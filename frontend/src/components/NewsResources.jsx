import React, { useState, useMemo } from 'react';

/**
 * Fallback parser for DuckDuckGo raw output text from SearchAgent:
 * Title : ...
 * URL : ...
 * Snippet : ...
 */
function parseSearchResults(rawText) {
  if (!rawText || typeof rawText !== 'string') return [];

  const items = [];
  const blocks = rawText.split(/-----------------------------|\n\s*\n(?=Title\s*:)/i);

  for (const block of blocks) {
    const titleMatch = block.match(/Title\s*:\s*(.+)/i);
    const urlMatch = block.match(/URL\s*:\s*(https?:\/\/[^\s]+)/i);
    const snippetMatch = block.match(/Snippet\s*:\s*([\s\S]+)/i);

    if (urlMatch) {
      const url = urlMatch[1].trim();
      const title = titleMatch ? titleMatch[1].trim() : 'Web Source';
      let snippet = snippetMatch ? snippetMatch[1].trim() : '';

      snippet = snippet.split('\nTitle :')[0].trim();

      let domain = '';
      try {
        domain = new URL(url).hostname.replace(/^www\./, '');
      } catch {
        domain = 'web';
      }

      items.push({
        title,
        url,
        snippet,
        domain,
        source_type: 'unknown',
        freshness: 'undated',
        publication_date: 'N/A',
        quality_score: 0.5,
        quality_tier: 'adequate',
        authority_indicators: url.startsWith('https://') ? ['HTTPS secure'] : [],
        is_duplicate: false,
      });
    }
  }

  return items;
}

const TYPE_CONFIG = {
  official: { label: 'Official / Gov', icon: '🏛️', colorClass: 'badge-official' },
  academic: { label: 'Academic / Science', icon: '🎓', colorClass: 'badge-academic' },
  news: { label: 'Established News', icon: '📰', colorClass: 'badge-news' },
  industry: { label: 'Industry & Consult', icon: '🏢', colorClass: 'badge-industry' },
  company: { label: 'Tech & Company', icon: '💻', colorClass: 'badge-company' },
  general: { label: 'General Web', icon: '🌐', colorClass: 'badge-general' },
  unknown: { label: 'Web Source', icon: '🔗', colorClass: 'badge-unknown' },
};

const FRESHNESS_CONFIG = {
  current: { label: 'Current (<6mo)', icon: '🟢', colorClass: 'fresh-current' },
  recent: { label: 'Recent (<1yr)', icon: '🟢', colorClass: 'fresh-recent' },
  aging: { label: 'Aging (1-3yr)', icon: '🟡', colorClass: 'fresh-aging' },
  stale: { label: 'Stale (>3yr)', icon: '🔴', colorClass: 'fresh-stale' },
  undated: { label: 'Undated', icon: '⚪', colorClass: 'fresh-undated' },
};

const TIER_COLORS = {
  excellent: '#10b981', // emerald
  good: '#3b82f6',      // blue
  adequate: '#8b5cf6',  // violet
  low: '#f59e0b',       // amber
  poor: '#ef4444',      // rose
  unknown: '#94a3b8',   // slate
};

export default function NewsResources({
  rawText = '',
  sourceProfiles = [],
  sourceQualitySummary = null,
  failedSources = [],
  degradedModes = [],
}) {
  const [filterQuery, setFilterQuery] = useState('');
  const [selectedType, setSelectedType] = useState('all');
  const [selectedFreshness, setSelectedFreshness] = useState('all');
  const [sortBy, setSortBy] = useState('quality');
  const [copiedUrl, setCopiedUrl] = useState(null);
  const [showFailed, setShowFailed] = useState(false);

  // Normalize sources: prefer structured sourceProfiles, fallback to parsed rawText
  const allResources = useMemo(() => {
    if (Array.isArray(sourceProfiles) && sourceProfiles.length > 0) {
      return sourceProfiles.map((p) => ({
        source_id: p.source_id,
        url: p.url,
        title: p.title || 'Web Document',
        domain: p.domain || 'web',
        snippet: p.snippet || p.text ? (p.snippet || p.text).slice(0, 280) + '…' : '',
        source_type: p.source_type || 'unknown',
        freshness: p.freshness || 'undated',
        publication_date: p.publication_date || 'N/A',
        quality_score: typeof p.quality_score === 'number' ? p.quality_score : 0.5,
        quality_tier: p.quality_tier || 'adequate',
        authority_score: p.authority_score || 0,
        authority_indicators: Array.isArray(p.authority_indicators) ? p.authority_indicators : [],
        is_duplicate: Boolean(p.is_duplicate),
        penalties: Array.isArray(p.penalties) ? p.penalties : [],
      }));
    }
    return parseSearchResults(rawText);
  }, [sourceProfiles, rawText]);

  // Filter and sort items
  const filteredResources = useMemo(() => {
    let items = allResources;

    // Type filter
    if (selectedType !== 'all') {
      items = items.filter((r) => r.source_type === selectedType);
    }

    // Freshness filter
    if (selectedFreshness !== 'all') {
      items = items.filter((r) => r.freshness === selectedFreshness);
    }

    // Text query filter
    if (filterQuery.trim()) {
      const q = filterQuery.toLowerCase();
      items = items.filter(
        (r) =>
          r.title.toLowerCase().includes(q) ||
          r.domain.toLowerCase().includes(q) ||
          r.snippet.toLowerCase().includes(q) ||
          r.source_type.toLowerCase().includes(q)
      );
    }

    // Sorting
    return [...items].sort((a, b) => {
      if (sortBy === 'quality') {
        return (b.quality_score || 0) - (a.quality_score || 0);
      }
      if (sortBy === 'authority') {
        return (b.authority_score || 0) - (a.authority_score || 0);
      }
      if (sortBy === 'domain') {
        return a.domain.localeCompare(b.domain);
      }
      return 0;
    });
  }, [allResources, selectedType, selectedFreshness, filterQuery, sortBy]);

  const handleCopy = (url) => {
    navigator.clipboard.writeText(url);
    setCopiedUrl(url);
    setTimeout(() => setCopiedUrl(null), 2000);
  };

  if (!rawText && allResources.length === 0) return null;

  // Calculate summary stats
  const totalCount = allResources.length;
  const avgQuality = sourceQualitySummary?.average_quality != null
    ? Math.round(sourceQualitySummary.average_quality * 100)
    : totalCount > 0
    ? Math.round((allResources.reduce((acc, r) => acc + (r.quality_score || 0), 0) / totalCount) * 100)
    : 0;

  const officialCount = allResources.filter((r) => ['official', 'academic'].includes(r.source_type)).length;
  const freshCount = allResources.filter((r) => ['current', 'recent'].includes(r.freshness)).length;
  const duplicateCount = allResources.filter((r) => r.is_duplicate).length;

  return (
    <div className="resources-container">
      {/* SOURCE QUALITY AUDIT DASHBOARD HEADER */}
      <div className="quality-audit-summary-card">
        <div className="summary-card-header">
          <div className="header-meta">
            <span className="summary-title-icon">🛡️</span>
            <div>
              <h3 className="summary-title">Deterministic Source Quality & Freshness Engine</h3>
              <p className="summary-subtitle">
                Signal-based credibility scoring, domain classification, and temporal freshness validation
              </p>
            </div>
          </div>
          <div className="quality-overall-badge">
            <span className="quality-pct-val">{avgQuality}%</span>
            <span className="quality-pct-lbl">Avg Quality</span>
          </div>
        </div>

        {/* METRICS ROW */}
        <div className="quality-kpi-grid">
          <div className="kpi-cell">
            <span className="kpi-num">{totalCount}</span>
            <span className="kpi-name">Total Discovered</span>
          </div>
          <div className="kpi-cell">
            <span className="kpi-num color-emerald">{officialCount}</span>
            <span className="kpi-name">Official / Academic</span>
          </div>
          <div className="kpi-cell">
            <span className="kpi-num color-cyan">{freshCount}</span>
            <span className="kpi-name">Fresh / Current</span>
          </div>
          {duplicateCount > 0 && (
            <div className="kpi-cell">
              <span className="kpi-num color-amber">{duplicateCount}</span>
              <span className="kpi-name">Syndicated / Duplicate</span>
            </div>
          )}
          {failedSources && failedSources.length > 0 && (
            <div className="kpi-cell">
              <span className="kpi-num color-rose" style={{ color: '#ef4444' }}>{failedSources.length}</span>
              <span className="kpi-name">Inaccessible / Skipped</span>
            </div>
          )}
        </div>

        {/* TRANSPARENT FAULT TOLERANCE AUDIT CARD */}
        {failedSources && failedSources.length > 0 && (
          <div style={{
            background: 'rgba(239, 68, 68, 0.05)',
            border: '1px solid rgba(239, 68, 68, 0.25)',
            borderRadius: '10px',
            padding: '12px 16px',
            marginTop: '16px',
            marginBottom: '8px'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontWeight: '600', color: '#b91c1c' }}>
                <span>🛡️ Audited Inaccessible Sources ({failedSources.length})</span>
                <span style={{ fontSize: '0.75rem', background: '#fee2e2', padding: '2px 8px', borderRadius: '10px', color: '#991b1b' }}>
                  Zero Fabrication · Safe Failover
                </span>
              </div>
              <button
                onClick={() => setShowFailed(!showFailed)}
                style={{
                  background: 'none',
                  border: 'none',
                  color: '#b91c1c',
                  cursor: 'pointer',
                  fontSize: '0.8rem',
                  fontWeight: '600'
                }}
              >
                {showFailed ? '▲ Hide Details' : '▼ View Skipped Sources'}
              </button>
            </div>
            <p style={{ margin: '6px 0 0 0', fontSize: '0.82rem', color: '#7f1d1d', lineHeight: '1.4' }}>
              These URLs could not be scraped due to paywalls, HTTP errors, or timeouts. SYNAPSE AI transparently recorded them and automatically failed over to secondary candidate links and search snippets, ensuring research continued seamlessly without fabricating citations.
            </p>
            {showFailed && (
              <div style={{ marginTop: '10px', display: 'flex', flexDirection: 'column', gap: '6px' }}>
                {failedSources.map((f, i) => (
                  <div key={i} style={{ fontSize: '0.78rem', background: '#ffffff', border: '1px solid #fecaca', padding: '6px 10px', borderRadius: '6px' }}>
                    <div style={{ fontWeight: '600', color: '#991b1b', wordBreak: 'break-all' }}>
                      <a href={f.url} target="_blank" rel="noopener noreferrer" style={{ color: '#b91c1c' }}>
                        {f.url}
                      </a>
                    </div>
                    <div style={{ color: '#4b5563', fontSize: '0.74rem', marginTop: '2px' }}>
                      Error: <strong>{f.error || 'Failed to scrape'}</strong> {f.status_code ? `(HTTP ${f.status_code})` : ''} · Time: {f.timestamp || 'N/A'}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* TYPE FILTER PILLS */}
        <div className="source-filter-pills-row">
          <span className="filter-label">Filter Category:</span>
          {['all', 'official', 'academic', 'news', 'industry', 'company', 'general'].map((t) => {
            const cfg = TYPE_CONFIG[t] || { label: 'All', icon: '✨' };
            const count = t === 'all' ? totalCount : allResources.filter((r) => r.source_type === t).length;
            if (t !== 'all' && count === 0) return null;

            return (
              <button
                key={t}
                className={`type-pill-btn${selectedType === t ? ' active' : ''}`}
                onClick={() => setSelectedType(t)}
              >
                <span>{cfg.icon} {cfg.label}</span>
                <span className="pill-badge">{count}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* SEARCH AND SORT CONTROLS */}
      <div className="resources-controls-bar">
        <div className="resources-search-box">
          <span className="r-search-icon">🔍</span>
          <input
            type="text"
            placeholder="Search by title, domain, or snippet..."
            value={filterQuery}
            onChange={(e) => setFilterQuery(e.target.value)}
          />
          {filterQuery && (
            <button className="clear-filter-btn" onClick={() => setFilterQuery('')}>
              ✕
            </button>
          )}
        </div>

        <div className="resources-sort-group">
          <label htmlFor="source-sort-select">Sort by:</label>
          <select
            id="source-sort-select"
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value)}
            className="source-sort-dropdown"
          >
            <option value="quality">Quality Score (High to Low)</option>
            <option value="authority">Authority Weight</option>
            <option value="domain">Domain Alphabetical</option>
          </select>
        </div>
      </div>

      {/* SOURCES CARDS GRID */}
      {filteredResources.length === 0 ? (
        <div className="no-sources-found">
          <p>No sources match the selected filters.</p>
          <button
            className="action-btn md-btn"
            onClick={() => {
              setSelectedType('all');
              setSelectedFreshness('all');
              setFilterQuery('');
            }}
          >
            Reset All Filters
          </button>
        </div>
      ) : (
        <div className="resources-grid">
          {filteredResources.map((res, idx) => {
            const typeInfo = TYPE_CONFIG[res.source_type] || TYPE_CONFIG.unknown;
            const freshInfo = FRESHNESS_CONFIG[res.freshness] || FRESHNESS_CONFIG.undated;
            const tierColor = TIER_COLORS[res.quality_tier] || '#64748b';
            const qualityPct = Math.round((res.quality_score || 0) * 100);

            return (
              <div
                className={`resource-card${res.is_duplicate ? ' is-duplicate-card' : ''}`}
                key={res.url + idx}
              >
                <div className="resource-card-top">
                  <div className="badges-group">
                    <span className="domain-badge">
                      <img
                        src={`https://www.google.com/s2/favicons?domain=${res.domain}&sz=32`}
                        alt=""
                        className="domain-favicon"
                        onError={(e) => {
                          e.target.style.display = 'none';
                        }}
                      />
                      {res.domain}
                    </span>

                    <span className={`source-type-chip ${typeInfo.colorClass}`}>
                      {typeInfo.icon} {typeInfo.label}
                    </span>
                  </div>

                  <div className="quality-pill-indicator" style={{ borderColor: tierColor }}>
                    <span className="tier-dot" style={{ backgroundColor: tierColor }} />
                    <span className="tier-score">{qualityPct}%</span>
                    <span className="tier-name">{res.quality_tier}</span>
                  </div>
                </div>

                <h4 className="resource-title">
                  <a
                    href={res.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    title={res.title}
                  >
                    {res.title}
                  </a>
                </h4>

                {res.snippet && (
                  <p className="resource-snippet">{res.snippet}</p>
                )}

                {/* METADATA SIGNALS ROW */}
                <div className="metadata-signals-container">
                  <div className="metadata-signals-row">
                    <span className={`freshness-badge ${freshInfo.colorClass}`} title={`Freshness status: ${res.freshness}`}>
                      {freshInfo.icon} {freshInfo.label}
                    </span>

                    {res.publication_date && res.publication_date !== 'N/A' && (
                      <span className="meta-chip pub-date-chip">
                        📅 {res.publication_date}
                      </span>
                    )}

                    {res.is_duplicate && (
                      <span className="meta-chip duplicate-chip">
                        ⚠️ Syndicated Duplicate
                      </span>
                    )}
                  </div>

                  {/* AUTHORITY SIGNALS */}
                  {res.authority_indicators && res.authority_indicators.length > 0 && (
                    <div className="authority-signals-tags">
                      {res.authority_indicators.map((sig, sIdx) => (
                        <span key={sIdx} className="authority-signal-tag">
                          ✓ {sig}
                        </span>
                      ))}
                    </div>
                  )}
                </div>

                <div className="resource-card-footer">
                  <a
                    href={res.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="visit-link-btn"
                  >
                    Visit Source ↗
                  </a>

                  <button
                    className="copy-url-btn"
                    onClick={() => handleCopy(res.url)}
                    title="Copy link"
                  >
                    {copiedUrl === res.url ? '✓ Copied' : '🔗 Copy'}
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
