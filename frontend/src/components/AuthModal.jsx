import React, { useState } from 'react';
import { login, register } from '../api';

export default function AuthModal({ isOpen, onClose, onAuthSuccess }) {
  const [mode, setMode] = useState('login'); // 'login' | 'register'
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [username, setUsername] = useState('');
  const [fullName, setFullName] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');

  if (!isOpen) return null;

  const handleSubmit = async (e) => {
    e.preventDefault();
    setErrorMsg('');

    if (!email.trim() || !password.trim()) {
      setErrorMsg('Please provide both email and password.');
      return;
    }

    if (mode === 'register' && password.length < 8) {
      setErrorMsg('Password must be at least 8 characters long.');
      return;
    }

    setLoading(true);
    try {
      let data;
      if (mode === 'login') {
        data = await login(email.trim(), password);
      } else {
        data = await register(email.trim(), password, username.trim(), fullName.trim());
      }
      setLoading(false);
      onAuthSuccess(data.user);
      onClose();
    } catch (err) {
      setLoading(false);
      setErrorMsg(err.message || 'Authentication error. Please try again.');
    }
  };

  const switchMode = (newMode) => {
    setMode(newMode);
    setErrorMsg('');
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div
        className="modal-container auth-modal"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="modal-header">
          <div className="auth-header-title">
            <span className="auth-icon-badge">🔐</span>
            <div>
              <h3>{mode === 'login' ? 'Welcome Back' : 'Create Your Account'}</h3>
              <p className="auth-subtitle">
                {mode === 'login'
                  ? 'Access your private research projects and reports'
                  : 'Start organizing your private multi-agent research workspaces'}
              </p>
            </div>
          </div>
          <button className="modal-close-btn" onClick={onClose} aria-label="Close">
            ✕
          </button>
        </div>

        <div className="auth-tabs">
          <button
            type="button"
            className={`auth-tab-btn ${mode === 'login' ? 'active' : ''}`}
            onClick={() => switchMode('login')}
          >
            Sign In
          </button>
          <button
            type="button"
            className={`auth-tab-btn ${mode === 'register' ? 'active' : ''}`}
            onClick={() => switchMode('register')}
          >
            Register
          </button>
        </div>

        {errorMsg && <div className="auth-error-banner">{errorMsg}</div>}

        <form onSubmit={handleSubmit} className="auth-form">
          {mode === 'register' && (
            <>
              <div className="auth-input-group">
                <label>Full Name</label>
                <input
                  type="text"
                  placeholder="e.g. Dr. Alex Mercer"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                />
              </div>
              <div className="auth-input-group">
                <label>Username (optional)</label>
                <input
                  type="text"
                  placeholder="e.g. alex_researcher"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                />
              </div>
            </>
          )}

          <div className="auth-input-group">
            <label>Email Address</label>
            <input
              type="email"
              required
              autoFocus
              placeholder="analyst@domain.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>

          <div className="auth-input-group">
            <label>Password</label>
            <div className="password-input-wrapper">
              <input
                type={showPassword ? 'text' : 'password'}
                required
                placeholder={mode === 'register' ? 'At least 8 characters' : 'Enter password'}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
              <button
                type="button"
                className="pwd-toggle-btn"
                onClick={() => setShowPassword(!showPassword)}
                tabIndex="-1"
              >
                {showPassword ? 'Hide' : 'Show'}
              </button>
            </div>
            {mode === 'register' && (
              <span className="auth-hint">
                Must be at least 8 characters (mixed case, numbers or symbols recommended).
              </span>
            )}
          </div>

          <button
            type="submit"
            className="auth-submit-btn"
            disabled={loading}
          >
            {loading ? (
              <span className="spinner-inline">Connecting...</span>
            ) : mode === 'login' ? (
              'Sign In to Workspace 🚀'
            ) : (
              'Create Account 🚀'
            )}
          </button>
        </form>

        <div className="auth-footer-toggle">
          {mode === 'login' ? (
            <p>
              Don't have an account yet?{' '}
              <button
                type="button"
                className="auth-link-btn"
                onClick={() => switchMode('register')}
              >
                Register here
              </button>
            </p>
          ) : (
            <p>
              Already have an account?{' '}
              <button
                type="button"
                className="auth-link-btn"
                onClick={() => switchMode('login')}
              >
                Sign In
              </button>
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
