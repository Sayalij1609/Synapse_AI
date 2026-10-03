import React, { useState, useEffect, useCallback } from 'react';
import {
  fetchProjects, createProject, deleteProject,
  fetchProjectSessions, deleteSession,
  fetchSessionReports, fetchSessionDossier, triggerDownload,
} from '../api';
import Icon from './shared/Icon';
import StatusBadge from './shared/StatusBadge';

export default function UserWorkspace({
  currentUser, onOpenAuth, onLogout,
  onLaunchResearchInProject, onLoadSessionInDashboard,
}) {
  const [projects, setProjects] = useState([]);
  const [selectedProjectId, setSelectedProjectId] = useState(null);
  const [sessions, setSessions] = useState([]);
  const [loadingProjects, setLoadingProjects] = useState(false);
  const [loadingSessions, setLoadingSessions] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');
  const [showNewProject, setShowNewProject] = useState(false);
  const [newTitle, setNewTitle] = useState('');
  const [newDesc, setNewDesc] = useState('');
  const [creatingProject, setCreatingProject] = useState(false);
  const [sessionTopic, setSessionTopic] = useState('');
  const [inspectingSessionId, setInspectingSessionId] = useState(null);
  const [reportVersions, setReportVersions] = useState([]);
  const [loadingReports, setLoadingReports] = useState(false);
  const [exportingSessionId, setExportingSessionId] = useState(null);

  const loadProjects = useCallback(async () => {
    if (!currentUser) return;
    setLoadingProjects(true);
    setErrorMsg('');
    try {
      const data = await fetchProjects();
      setProjects(data || []);
      if (data?.length > 0 && !selectedProjectId) setSelectedProjectId(data[0].id);
    } catch (err) { setErrorMsg(err.message || 'Failed to load projects'); }
    finally { setLoadingProjects(false); }
  }, [currentUser, selectedProjectId]);

  useEffect(() => {
    if (currentUser) loadProjects();
    else { setProjects([]); setSelectedProjectId(null); setSessions([]); }
  }, [currentUser, loadProjects]);

  const loadSessions = useCallback(async (pid) => {
    if (!pid) return;
    setLoadingSessions(true);
    try { setSessions(await fetchProjectSessions(pid) || []); }
    catch { /* no-op */ }
    finally { setLoadingSessions(false); }
  }, []);

  useEffect(() => {
    if (selectedProjectId) loadSessions(selectedProjectId);
    else setSessions([]);
  }, [selectedProjectId, loadSessions]);

  const handleCreateProject = async (e) => {
    e.preventDefault();
    if (!newTitle.trim()) return;
    setCreatingProject(true);
    try {
      const created = await createProject(newTitle.trim(), newDesc.trim());
      setNewTitle(''); setNewDesc(''); setShowNewProject(false);
      await loadProjects();
      setSelectedProjectId(created.id);
    } catch (err) { alert(err.message); }
    finally { setCreatingProject(false); }
  };

  const handleDeleteProject = async (e, pid) => {
    e.stopPropagation();
    if (!window.confirm('Delete this project and all sessions?')) return;
    try { await deleteProject(pid); if (selectedProjectId === pid) setSelectedProjectId(null); await loadProjects(); }
    catch (err) { alert(err.message); }
  };

  const handleDeleteSession = async (e, sid) => {
    e.stopPropagation();
    if (!window.confirm('Delete this research session?')) return;
    try { await deleteSession(sid); if (selectedProjectId) loadSessions(selectedProjectId); }
    catch (err) { alert(err.message); }
  };

  const handleLaunchSession = (e) => {
    e.preventDefault();
    if (!sessionTopic.trim() || !selectedProjectId) return;
    const topic = sessionTopic.trim();
    setSessionTopic('');
    onLaunchResearchInProject(topic, selectedProjectId);
  };

  const handleViewReports = async (e, sid) => {
    e.stopPropagation();
    setInspectingSessionId(sid);
    setLoadingReports(true);
    try { setReportVersions(await fetchSessionReports(sid) || []); }
    catch (err) { alert(err.message); }
    finally { setLoadingReports(false); }
  };

  const handleExportDossier = async (e, session) => {
    e.stopPropagation();
    setExportingSessionId(session.id);
    try {
      const dossier = await fetchSessionDossier(session.id);
      const safeTopic = (session.topic || 'research_session').toLowerCase().replace(/[^a-z0-9_-]/g, '_').slice(0, 40);
      const mdContent = dossier.dossier_markdown || `# SYNAPSE AI — Research Dossier\n**Topic**: ${session.topic}\n\n${dossier.report?.content_markdown || ''}`;
      triggerDownload(mdContent, `synapse_dossier_${safeTopic}.md`, 'text/markdown;charset=utf-8');
    } catch (err) { alert(err.message); }
    finally { setExportingSessionId(null); }
  };

  // Protected gate
  if (!currentUser) {
    return (
      <div className="workspace-gate">
        <div className="gate-card">
          <div className="section-icon accent" style={{ width: 56, height: 56, borderRadius: 'var(--radius-lg)', fontSize: '1.4rem', margin: '0 auto var(--space-5)' }}>
            <Icon name="lock" size={24} />
          </div>
          <h2 style={{ textAlign: 'center', marginBottom: 'var(--space-3)', fontSize: 'var(--text-2xl)', fontWeight: 800 }}>
            Protected Workspace
          </h2>
          <p style={{ textAlign: 'center', color: 'var(--text-muted)', marginBottom: 'var(--space-6)', maxWidth: 360, margin: '0 auto var(--space-6)' }}>
            Sign in to access isolated research projects, versioned reports, and private source evidence.
          </p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-2)', marginBottom: 'var(--space-6)', padding: '0 var(--space-4)' }}>
            {['User-specific research projects', 'Isolated vector evidence & citations', 'Versioned report storage & audit trail', 'Deterministic source quality analytics'].map(f => (
              <div key={f} style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)', fontSize: 'var(--text-sm)', color: 'var(--text-secondary)' }}>
                <Icon name="check" size={14} style={{ color: 'var(--accent)' }} /> {f}
              </div>
            ))}
          </div>
          <button className="btn btn-primary btn-lg" onClick={onOpenAuth} style={{ width: '100%' }}>
            Sign In / Register <Icon name="arrowRight" size={16} />
          </button>
        </div>
      </div>
    );
  }

  const activeProject = projects.find((p) => p.id === selectedProjectId);

  return (
    <div className="workspace-view">
      {/* Header */}
      <div className="workspace-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)' }}>
          <div className="section-icon amber"><Icon name="folder" size={18} /></div>
          <div>
            <div style={{ fontWeight: 700, fontSize: 'var(--text-lg)' }}>Research Workspace</div>
            <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>Multi-Tenant Isolated</div>
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
            <div style={{ width: 32, height: 32, borderRadius: 'var(--radius-full)', background: 'var(--gradient-primary)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 700, fontSize: 'var(--text-sm)', color: '#fff' }}>
              {(currentUser.full_name || currentUser.email || 'U')[0].toUpperCase()}
            </div>
            <div>
              <div style={{ fontSize: 'var(--text-sm)', fontWeight: 600 }}>{currentUser.full_name || currentUser.username || currentUser.email}</div>
              <div style={{ fontSize: '11px', color: 'var(--text-faint)' }}>{currentUser.email}</div>
            </div>
          </div>
          <button className="btn btn-ghost btn-sm" onClick={onLogout}>Sign Out</button>
        </div>
      </div>

      {errorMsg && <div className="err" style={{ margin: 'var(--space-4) 0' }}>{errorMsg}</div>}

      <div className="workspace-layout">
        {/* Left sidebar */}
        <aside className="workspace-sidebar">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 'var(--space-4)' }}>
            <h3 style={{ fontSize: 'var(--text-sm)', fontWeight: 700, color: 'var(--text-secondary)' }}>Projects ({projects.length})</h3>
            <button className="btn btn-primary btn-sm" onClick={() => setShowNewProject(true)}>
              + New
            </button>
          </div>

          {showNewProject && (
            <form onSubmit={handleCreateProject} style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-active)', borderRadius: 'var(--radius-md)', padding: 'var(--space-4)', marginBottom: 'var(--space-4)' }}>
              <input className="input-field" type="text" required autoFocus placeholder="Project title" value={newTitle} onChange={(e) => setNewTitle(e.target.value)} style={{ marginBottom: 'var(--space-2)' }} />
              <textarea className="input-field" placeholder="Description…" rows="2" value={newDesc} onChange={(e) => setNewDesc(e.target.value)} style={{ marginBottom: 'var(--space-3)', resize: 'vertical' }} />
              <div style={{ display: 'flex', gap: 'var(--space-2)' }}>
                <button type="button" className="btn btn-ghost btn-sm" onClick={() => setShowNewProject(false)}>Cancel</button>
                <button type="submit" className="btn btn-primary btn-sm" disabled={creatingProject}>
                  {creatingProject ? 'Creating…' : 'Create'}
                </button>
              </div>
            </form>
          )}

          {loadingProjects && <div style={{ fontSize: 'var(--text-sm)', color: 'var(--text-muted)', padding: 'var(--space-4)' }}>Loading…</div>}

          {!loadingProjects && projects.length === 0 && !showNewProject && (
            <div style={{ textAlign: 'center', padding: 'var(--space-8) var(--space-4)', color: 'var(--text-faint)' }}>
              <Icon name="folder" size={24} style={{ marginBottom: 'var(--space-3)', opacity: 0.4 }} />
              <p style={{ fontSize: 'var(--text-sm)', marginBottom: 'var(--space-3)' }}>No projects yet</p>
              <button className="btn btn-secondary btn-sm" onClick={() => setShowNewProject(true)}>Create First Project</button>
            </div>
          )}

          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-2)' }}>
            {projects.map((proj) => (
              <div
                key={proj.id}
                className={`ws-project-item ${proj.id === selectedProjectId ? 'active' : ''}`}
                onClick={() => setSelectedProjectId(proj.id)}
              >
                <div style={{ flex: 1 }}>
                  <div style={{ fontWeight: 600, fontSize: 'var(--text-sm)', marginBottom: '2px' }}>{proj.title}</div>
                  {proj.description && (
                    <div style={{ fontSize: '11px', color: 'var(--text-faint)', lineHeight: 1.4, display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>
                      {proj.description}
                    </div>
                  )}
                  <div style={{ fontSize: '10px', color: 'var(--text-faint)', marginTop: '4px' }}>
                    {new Date(proj.created_at).toLocaleDateString()}
                  </div>
                </div>
                <button className="btn btn-ghost btn-icon" onClick={(e) => handleDeleteProject(e, proj.id)} title="Delete" style={{ color: 'var(--text-faint)', flexShrink: 0 }}>
                  <Icon name="x" size={12} />
                </button>
              </div>
            ))}
          </div>
        </aside>

        {/* Main content */}
        <main className="workspace-main">
          {activeProject ? (
            <div>
              {/* Project banner */}
              <div style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius-lg)', padding: 'var(--space-6)', marginBottom: 'var(--space-6)' }}>
                <h3 style={{ fontSize: 'var(--text-xl)', fontWeight: 700, marginBottom: 'var(--space-2)' }}>{activeProject.title}</h3>
                {activeProject.description && (
                  <p style={{ fontSize: 'var(--text-sm)', color: 'var(--text-muted)', marginBottom: 'var(--space-4)' }}>{activeProject.description}</p>
                )}
                <div style={{ display: 'flex', gap: 'var(--space-2)', marginBottom: 'var(--space-5)' }}>
                  <span className="chip mono">{activeProject.id.slice(0, 8)}…</span>
                  <span className="chip cyan">{sessions.length} sessions</span>
                  <span className="chip">{new Date(activeProject.created_at).toLocaleDateString()}</span>
                </div>

                {/* Quick launch */}
                <form onSubmit={handleLaunchSession}>
                  <div className="search-input-wrap">
                    <Icon name="bolt" size={16} />
                    <input className="search-input" type="text" required placeholder="Start research in this project…" value={sessionTopic} onChange={(e) => setSessionTopic(e.target.value)} />
                    <button type="submit" className="search-run-btn" style={{ padding: 'var(--space-2) var(--space-4)' }}>
                      Research <Icon name="arrowRight" size={14} />
                    </button>
                  </div>
                </form>
              </div>

              {/* Sessions */}
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 'var(--space-4)' }}>
                <h4 style={{ fontSize: 'var(--text-base)', fontWeight: 700 }}>Sessions ({sessions.length})</h4>
                <button className="btn btn-ghost btn-sm" onClick={() => loadSessions(activeProject.id)}>
                  <Icon name="refresh" size={12} /> Refresh
                </button>
              </div>

              {loadingSessions && <div style={{ color: 'var(--text-muted)', fontSize: 'var(--text-sm)', padding: 'var(--space-6)' }}>Loading sessions…</div>}

              {!loadingSessions && sessions.length === 0 && (
                <div style={{ textAlign: 'center', padding: 'var(--space-10)', color: 'var(--text-faint)' }}>
                  <Icon name="beaker" size={28} style={{ marginBottom: 'var(--space-3)', opacity: 0.4 }} />
                  <p style={{ fontSize: 'var(--text-sm)' }}>No sessions yet. Start research above.</p>
                </div>
              )}

              {!loadingSessions && sessions.length > 0 && (
                <div className="sessions-table-wrap">
                  <table className="ws-table">
                    <thead>
                      <tr>
                        <th>Topic</th>
                        <th>Status</th>
                        <th>Verification</th>
                        <th>Date</th>
                        <th>Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {sessions.map((s) => (
                        <tr key={s.id}>
                          <td>
                            <div style={{ fontWeight: 600, fontSize: 'var(--text-sm)' }}>{s.topic}</div>
                            {s.session_name && <div style={{ fontSize: '10px', color: 'var(--text-faint)' }}>{s.session_name}</div>}
                          </td>
                          <td><StatusBadge status={s.status?.toLowerCase() || 'pending'} showDot /></td>
                          <td>
                            <span className={`status-badge ${s.verification_status === 'PASS' ? 'completed' : s.verification_status === 'RESEARCH_REQUIRED' ? 'failed' : 'idle'}`}>
                              {s.verification_status || 'UNVERIFIED'}
                            </span>
                          </td>
                          <td style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>
                            {s.created_at ? new Date(s.created_at).toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : '—'}
                          </td>
                          <td>
                            <div style={{ display: 'flex', gap: 'var(--space-1)' }}>
                              <button className="btn btn-ghost btn-sm" onClick={() => onLoadSessionInDashboard(s.id)}>View</button>
                              <button className="btn btn-ghost btn-sm" onClick={(e) => handleViewReports(e, s.id)}>Versions</button>
                              <button className="btn btn-ghost btn-sm" onClick={(e) => handleExportDossier(e, s)} disabled={exportingSessionId === s.id}>
                                {exportingSessionId === s.id ? '…' : 'Dossier'}
                              </button>
                              <button className="btn btn-ghost btn-icon" onClick={(e) => handleDeleteSession(e, s.id)} style={{ color: 'var(--danger)' }}>
                                <Icon name="x" size={12} />
                              </button>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          ) : (
            <div style={{ textAlign: 'center', padding: 'var(--space-20)', color: 'var(--text-faint)' }}>
              <Icon name="folder" size={36} style={{ marginBottom: 'var(--space-4)', opacity: 0.3 }} />
              <h3 style={{ fontSize: 'var(--text-lg)', fontWeight: 600, marginBottom: 'var(--space-2)' }}>Select a Project</h3>
              <p style={{ fontSize: 'var(--text-sm)' }}>Choose or create a project on the left to view sessions.</p>
            </div>
          )}
        </main>
      </div>

      {/* Report Versions Modal */}
      {inspectingSessionId && (
        <div className="modal-overlay" onClick={() => setInspectingSessionId(null)}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()} style={{ maxWidth: 560 }}>
            <div className="modal-header">
              <div className="modal-title">Report Versions</div>
              <button className="modal-close" onClick={() => setInspectingSessionId(null)}><Icon name="x" size={18} /></button>
            </div>
            <div className="modal-body">
              {loadingReports && <div style={{ color: 'var(--text-muted)', fontSize: 'var(--text-sm)' }}>Loading…</div>}
              {!loadingReports && reportVersions.length === 0 && <p style={{ color: 'var(--text-muted)', fontSize: 'var(--text-sm)' }}>No versions archived.</p>}
              {!loadingReports && reportVersions.map((r) => (
                <div key={r.id} style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius-md)', padding: 'var(--space-4)', marginBottom: 'var(--space-3)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--space-2)' }}>
                    <span className="chip accent" style={{ fontWeight: 700 }}>Version {r.version}</span>
                    <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>{new Date(r.created_at).toLocaleString()}</span>
                  </div>
                  <div style={{ display: 'flex', gap: 'var(--space-3)', fontSize: 'var(--text-xs)', color: 'var(--text-secondary)' }}>
                    <span>Words: {r.word_count || '—'}</span>
                    <span>Confidence: {(r.confidence_score * 100).toFixed(0)}%</span>
                    <span>Citations: {r.citation_count || 0}</span>
                  </div>
                  {r.feedback && (
                    <div style={{ marginTop: 'var(--space-3)', fontSize: 'var(--text-xs)', color: 'var(--text-muted)', fontStyle: 'italic', lineHeight: 1.5 }}>
                      {r.feedback}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
