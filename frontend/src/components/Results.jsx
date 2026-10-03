import { useState } from 'react';
import { marked } from 'marked';
import { downloadPdf, downloadDocx, downloadMarkdown, fetchSessionDossier, triggerDownload } from '../api';
import Icon from './shared/Icon';
import NewsResources from './NewsResources';
import AgentTelemetryView from './AgentTelemetryView';
import EvidencePanel from './EvidencePanel';

/**
 * Client-side defense-in-depth: strip JSON artifacts and binary garbage
 * from report markdown before rendering.
 */
function sanitizeReportMarkdown(raw) {
  if (!raw) return '';
  let text = raw;
  text = text.replace(/^\s*\{[\s\S]*?"(?:executive_)?summary"\s*:/m, '');
  text = text.replace(/"claims"\s*:\s*\[[\s\S]*?\]\s*\}/m, '');
  text = text.split('\n').filter(line => {
    if (line.trim().length === 0) return true;
    const printable = [...line].filter(ch => ch.charCodeAt(0) >= 32 || ch === '\n' || ch === '\t').length;
    return printable / line.length > 0.8;
  }).join('\n');
  return text;
}

function ExpandablePanel({ label, agentLabel, content }) {
  const [open, setOpen] = useState(false);
  if (!content) return null;

  return (
    <div className="expand-panel">
      <button className={`expand-trigger ${open ? 'open' : ''}`} onClick={() => setOpen(o => !o)}>
        <span className="expand-arrow">
          <Icon name="chevronRight" size={12} />
        </span>
        {label}
      </button>
      <div className={`expand-body ${open ? 'open' : ''}`}>
        <div className="expand-content">
          <div style={{ marginBottom: '8px', color: 'var(--text-muted)', fontWeight: 600 }}>{agentLabel}</div>
          {content}
        </div>
      </div>
    </div>
  );
}

/**
 * Results — Content-only renderer. Tab selection is driven by parent
 * via the `forcedTab` prop (from DashboardPanel sidebar).
 */
export default function Results({ results, topic, evidenceClaims, sourceProfiles, forcedTab = 'report' }) {
  const [pdfLoading, setPdfLoading] = useState(false);
  const [docxLoading, setDocxLoading] = useState(false);
  const [mdLoading, setMdLoading] = useState(false);
  const [dossierLoading, setDossierLoading] = useState(false);
  const [copySuccess, setCopySuccess] = useState(false);
  const [selectedCycle, setSelectedCycle] = useState(null);

  const activeTab = forcedTab;

  const handleDownloadMarkdown = async () => {
    if (!results.writer) return;
    setMdLoading(true);
    const safeTopic = topic ? topic.replace(/\s+/g, '_') : 'report';
    try {
      const blob = await downloadMarkdown({
        report: results.writer, topic,
        sessionId: results.session_id || results.id,
        claims: evidenceClaims || results.claims,
        sources: sourceProfiles || results.sources,
      });
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = `synapse_${safeTopic}.md`;
      a.click();
    } catch (err) {
      const a = document.createElement('a');
      a.href = URL.createObjectURL(new Blob([results.writer], { type: 'text/markdown' }));
      a.download = `synapse_${safeTopic}.md`;
      a.click();
    } finally {
      setMdLoading(false);
    }
  };

  const handleDownloadPdf = async () => {
    if (!results.writer) return;
    setPdfLoading(true);
    try {
      const blob = await downloadPdf({
        report: results.writer, topic,
        sessionId: results.session_id || results.id,
        claims: evidenceClaims || results.claims,
        sources: sourceProfiles || results.sources,
      });
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = `synapse_${topic ? topic.replace(/\s+/g, '_') : 'report'}.pdf`;
      a.click();
    } catch { alert('PDF download failed.'); }
    finally { setPdfLoading(false); }
  };

  const handleDownloadDocx = async () => {
    if (!results.writer) return;
    setDocxLoading(true);
    try {
      const blob = await downloadDocx({
        report: results.writer, topic,
        sessionId: results.session_id || results.id,
        claims: evidenceClaims || results.claims,
        sources: sourceProfiles || results.sources,
      });
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = `synapse_${topic ? topic.replace(/\s+/g, '_') : 'report'}.docx`;
      a.click();
    } catch { alert('Word (.docx) download failed.'); }
    finally { setDocxLoading(false); }
  };

  const handleExportDossier = async () => {
    setDossierLoading(true);
    try {
      const sessionId = results.session_id || results.id;
      let dossierContent = '';
      if (sessionId) {
        try {
          const d = await fetchSessionDossier(sessionId);
          if (d?.dossier_markdown) dossierContent = d.dossier_markdown;
        } catch {}
      }
      if (!dossierContent) {
        const lines = [
          '# SYNAPSE AI — Research Dossier',
          `**Topic**: ${topic || 'Autonomous Research'}`,
          `**Generated**: ${new Date().toISOString()}`, '', '---',
          '## 1. Executive Research Report', '', results.writer || '*No report text generated.*', '',
          '---', '## 2. Research Plan & Strategy', '', results.planner || '*No plan data available.*', '',
        ];
        if (evidenceClaims && evidenceClaims.totalClaims > 0) {
          lines.push('---', '## 3. Evidence & Grounded Claims Lineage', '');
          const { grounded = [], unsupported = [], insufficient = [] } = evidenceClaims;
          lines.push(`*Summary: ${grounded.length} grounded, ${insufficient.length} insufficient, ${unsupported.length} unsupported.*`, '');
          [...grounded, ...insufficient, ...unsupported].forEach((c, idx) => {
            lines.push(`### Claim ${idx + 1}: ${c.text}`);
            lines.push(`- Status: ${c.status || 'Audited'} | Confidence: ${((c.confidence ?? 0.5) * 100).toFixed(0)}%`);
            if (c.verification_notes) lines.push(`- Notes: ${c.verification_notes}`);
            lines.push('');
          });
        }
        if (sourceProfiles && sourceProfiles.length > 0) {
          lines.push('---', '## 4. Source Quality Registry', '');
          lines.push('| Title | Domain | Type | Freshness | Quality Score |');
          lines.push('|-------|--------|------|-----------|---------------|');
          sourceProfiles.forEach(s => {
            lines.push(`| [${s.title || s.url}](${s.url}) | ${s.domain || '—'} | ${s.source_type || '—'} | ${s.freshness || 'undated'} | ${s.composite_score?.toFixed(2) || '—'} |`);
          });
          lines.push('');
        }
        dossierContent = lines.join('\n');
      }
      const safeTopic = (topic || 'research_session').toLowerCase().replace(/[^a-z0-9_-]/g, '_').slice(0, 40);
      triggerDownload(dossierContent, `synapse_dossier_${safeTopic}.md`, 'text/markdown;charset=utf-8');
    } catch (err) { alert('Failed to export dossier: ' + err.message); }
    finally { setDossierLoading(false); }
  };

  const handleCopyReport = () => {
    if (!results.writer) return;
    navigator.clipboard.writeText(results.writer);
    setCopySuccess(true);
    setTimeout(() => setCopySuccess(false), 2500);
  };

  const hasEvidence = evidenceClaims && evidenceClaims.totalClaims > 0;

  return (
    <div className="results-content">
      {/* REPORT TAB */}
      {activeTab === 'report' && (
        <div>
          {results.writer ? (
            <>
              {/* Cycle selector — visible when multiple cycles exist */}
              {results.reportHistory && results.reportHistory.length > 1 && (
                <div className="cycle-selector">
                  <span className="cycle-label">View Cycle:</span>
                  <button
                    className={`cycle-tab ${!selectedCycle ? 'active' : ''}`}
                    onClick={() => setSelectedCycle(null)}
                  >
                    Final Report
                  </button>
                  {results.reportHistory.map(h => (
                    <button
                      key={h.cycle}
                      className={`cycle-tab ${selectedCycle === h.cycle ? 'active' : ''}`}
                      onClick={() => setSelectedCycle(h.cycle)}
                    >
                      Cycle {h.cycle}
                      <span className="cycle-meta">{h.words_count}w</span>
                    </button>
                  ))}
                </div>
              )}

              <div className="report-card">
                <div className="report-card-header">
                  <div className="report-card-label">
                    <Icon name="writer" size={16} />
                    {selectedCycle
                      ? `Cycle ${selectedCycle} Report`
                      : 'Executive Research Document'}
                  </div>
                  <button className={`copy-btn ${copySuccess ? 'copied' : ''}`} onClick={handleCopyReport}>
                    <Icon name={copySuccess ? 'check' : 'copy'} size={13} />
                    {copySuccess ? 'Copied' : 'Copy'}
                  </button>
                </div>
                <div className="report-body">
                  <div className="md" dangerouslySetInnerHTML={{
                    __html: marked.parse(sanitizeReportMarkdown(
                      selectedCycle
                        ? (results.reportHistory.find(h => h.cycle === selectedCycle)?.report || results.writer)
                        : results.writer
                    ))
                  }} />
                </div>
              </div>

              <div className="export-bar">
                <button className="export-btn pdf" onClick={handleDownloadPdf} disabled={pdfLoading}>
                  <Icon name="download" size={14} />
                  {pdfLoading ? 'Generating…' : 'PDF (.pdf)'}
                </button>
                <button className="export-btn docx" onClick={handleDownloadDocx} disabled={docxLoading}>
                  <Icon name="download" size={14} />
                  {docxLoading ? 'Generating…' : 'Word (.docx)'}
                </button>
                <button className="export-btn md-export" onClick={handleDownloadMarkdown} disabled={mdLoading}>
                  <Icon name="download" size={14} />
                  {mdLoading ? 'Generating…' : 'Markdown (.md)'}
                </button>
                <button className="export-btn dossier" onClick={handleExportDossier} disabled={dossierLoading}>
                  <Icon name="folder" size={14} />
                  {dossierLoading ? 'Compiling…' : 'Full Dossier'}
                </button>
              </div>
            </>
          ) : (
            <div className="tab-pending">
              <div className="tab-pending-icon"><Icon name="writer" size={24} /></div>
              <p>Writer Agent is synthesizing research findings into an executive report…</p>
            </div>
          )}
        </div>
      )}

      {/* EVIDENCE TAB */}
      {activeTab === 'evidence' && (
        <div>
          {hasEvidence ? (
            <EvidencePanel evidenceClaims={evidenceClaims} sourceProfiles={sourceProfiles} />
          ) : (
            <div className="tab-pending">
              <div className="tab-pending-icon"><Icon name="shield" size={24} /></div>
              <p>Evidence claims will appear after the Writer and Verification agents complete their analysis…</p>
            </div>
          )}
        </div>
      )}

      {/* SOURCES TAB */}
      {activeTab === 'sources' && (
        <div>
          {results.search || (results.sourceQualityProfiles && results.sourceQualityProfiles.length > 0) ? (
            <NewsResources
              rawText={results.search}
              sourceProfiles={results.sourceQualityProfiles}
              sourceQualitySummary={results.sourceQualitySummary}
              failedSources={results.failedSources || []}
              degradedModes={results.degradedModes || []}
            />
          ) : (
            <div className="tab-pending">
              <div className="tab-pending-icon"><Icon name="search" size={24} /></div>
              <p>Search Agent is discovering live web sources…</p>
            </div>
          )}
        </div>
      )}

      {/* CRITIC TAB */}
      {activeTab === 'critic' && (
        <div>
          {results.critic ? (
            <div className="review-card">
              <div className="review-card-header">
                <div className="card-label">
                  <Icon name="star" size={16} />
                  Critic Agent Quality Review
                </div>
              </div>
              <div className="review-body">
                <div className="md" dangerouslySetInnerHTML={{ __html: marked.parse(results.critic) }} />
              </div>
            </div>
          ) : (
            <div className="tab-pending">
              <div className="tab-pending-icon"><Icon name="star" size={24} /></div>
              <p>Critic Agent will perform quality review once report is complete…</p>
            </div>
          )}
        </div>
      )}

      {/* TELEMETRY TAB */}
      {activeTab === 'telemetry' && (
        <div className="telemetry-container">
          <AgentTelemetryView results={results} />
          <div className="telemetry-divider"><h4>Raw Diagnostic Payloads</h4></div>
          <ExpandablePanel label="Structured Research Plan (Planner Agent)" agentLabel="Planner Output" content={results.planner} />
          <ExpandablePanel label="Concurrent Subtasks & Evidence Summary" agentLabel="Subtasks Telemetry" content={results.evidence} />
          {results.failedSources && results.failedSources.length > 0 && (
            <ExpandablePanel
              label={`Fault Tolerance: Skipped Sources (${results.failedSources.length})`}
              agentLabel="Transparent Source Failures"
              content={JSON.stringify(results.failedSources, null, 2)}
            />
          )}
          {results.degradedModes && results.degradedModes.length > 0 && (
            <ExpandablePanel
              label={`Degradation Modes (${results.degradedModes.length})`}
              agentLabel="Active Graceful Degradation"
              content={JSON.stringify(results.degradedModes, null, 2)}
            />
          )}
          <ExpandablePanel
            label="Source Quality Profiles"
            agentLabel="Quality Profiles"
            content={results.sourceQualityProfiles?.length > 0 ? JSON.stringify(results.sourceQualityProfiles, null, 2) : null}
          />
          <ExpandablePanel label="Raw Search Output" agentLabel="Search Agent" content={results.search} />
          <ExpandablePanel label="Raw Reader Output" agentLabel="Reader Agent" content={results.reader} />
        </div>
      )}
    </div>
  );
}
