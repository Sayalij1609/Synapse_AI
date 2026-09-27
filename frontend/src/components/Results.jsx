import { useState } from 'react';
import { marked } from 'marked';
import { downloadPdf, downloadDocx, downloadMarkdown, fetchSessionDossier, triggerDownload } from '../api';
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

  // Strip raw JSON blocks that leaked into report text
  text = text.replace(/^\s*\{[\s\S]*?"summary"\s*:/m, '');
  text = text.replace(/"claims"\s*:\s*\[[\s\S]*?\]\s*\}/m, '');

  // Remove lines with >50% non-printable characters (binary corruption)
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
    <div className="result-block">
      <button
        className={`expand-btn${open ? ' open' : ''}`}
        onClick={() => setOpen((o) => !o)}
      >
        <span className="expand-arrow">▶</span> {label}
      </button>
      <div className={`expand-body${open ? ' open' : ''}`}>
        <div className="raw-panel">
          <div className="raw-label">{agentLabel}</div>
          <div className="raw-text">{content}</div>
        </div>
      </div>
    </div>
  );
}

export default function Results({ results, topic, evidenceClaims, sourceProfiles }) {
  const [activeTab, setActiveTab] = useState('report');
  const [pdfLoading, setPdfLoading] = useState(false);
  const [docxLoading, setDocxLoading] = useState(false);
  const [mdLoading, setMdLoading] = useState(false);
  const [dossierLoading, setDossierLoading] = useState(false);
  const [copySuccess, setCopySuccess] = useState(false);

  const hasAny = results.planner || results.search || results.reader || results.writer || results.critic;

  if (!hasAny) return null;

  const handleDownloadMarkdown = async () => {
    if (!results.writer) return;
    setMdLoading(true);
    const safeTopic = topic ? topic.replace(/\s+/g, '_') : 'report';
    try {
      const blob = await downloadMarkdown({
        report: results.writer,
        topic,
        sessionId: results.session_id || results.id,
        claims: evidenceClaims || results.claims,
        sources: sourceProfiles || results.sources,
      });
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = `synapse_${safeTopic}.md`;
      a.click();
    } catch (err) {
      console.warn('Backend markdown export failed, using local raw report fallback', err);
      const a = document.createElement('a');
      a.href = URL.createObjectURL(
        new Blob([results.writer], { type: 'text/markdown' })
      );
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
        report: results.writer,
        topic,
        sessionId: results.session_id || results.id,
        claims: evidenceClaims || results.claims,
        sources: sourceProfiles || results.sources,
      });
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = `synapse_${topic ? topic.replace(/\s+/g, '_') : 'report'}.pdf`;
      a.click();
    } catch {
      alert('PDF download failed.');
    } finally {
      setPdfLoading(false);
    }
  };

  const handleDownloadDocx = async () => {
    if (!results.writer) return;
    setDocxLoading(true);
    try {
      const blob = await downloadDocx({
        report: results.writer,
        topic,
        sessionId: results.session_id || results.id,
        claims: evidenceClaims || results.claims,
        sources: sourceProfiles || results.sources,
      });
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = `synapse_${topic ? topic.replace(/\s+/g, '_') : 'report'}.docx`;
      a.click();
    } catch {
      alert('Word (.docx) download failed.');
    } finally {
      setDocxLoading(false);
    }
  };

  const handleExportDossier = async () => {
    setDossierLoading(true);
    try {
      const sessionId = results.session_id || results.id;
      let dossierContent = '';
      if (sessionId) {
        try {
          const d = await fetchSessionDossier(sessionId);
          if (d?.dossier_markdown) {
            dossierContent = d.dossier_markdown;
          }
        } catch {
          // fallback to client-compiled dossier
        }
      }

      if (!dossierContent) {
        const lines = [
          '# SYNAPSE AI — Research Dossier',
          `**Topic**: ${topic || 'Autonomous Research'}`,
          `**Generated**: ${new Date().toISOString()}`,
          '',
          '---',
          '## 1. Executive Research Report',
          '',
          results.writer || '*No report text generated.*',
          '',
          '---',
          '## 2. Research Plan & Strategy',
          '',
          results.planner || '*No plan data available.*',
          '',
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
    } catch (err) {
      alert('Failed to export dossier: ' + err.message);
    } finally {
      setDossierLoading(false);
    }
  };

  const handleCopyReport = () => {
    if (!results.writer) return;
    navigator.clipboard.writeText(results.writer);
    setCopySuccess(true);
    setTimeout(() => setCopySuccess(false), 2500);
  };

  const hasEvidence = evidenceClaims && evidenceClaims.totalClaims > 0;

  return (
    <div className="lab-results-hub">
      {/* HUB TAB HEADER */}
      <div className="hub-tab-bar">
        <button
          className={`hub-tab${activeTab === 'report' ? ' active' : ''}`}
          onClick={() => setActiveTab('report')}
        >
          📝 Executive Report
        </button>

        <button
          className={`hub-tab${activeTab === 'evidence' ? ' active' : ''}`}
          onClick={() => setActiveTab('evidence')}
        >
          🔬 Evidence & Claims
          {hasEvidence && (
            <span className="hub-tab-count">{evidenceClaims.totalClaims}</span>
          )}
        </button>

        <button
          className={`hub-tab${activeTab === 'sources' ? ' active' : ''}`}
          onClick={() => setActiveTab('sources')}
        >
          🌐 Web News & Sources
        </button>

        <button
          className={`hub-tab${activeTab === 'critic' ? ' active' : ''}`}
          onClick={() => setActiveTab('critic')}
        >
          ⭐ Quality Audit Review
        </button>

        <button
          className={`hub-tab${activeTab === 'telemetry' ? ' active' : ''}`}
          onClick={() => setActiveTab('telemetry')}
        >
          🛠️ Agent Telemetry
        </button>
      </div>

      {/* TAB PAYLOAD CONTENT */}
      <div className="hub-content-area">
        {/* EXECUTIVE REPORT TAB */}
        {activeTab === 'report' && (
          <div className="report-wrapper">
            {results.writer ? (
              <>
                <div className="report-card">
                  <div className="report-card-header">
                    <div className="card-label purple">📝 Executive Research Document</div>
                    <button
                      className="copy-report-btn"
                      onClick={handleCopyReport}
                      title="Copy report text"
                    >
                      {copySuccess ? '✓ Copied to Clipboard' : '📋 Copy Text'}
                    </button>
                  </div>

                  <div
                    className="md"
                    dangerouslySetInnerHTML={{ __html: marked.parse(sanitizeReportMarkdown(results.writer)) }}
                  />
                </div>

                {/* EXPORT ACTION SUITE */}
                <div className="export-action-bar">
                  <button
                    className="action-btn docx-btn"
                    onClick={handleDownloadDocx}
                    disabled={docxLoading}
                  >
                    📘 {docxLoading ? 'Generating Word…' : 'Download Word (.docx)'}
                  </button>

                  <button
                    className="action-btn pdf-btn"
                    onClick={handleDownloadPdf}
                    disabled={pdfLoading}
                  >
                    📕 {pdfLoading ? 'Generating PDF…' : 'Download PDF (.pdf)'}
                  </button>

                  <button
                    className="action-btn md-btn"
                    onClick={handleDownloadMarkdown}
                    disabled={mdLoading}
                  >
                    📝 {mdLoading ? 'Generating Markdown…' : 'Download Markdown (.md)'}
                  </button>

                  <button
                    className="action-btn dossier-btn"
                    onClick={handleExportDossier}
                    disabled={dossierLoading}
                    title="Export comprehensive research dossier with report, plan, claims lineage, and source quality"
                  >
                    📁 {dossierLoading ? 'Compiling Dossier…' : 'Export Full Dossier (.md)'}
                  </button>
                </div>
              </>
            ) : (
              <div className="tab-pending-state">
                <span className="pending-icon">✍️</span>
                <p>Writer Agent is synthesizing research findings into an executive report...</p>
              </div>
            )}
          </div>
        )}

        {/* EVIDENCE & CLAIMS TAB */}
        {activeTab === 'evidence' && (
          <div>
            {hasEvidence ? (
              <EvidencePanel
                evidenceClaims={evidenceClaims}
                sourceProfiles={sourceProfiles}
              />
            ) : (
              <div className="tab-pending-state">
                <span className="pending-icon">🔬</span>
                <p>Evidence claims will appear after the Writer and Verification agents complete their analysis...</p>
              </div>
            )}
          </div>
        )}

        {/* WEB NEWS & SOURCES TAB */}
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
              <div className="tab-pending-state">
                <span className="pending-icon">🔍</span>
                <p>Search Agent is discovering live web sources...</p>
              </div>
            )}
          </div>
        )}

        {/* CRITIC QUALITY AUDIT TAB */}
        {activeTab === 'critic' && (
          <div>
            {results.critic ? (
              <div className="review-card">
                <div className="card-label green">⭐ Critic Agent Quality Review</div>
                <div
                  className="md"
                  dangerouslySetInnerHTML={{ __html: marked.parse(results.critic) }}
                />
              </div>
            ) : (
              <div className="tab-pending-state">
                <span className="pending-icon">⭐</span>
                <p>Critic Agent will perform quality review once report is complete...</p>
              </div>
            )}
          </div>
        )}

        {/* TELEMETRY LOGS TAB */}
        {activeTab === 'telemetry' && (
          <div className="telemetry-wrapper">
            <AgentTelemetryView results={results} />

            <div className="telemetry-raw-logs-divider">
              <h4>🔍 Raw Diagnostic Payloads & Logs</h4>
            </div>

            <ExpandablePanel
              label="Structured Research Plan (Planner Agent)"
              agentLabel="Research Planner Output"
              content={results.planner}
            />

            <ExpandablePanel
              label="Concurrent Subtasks & Evidence Summary"
              agentLabel="Subtasks Execution Telemetry"
              content={results.evidence}
            />

            {results.failedSources && results.failedSources.length > 0 && (
              <ExpandablePanel
                label={`Fault Tolerance Audit: Skipped Inaccessible Sources (${results.failedSources.length})`}
                agentLabel="Transparent Source Failures (Never Fabricated, Gracefully Handled)"
                content={JSON.stringify(results.failedSources, null, 2)}
              />
            )}

            {results.degradedModes && results.degradedModes.length > 0 && (
              <ExpandablePanel
                label={`Resilience Degradation Modes Active (${results.degradedModes.length})`}
                agentLabel="Active Graceful Degradation Modes"
                content={JSON.stringify(results.degradedModes, null, 2)}
              />
            )}

            <ExpandablePanel
              label="Deterministic Source Quality & Freshness Profiles"
              agentLabel="Source Quality Profiles"
              content={
                results.sourceQualityProfiles && results.sourceQualityProfiles.length > 0
                  ? JSON.stringify(results.sourceQualityProfiles, null, 2)
                  : null
              }
            />

            <ExpandablePanel
              label="Raw Search Agent Output Payload"
              agentLabel="Search Agent Output"
              content={results.search}
            />

            <ExpandablePanel
              label="Raw Reader Agent Scraped Webpage Text"
              agentLabel="Reader Agent Output"
              content={results.reader}
            />
          </div>
        )}
      </div>
    </div>
  );
}
