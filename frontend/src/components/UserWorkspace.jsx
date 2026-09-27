import React, { useState, useEffect, useCallback } from 'react';
import {
  fetchProjects,
  createProject,
  deleteProject,
  fetchProjectSessions,
  deleteSession,
  fetchSessionReports,
  fetchSessionDossier,
  triggerDownload,
} from '../api';

export default function UserWorkspace({
  currentUser,
  onOpenAuth,
  onLogout,
  onLaunchResearchInProject,
  onLoadSessionInDashboard,
}) {
  const [projects, setProjects] = useState([]);
  const [selectedProjectId, setSelectedProjectId] = useState(null);
  const [sessions, setSessions] = useState([]);
  const [loadingProjects, setLoadingProjects] = useState(false);
  const [loadingSessions, setLoadingSessions] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');

  // New project modal / inline form state
  const [showNewProject, setShowNewProject] = useState(false);
  const [newTitle, setNewTitle] = useState('');
  const [newDesc, setNewDesc] = useState('');
  const [creatingProject, setCreatingProject] = useState(false);

  // New session launch state
  const [sessionTopic, setSessionTopic] = useState('');

  // Report versions modal state
  const [inspectingSessionId, setInspectingSessionId] = useState(null);
  const [reportVersions, setReportVersions] = useState([]);
  const [loadingReports, setLoadingReports] = useState(false);

  const loadProjects = useCallback(async () => {
    if (!currentUser) return;
    setLoadingProjects(true);
    setErrorMsg('');
    try {
      const data = await fetchProjects();
      setProjects(data || []);
      if (data && data.length > 0 && !selectedProjectId) {
        setSelectedProjectId(data[0].id);
      }
    } catch (err) {
      setErrorMsg(err.message || 'Failed to load projects');
    } finally {
      setLoadingProjects(false);
    }
  }, [currentUser, selectedProjectId]);

  useEffect(() => {
    if (currentUser) {
      loadProjects();
    } else {
      setProjects([]);
      setSelectedProjectId(null);
      setSessions([]);
    }
  }, [currentUser, loadProjects]);

  const loadSessions = useCallback(async (projectId) => {
    if (!projectId) return;
    setLoadingSessions(true);
    try {
      const data = await fetchProjectSessions(projectId);
      setSessions(data || []);
    } catch (err) {
      console.error('Failed to load project sessions:', err);
    } finally {
      setLoadingSessions(false);
    }
  }, []);

  useEffect(() => {
    if (selectedProjectId) {
      loadSessions(selectedProjectId);
    } else {
      setSessions([]);
    }
  }, [selectedProjectId, loadSessions]);

  const handleCreateProject = async (e) => {
    e.preventDefault();
    if (!newTitle.trim()) return;
    setCreatingProject(true);
    try {
      const created = await createProject(newTitle.trim(), newDesc.trim());
      setNewTitle('');
      setNewDesc('');
      setShowNewProject(false);
      await loadProjects();
      setSelectedProjectId(created.id);
    } catch (err) {
      alert(err.message || 'Failed to create project');
    } finally {
      setCreatingProject(false);
    }
  };

  const handleDeleteProject = async (e, projectId) => {
    e.stopPropagation();
    if (!window.confirm('Are you sure you want to delete this project and all its research sessions?')) return;
    try {
      await deleteProject(projectId);
      if (selectedProjectId === projectId) {
        setSelectedProjectId(null);
      }
      await loadProjects();
    } catch (err) {
      alert(err.message || 'Failed to delete project');
    }
  };

  const handleDeleteSession = async (e, sessionId) => {
    e.stopPropagation();
    if (!window.confirm('Delete this research session?')) return;
    try {
      await deleteSession(sessionId);
      if (selectedProjectId) {
        loadSessions(selectedProjectId);
      }
    } catch (err) {
      alert(err.message || 'Failed to delete session');
    }
  };

  const handleLaunchSession = (e) => {
    e.preventDefault();
    if (!sessionTopic.trim() || !selectedProjectId) return;
    const topic = sessionTopic.trim();
    setSessionTopic('');
    onLaunchResearchInProject(topic, selectedProjectId);
  };

  const handleViewReports = async (e, sessionId) => {
    e.stopPropagation();
    setInspectingSessionId(sessionId);
    setLoadingReports(true);
    try {
      const data = await fetchSessionReports(sessionId);
      setReportVersions(data || []);
    } catch (err) {
      alert(err.message || 'Failed to load report versions');
    } finally {
      setLoadingReports(false);
    }
  };

  const [exportingSessionId, setExportingSessionId] = useState(null);

  const handleExportDossier = async (e, session) => {
    e.stopPropagation();
    setExportingSessionId(session.id);
    try {
      const dossier = await fetchSessionDossier(session.id);
      const safeTopic = (session.topic || 'research_session')
        .toLowerCase()
        .replace(/[^a-z0-9_-]/g, '_')
        .slice(0, 40);
      const mdContent = dossier.dossier_markdown || `# SYNAPSE AI — Research Dossier\n**Topic**: ${session.topic}\n\n${dossier.report?.content_markdown || ''}`;
      triggerDownload(mdContent, `synapse_dossier_${safeTopic}.md`, 'text/markdown;charset=utf-8');
    } catch (err) {
      alert(err.message || 'Failed to export session dossier');
    } finally {
      setExportingSessionId(null);
    }
  };

  // If not logged in, render protected view notice
  if (!currentUser) {
    return (
      <div className="workspace-container protected-gate">
        <div className="gate-card">
          <div className="gate-icon">🔒</div>
          <h2>Protected Research Workspace</h2>
          <p>
            SYNAPSE AI isolates your research projects, sessions, sources, reports, and agent
            telemetry. Unauthorized users cannot access your data.
          </p>
          <div className="gate-features">
            <div className="gate-feat-item">
              <span className="feat-check">✓</span> User-specific research projects
            </div>
            <div className="gate-feat-item">
              <span className="feat-check">✓</span> Isolated vector evidence chunks & citations
            </div>
            <div className="gate-feat-item">
              <span className="feat-check">✓</span> Versioned report storage & audit trail
            </div>
            <div className="gate-feat-item">
              <span className="feat-check">✓</span> Deterministic source quality analytics
            </div>
          </div>
          <button className="gate-cta-btn" onClick={onOpenAuth}>
            Sign In / Register to Access Workspace 🚀
          </button>
        </div>
      </div>
    );
  }

  const activeProject = projects.find((p) => p.id === selectedProjectId);

  return (
    <div className="workspace-container">
      {/* Top Profile & Header Bar */}
      <div className="workspace-header-bar">
        <div className="workspace-title-group">
          <h2>
            <span className="workspace-icon">📁</span> Research Workspaces
          </h2>
          <span className="workspace-badge-tag">Multi-Tenant Isolated</span>
        </div>

        <div className="workspace-user-card">
          <div className="user-avatar-circle">
            {(currentUser.full_name || currentUser.email || 'U')[0].toUpperCase()}
          </div>
          <div className="user-info-text">
            <span className="user-display-name">
              {currentUser.full_name || currentUser.username || currentUser.email}
            </span>
            <span className="user-email-text">{currentUser.email}</span>
          </div>
          <button className="workspace-logout-btn" onClick={onLogout} title="Sign Out">
            Sign Out
          </button>
        </div>
      </div>

      {errorMsg && <div className="workspace-error-banner">{errorMsg}</div>}

      <div className="workspace-layout">
        {/* Left Column: Projects List */}
        <aside className="workspace-projects-sidebar">
          <div className="projects-header">
            <h3>Your Projects ({projects.length})</h3>
            <button
              className="add-project-btn"
              onClick={() => setShowNewProject(true)}
              title="Create new project"
            >
              + New
            </button>
          </div>

          {showNewProject && (
            <form onSubmit={handleCreateProject} className="new-project-card-form">
              <h4>Create Research Project</h4>
              <input
                type="text"
                required
                autoFocus
                placeholder="Project title (e.g. Quantum Computing 2026)"
                value={newTitle}
                onChange={(e) => setNewTitle(e.target.value)}
              />
              <textarea
                placeholder="Brief description or research objectives..."
                rows="2"
                value={newDesc}
                onChange={(e) => setNewDesc(e.target.value)}
              />
              <div className="form-actions-row">
                <button
                  type="button"
                  className="btn-cancel"
                  onClick={() => setShowNewProject(false)}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="btn-submit"
                  disabled={creatingProject}
                >
                  {creatingProject ? 'Creating...' : 'Create Project'}
                </button>
              </div>
            </form>
          )}

          {loadingProjects && <div className="loading-state">Loading projects...</div>}

          {!loadingProjects && projects.length === 0 && !showNewProject && (
            <div className="empty-projects-state">
              <p>No projects yet.</p>
              <button
                className="btn-create-first"
                onClick={() => setShowNewProject(true)}
              >
                Create your first project
              </button>
            </div>
          )}

          <div className="project-items-list">
            {projects.map((proj) => (
              <div
                key={proj.id}
                className={`project-list-card ${proj.id === selectedProjectId ? 'active' : ''}`}
                onClick={() => setSelectedProjectId(proj.id)}
              >
                <div className="proj-card-top">
                  <h4 className="proj-title">{proj.title}</h4>
                  <button
                    className="proj-delete-btn"
                    onClick={(e) => handleDeleteProject(e, proj.id)}
                    title="Delete project"
                  >
                    🗑️
                  </button>
                </div>
                {proj.description && (
                  <p className="proj-desc-text">{proj.description}</p>
                )}
                <div className="proj-meta-row">
                  <span className="proj-meta-tag">
                    🕒 {new Date(proj.created_at).toLocaleDateString()}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </aside>

        {/* Right Column: Active Project Details & Sessions */}
        <main className="workspace-main-content">
          {activeProject ? (
            <div>
              <div className="project-detail-banner">
                <div className="proj-detail-info">
                  <h3>{activeProject.title}</h3>
                  {activeProject.description && (
                    <p className="proj-banner-desc">{activeProject.description}</p>
                  )}
                  <div className="proj-detail-tags">
                    <span className="detail-tag">ID: {activeProject.id.slice(0, 8)}...</span>
                    <span className="detail-tag">Sessions: {sessions.length}</span>
                    <span className="detail-tag">
                      Created: {new Date(activeProject.created_at).toLocaleDateString()}
                    </span>
                  </div>
                </div>

                {/* Quick Launch form bound to this project */}
                <form onSubmit={handleLaunchSession} className="project-quick-launch-form">
                  <div className="launch-input-wrapper">
                    <input
                      type="text"
                      required
                      placeholder="Start autonomous research inside this project..."
                      value={sessionTopic}
                      onChange={(e) => setSessionTopic(e.target.value)}
                    />
                    <button type="submit" className="launch-in-proj-btn">
                      Research 🚀
                    </button>
                  </div>
                </form>
              </div>

              {/* Sessions Table / List */}
              <div className="project-sessions-section">
                <div className="sessions-header-row">
                  <h4>Research Sessions ({sessions.length})</h4>
                  <button
                    className="refresh-sessions-btn"
                    onClick={() => loadSessions(activeProject.id)}
                  >
                    ↻ Refresh
                  </button>
                </div>

                {loadingSessions && (
                  <div className="loading-state">Loading sessions...</div>
                )}

                {!loadingSessions && sessions.length === 0 && (
                  <div className="empty-sessions-notice">
                    <div className="empty-icon">🔬</div>
                    <p>No research sessions recorded in this project yet.</p>
                    <p className="subtext">
                      Type a topic above to initiate autonomous multi-agent research.
                    </p>
                  </div>
                )}

                {!loadingSessions && sessions.length > 0 && (
                  <div className="sessions-table-container">
                    <table className="sessions-table">
                      <thead>
                        <tr>
                          <th>Topic / Name</th>
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
                              <div className="session-topic-cell">
                                <span className="topic-text">{s.topic}</span>
                                {s.session_name && (
                                  <span className="session-name-tag">{s.session_name}</span>
                                )}
                              </div>
                            </td>
                            <td>
                              <span className={`status-badge-pill ${s.status?.toLowerCase() || 'pending'}`}>
                                {s.status || 'PENDING'}
                              </span>
                            </td>
                            <td>
                              <span
                                className={`verification-badge-pill ${
                                  s.verification_status === 'PASS'
                                    ? 'pass'
                                    : s.verification_status === 'RESEARCH_REQUIRED'
                                    ? 'fail'
                                    : 'unknown'
                                }`}
                              >
                                {s.verification_status || 'UNVERIFIED'}
                              </span>
                            </td>
                            <td className="date-cell">
                              {s.created_at
                                ? new Date(s.created_at).toLocaleString([], {
                                    month: 'short',
                                    day: 'numeric',
                                    hour: '2-digit',
                                    minute: '2-digit',
                                  })
                                : '—'}
                            </td>
                            <td>
                              <div className="session-action-btns">
                                <button
                                  className="action-btn-view"
                                  onClick={() => onLoadSessionInDashboard(s.id)}
                                  title="View Full Report & Evidence"
                                >
                                  View
                                </button>
                                <button
                                  className="action-btn-versions"
                                  onClick={(e) => handleViewReports(e, s.id)}
                                  title="View Report Versions"
                                >
                                  Versions
                                </button>
                                <button
                                  className="action-btn-dossier"
                                  onClick={(e) => handleExportDossier(e, s)}
                                  disabled={exportingSessionId === s.id}
                                  title="Export Comprehensive Research Dossier (.md)"
                                >
                                  {exportingSessionId === s.id ? '…' : 'Dossier 📥'}
                                </button>
                                <button
                                  className="action-btn-del"
                                  onClick={(e) => handleDeleteSession(e, s.id)}
                                  title="Delete Session"
                                >
                                  ✕
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
            </div>
          ) : (
            <div className="no-project-selected">
              <h3>Select or create a research project on the left.</h3>
              <p>Your research sessions, sources, and reports are saved per project.</p>
            </div>
          )}
        </main>
      </div>

      {/* Report Versions Modal */}
      {inspectingSessionId && (
        <div className="modal-overlay" onClick={() => setInspectingSessionId(null)}>
          <div
            className="modal-container report-versions-modal"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="modal-header">
              <h3>Report Versions for Session {inspectingSessionId.slice(0, 8)}...</h3>
              <button
                className="modal-close-btn"
                onClick={() => setInspectingSessionId(null)}
              >
                ✕
              </button>
            </div>

            <div className="modal-body">
              {loadingReports && <div className="loading-state">Loading versions...</div>}
              {!loadingReports && reportVersions.length === 0 && (
                <p>No report versions archived for this session.</p>
              )}
              {!loadingReports && reportVersions.length > 0 && (
                <div className="report-versions-list">
                  {reportVersions.map((r) => (
                    <div key={r.id} className="report-version-card">
                      <div className="version-header">
                        <span className="version-pill">Version {r.version}</span>
                        <span className="version-date">
                          {new Date(r.created_at).toLocaleString()}
                        </span>
                      </div>
                      <div className="version-stats">
                        <span>Word count: {r.word_count || '—'}</span>
                        <span>Confidence: {(r.confidence_score * 100).toFixed(0)}%</span>
                        <span>Citations: {r.citation_count || 0}</span>
                      </div>
                      {r.feedback && (
                        <div className="version-feedback">
                          <strong>Verification Feedback:</strong>
                          <p>{r.feedback}</p>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
