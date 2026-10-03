import React, { useState, useEffect } from 'react';
import Icon from './shared/Icon';

export default function Topbar({
  currentView,
  onSwitchView,
  onOpenHistory,
  currentUser,
  onOpenAuth,
  onLogout,
}) {
  const [theme, setTheme] = useState(() => {
    return localStorage.getItem('syn-theme') || 'dark';
  });

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('syn-theme', theme);
  }, [theme]);

  const toggleTheme = () => {
    setTheme(prev => prev === 'dark' ? 'light' : 'dark');
  };

  return (
    <header className="topbar">
      <div className="topbar-left">
        <div className="topbar-brand" onClick={() => onSwitchView('home')} title="Return to Home">
          <div className="brand-logo">
            <Icon name="bolt" size={16} strokeWidth={2.5} />
          </div>
          <span className="brand-wordmark">
            SYNAPSE<span className="brand-ai">AI</span>
          </span>
        </div>

        <div className="nav-divider" />

        <nav className="topbar-nav">
          <button
            className={`nav-tab${currentView === 'home' ? ' active' : ''}`}
            onClick={() => onSwitchView('home')}
          >
            <Icon name="home" size={16} /> Overview
          </button>

          <button
            className={`nav-tab${currentView === 'dashboard' ? ' active' : ''}`}
            onClick={() => onSwitchView('dashboard')}
          >
            <Icon name="beaker" size={16} /> Research Lab
          </button>

          <button
            className={`nav-tab${currentView === 'workspace' ? ' active' : ''}`}
            onClick={() => onSwitchView('workspace')}
          >
            <Icon name="folder" size={16} /> Workspace
            {currentUser && <span className="nav-user-dot" />}
          </button>

          <button className="nav-tab" onClick={onOpenHistory}>
            <Icon name="clock" size={16} /> History
          </button>
        </nav>
      </div>

      <div className="topbar-right">
        <div className="engine-status">
          <span className="engine-dot" />
          Engine Active
        </div>

        {/* Theme Toggle */}
        <button
          className="theme-toggle"
          onClick={toggleTheme}
          title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
        >
          <Icon name={theme === 'dark' ? 'sun' : 'moon'} size={16} />
        </button>

        {currentUser ? (
          <div className="topbar-auth-group">
            <button
              className="user-pill"
              onClick={() => onSwitchView('workspace')}
              title={`Logged in as ${currentUser.email}`}
            >
              <span className="user-avatar">
                {(currentUser.full_name || currentUser.username || currentUser.email || 'U')[0].toUpperCase()}
              </span>
              <span className="user-name">
                {currentUser.full_name || currentUser.username || currentUser.email.split('@')[0]}
              </span>
            </button>
            <button className="signout-btn" onClick={onLogout} title="Sign Out">
              Sign Out
            </button>
          </div>
        ) : (
          <div className="topbar-auth-group">
            <button className="signin-btn" onClick={onOpenAuth}>
              <Icon name="lock" size={14} /> Sign In
            </button>
            {currentView === 'home' && (
              <button className="launch-btn" onClick={() => onSwitchView('dashboard')}>
                <Icon name="bolt" size={14} /> Launch Lab
              </button>
            )}
          </div>
        )}
      </div>
    </header>
  );
}
