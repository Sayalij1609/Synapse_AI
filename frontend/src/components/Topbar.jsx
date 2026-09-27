import React from 'react';

export default function Topbar({
  currentView,
  onSwitchView,
  onOpenHistory,
  currentUser,
  onOpenAuth,
  onLogout,
}) {
  return (
    <header className="topbar">
      <div className="topbar-left">
        <div
          className="topbar-brand-title"
          onClick={() => onSwitchView('home')}
          title="Return to Home Overview"
        >
          <div className="brand-logo-badge">⚡</div>
          <span className="brand-name-text">
            SYNAPSE <span className="brand-accent-tag">AI</span>
          </span>
        </div>

        <div className="nav-divider" />

        <nav className="topbar-nav">
          <button
            className={`topbar-nav-tab${currentView === 'home' ? ' active' : ''}`}
            onClick={() => onSwitchView('home')}
          >
            <span className="nav-tab-icon">🏠</span> Overview
          </button>

          <button
            className={`topbar-nav-tab${currentView === 'dashboard' ? ' active' : ''}`}
            onClick={() => onSwitchView('dashboard')}
          >
            <span className="nav-tab-icon">🔬</span> Research Lab
          </button>

          <button
            className={`topbar-nav-tab${currentView === 'workspace' ? ' active' : ''}`}
            onClick={() => onSwitchView('workspace')}
          >
            <span className="nav-tab-icon">📁</span> Workspace
            {currentUser && <span className="nav-user-indicator">●</span>}
          </button>

          <button
            className="topbar-nav-tab"
            onClick={onOpenHistory}
          >
            <span className="nav-tab-icon">📜</span> History
          </button>
        </nav>
      </div>

      <div className="topbar-right">
        <div className="status-pill">
          <span className="status-dot" />
          Autonomous Engine · Active
        </div>

        {currentUser ? (
          <div className="topbar-auth-group">
            <button
              className="topbar-user-pill"
              onClick={() => onSwitchView('workspace')}
              title={`Logged in as ${currentUser.email}`}
            >
              <span className="user-pill-avatar">
                {(currentUser.full_name || currentUser.username || currentUser.email || 'U')[0].toUpperCase()}
              </span>
              <span className="user-pill-name">
                {currentUser.full_name || currentUser.username || currentUser.email.split('@')[0]}
              </span>
            </button>
            <button
              className="topbar-auth-btn signout-btn"
              onClick={onLogout}
              title="Sign Out"
            >
              Sign Out
            </button>
          </div>
        ) : (
          <div className="topbar-auth-group">
            <button
              className="topbar-auth-btn signin-btn"
              onClick={onOpenAuth}
            >
              Sign In 🔐
            </button>
            {currentView === 'home' && (
              <button
                className="topbar-action-btn"
                onClick={() => onSwitchView('dashboard')}
              >
                Launch Lab 🚀
              </button>
            )}
          </div>
        )}
      </div>
    </header>
  );
}
