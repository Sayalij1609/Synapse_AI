import React, { useState, useMemo } from 'react';
import Icon from './shared/Icon';

function parseSearchResults(rawText) {
  if (!rawText || typeof rawText !== 'string') return [];
  const items = [];
  const blocks = rawText.split(/-----------------------------|\\n\\s*\\n(?=Title\\s*:)/i);
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
      try { domain = new URL(url).hostname.replace(/^www\./, ''); } catch { domain = 'web'; }
      items.push({ title, url, snippet, domain, source_type: 'unknown', freshness: 'undated', publication_date: 'N/A', quality_score: 0.5, quality_tier: 'adequate', authority_indicators: url.startsWith('https://') ? ['HTTPS secure'] : [], is_duplicate: false });
    }
  }
  return items;
}

const TIER_COLORS = {
  excellent: 'var(--success)', good: 'var(--cyan)', adequate: 'var(--accent)',
  low: 'var(--warning)', poor: 'var(--danger)', unknown: 'var(--text-muted)',
};

export default function NewsResources({ rawText = '', sourceProfiles = [], sourceQualitySummary = null, failedSources = [], degradedModes = [] }) {
  const [filterQuery, setFilterQuery] = useState('');
  const [selectedType, setSelectedType] = useState('all');
  const [sortBy, setSortBy] = useState('quality');
  const [showFailed, setShowFailed] = useState(false);

  const allResources = useMemo(() => {
    if (Array.isArray(sourceProfiles) && sourceProfiles.length > 0) {
      return sourceProfiles.map((p) => ({
        source_id: p.source_id, url: p.url, title: p.title || 'Web Document', domain: p.domain || 'web',
        snippet: p.snippet || p.text ? (p.snippet || p.text).slice(0, 280) + '…' : '',
        source_type: p.source_type || 'unknown', freshness: p.freshness || 'undated',
        publication_date: p.publication_date || 'N/A',
        quality_score: typeof p.quality_score === 'number' ? p.quality_score : 0.5,
        quality_tier: p.quality_tier || 'adequate',
        authority_score: p.authority_score || 0,
        authority_indicators: Array.isArray(p.authority_indicators) ? p.authority_indicators : [],
        is_duplicate: Boolean(p.is_duplicate),
      }));
    }
    return parseSearchResults(rawText);
  }, [sourceProfiles, rawText]);

  const filteredResources = useMemo(() => {
    let items = allResources;
    if (selectedType !== 'all') items = items.filter((r) => r.source_type === selectedType);
    if (filterQuery.trim()) {
      const q = filterQuery.toLowerCase();
      items = items.filter((r) => r.title.toLowerCase().includes(q) || r.domain.toLowerCase().includes(q));
    }
    return [...items].sort((a, b) => {
      if (sortBy === 'quality') return (b.quality_score || 0) - (a.quality_score || 0);
      if (sortBy === 'domain') return a.domain.localeCompare(b.domain);
      return 0;
    });
  }, [allResources, selectedType, filterQuery, sortBy]);

  if (!rawText && allResources.length === 0) return null;

  const totalCount = allResources.length;
  const avgQuality = sourceQualitySummary?.average_quality != null
    ? Math.round(sourceQualitySummary.average_quality * 100)
    : totalCount > 0 ? Math.round((allResources.reduce((acc, r) => acc + (r.quality_score || 0), 0) / totalCount) * 100) : 0;
  const officialCount = allResources.filter((r) => ['official', 'academic'].includes(r.source_type)).length;
  const freshCount = allResources.filter((r) => ['current', 'recent'].includes(r.freshness)).length;

  const typeFilters = ['all', 'official', 'academic', 'news', 'industry', 'company', 'general']
    .map(t => ({ key: t, count: t === 'all' ? totalCount : allResources.filter(r => r.source_type === t).length }))
    .filter(t => t.key === 'all' || t.count > 0);

  return (
    <div className="sources-container">
      {/* Quality Summary */}
      <div style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius-lg)', padding: 'var(--space-6)', marginBottom: 'var(--space-6)' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 'var(--space-5)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)' }}>
            <div className="section-icon amber"><Icon name="shield" size={18} /></div>
            <div>
              <div style={{ fontWeight: 700, fontSize: 'var(--text-base)' }}>Source Quality Engine</div>
              <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>
                Credibility scoring, domain classification, freshness validation
              </div>
            </div>
          </div>
          <div style={{ textAlign: 'center', background: 'var(--accent-muted)', padding: 'var(--space-3) var(--space-5)', borderRadius: 'var(--radius-md)' }}>
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: 'var(--text-xl)', fontWeight: 700, color: 'var(--accent)' }}>{avgQuality}%</div>
            <div style={{ fontSize: '10px', color: 'var(--text-muted)', fontWeight: 600 }}>Avg Quality</div>
          </div>
        </div>

        <div className="metrics-dock" style={{ marginBottom: 'var(--space-4)' }}>
          <div className="metric-tile"><div className="metric-icon sources"><Icon name="globe" size={16} /></div><div><div className="metric-value">{totalCount}</div><div className="metric-label">Discovered</div></div></div>
          <div className="metric-tile"><div className="metric-icon words"><Icon name="star" size={16} /></div><div><div className="metric-value">{officialCount}</div><div className="metric-label">Official/Academic</div></div></div>
          <div className="metric-tile"><div className="metric-icon time"><Icon name="clock" size={16} /></div><div><div className="metric-value">{freshCount}</div><div className="metric-label">Fresh/Current</div></div></div>
          <div className="metric-tile"><div className="metric-icon score"><Icon name="flag" size={16} /></div><div><div className="metric-value">{failedSources.length}</div><div className="metric-label">Skipped</div></div></div>
        </div>

        {/* Failed sources */}
        {failedSources.length > 0 && (
          <div style={{ background: 'var(--danger-muted)', border: '1px solid rgba(239,68,68,0.2)', borderRadius: 'var(--radius-md)', padding: 'var(--space-3) var(--space-4)' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)', fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--danger)' }}>
                <Icon name="shield" size={14} /> Inaccessible Sources ({failedSources.length})
                <span className="chip rose" style={{ fontSize: '9px' }}>Safe Failover</span>
              </div>
              <button className="btn btn-ghost btn-sm" onClick={() => setShowFailed(!showFailed)} style={{ color: 'var(--danger)', fontSize: 'var(--text-xs)' }}>
                {showFailed ? 'Hide' : 'Show'}
              </button>
            </div>
            {showFailed && (
              <div style={{ marginTop: 'var(--space-3)', display: 'flex', flexDirection: 'column', gap: 'var(--space-2)' }}>
                {failedSources.map((f, i) => (
                  <div key={i} style={{ fontSize: 'var(--text-xs)', background: 'var(--bg-surface)', border: '1px solid var(--border)', padding: 'var(--space-2) var(--space-3)', borderRadius: 'var(--radius-sm)' }}>
                    <a href={f.url} target="_blank" rel="noopener noreferrer" style={{ color: 'var(--danger)', wordBreak: 'break-all', fontSize: '11px' }}>{f.url}</a>
                    <div style={{ color: 'var(--text-muted)', fontSize: '10px', marginTop: '2px' }}>
                      {f.error || 'Failed to scrape'} {f.status_code ? `(HTTP ${f.status_code})` : ''}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Type filters */}
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--space-2)', marginTop: 'var(--space-4)' }}>
          <span style={{ fontSize: 'var(--text-xs)', fontWeight: 600, color: 'var(--text-faint)', textTransform: 'uppercase', letterSpacing: '0.06em', alignSelf: 'center' }}>Filter:</span>
          {typeFilters.map(t => (
            <button key={t.key} className={`filter-btn ${selectedType === t.key ? 'active' : ''}`} onClick={() => setSelectedType(t.key)}>
              {t.key === 'all' ? 'All' : t.key} <span className="filter-count">{t.count}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Search bar */}
      <div style={{ display: 'flex', gap: 'var(--space-3)', marginBottom: 'var(--space-6)', alignItems: 'center' }}>
        <div className="search-input-wrap" style={{ flex: 1, padding: 'var(--space-1) var(--space-3)' }}>
          <Icon name="search" size={15} />
          <input className="search-input" type="text" placeholder="Search by title or domain…" value={filterQuery} onChange={(e) => setFilterQuery(e.target.value)} style={{ fontSize: 'var(--text-sm)', padding: 'var(--space-2) 0' }} />
        </div>
        <select value={sortBy} onChange={(e) => setSortBy(e.target.value)} className="input-field" style={{ width: 'auto', padding: 'var(--space-2) var(--space-3)', fontSize: 'var(--text-xs)', cursor: 'pointer' }}>
          <option value="quality">Sort: Quality</option>
          <option value="domain">Sort: Domain</option>
        </select>
      </div>

      {/* Source grid */}
      {filteredResources.length === 0 ? (
        <div className="tab-pending">
          <p style={{ fontSize: 'var(--text-sm)' }}>No sources match filters.</p>
          <button className="btn btn-secondary btn-sm" onClick={() => { setSelectedType('all'); setFilterQuery(''); }}>Reset Filters</button>
        </div>
      ) : (
        <div className="source-grid">
          {filteredResources.map((res, idx) => {
            const qualityPct = Math.round((res.quality_score || 0) * 100);
            const tierColor = TIER_COLORS[res.quality_tier] || 'var(--text-muted)';
            const qualityClass = qualityPct >= 70 ? 'high' : qualityPct >= 40 ? 'medium' : 'low';

            return (
              <div className="source-card" key={res.url + idx}>
                <div className="source-card-header">
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div className="source-title">
                      <a href={res.url} target="_blank" rel="noopener noreferrer" style={{ color: 'var(--text-primary)' }}>
                        {res.title}
                      </a>
                    </div>
                    <div className="source-domain">{res.domain}</div>
                  </div>
                  <span className={`source-quality-score ${qualityClass}`}>{qualityPct}%</span>
                </div>

                {res.snippet && (
                  <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)', lineHeight: 1.5, marginBottom: 'var(--space-3)', display: '-webkit-box', WebkitLineClamp: 3, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>
                    {res.snippet}
                  </div>
                )}

                <div className="source-meta">
                  <span className="chip" style={{ fontSize: '10px', padding: '1px 6px' }}>{res.source_type}</span>
                  {res.freshness !== 'undated' && (
                    <span className={`chip ${res.freshness === 'current' || res.freshness === 'recent' ? 'accent' : res.freshness === 'aging' ? 'amber' : 'rose'}`} style={{ fontSize: '10px', padding: '1px 6px' }}>
                      {res.freshness}
                    </span>
                  )}
                  {res.is_duplicate && <span className="chip amber" style={{ fontSize: '10px', padding: '1px 6px' }}>duplicate</span>}
                  {res.authority_indicators?.map((sig, i) => (
                    <span key={i} className="chip cyan" style={{ fontSize: '10px', padding: '1px 6px' }}>
                      <Icon name="check" size={8} strokeWidth={3} /> {sig}
                    </span>
                  ))}
                </div>

                <div style={{ display: 'flex', gap: 'var(--space-2)', marginTop: 'var(--space-3)', paddingTop: 'var(--space-3)', borderTop: '1px solid var(--border-subtle)' }}>
                  <a href={res.url} target="_blank" rel="noopener noreferrer" className="btn btn-ghost btn-sm" style={{ fontSize: '11px' }}>
                    <Icon name="globe" size={12} /> Visit Source
                  </a>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
