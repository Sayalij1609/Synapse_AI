import React, { useState } from 'react';
import { login, register } from '../api';
import Icon from './shared/Icon';

export default function AuthModal({ isOpen, onClose, onAuthSuccess }) {
  const [mode, setMode] = useState('login');
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
      <div className="modal-card auth-modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)' }}>
            <div className="section-icon accent">
              <Icon name="lock" size={18} />
            </div>
            <div>
              <div className="modal-title">
                {mode === 'login' ? 'Welcome Back' : 'Create Account'}
              </div>
              <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)', marginTop: '2px' }}>
                {mode === 'login'
                  ? 'Access your research projects'
                  : 'Start your research workspace'}
              </div>
            </div>
          </div>
          <button className="modal-close" onClick={onClose}>
            <Icon name="x" size={18} />
          </button>
        </div>

        <div className="modal-body">
          <div className="auth-tabs">
            <button
              type="button"
              className={`auth-tab ${mode === 'login' ? 'active' : ''}`}
              onClick={() => switchMode('login')}
            >
              Sign In
            </button>
            <button
              type="button"
              className={`auth-tab ${mode === 'register' ? 'active' : ''}`}
              onClick={() => switchMode('register')}
            >
              Register
            </button>
          </div>

          {errorMsg && <div className="auth-error">{errorMsg}</div>}

          <form onSubmit={handleSubmit} className="auth-form">
            {mode === 'register' && (
              <>
                <div className="auth-field">
                  <label>Full Name</label>
                  <input
                    className="input-field"
                    type="text"
                    placeholder="e.g. Dr. Alex Mercer"
                    value={fullName}
                    onChange={(e) => setFullName(e.target.value)}
                  />
                </div>
                <div className="auth-field">
                  <label>Username (optional)</label>
                  <input
                    className="input-field"
                    type="text"
                    placeholder="e.g. alex_researcher"
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                  />
                </div>
              </>
            )}

            <div className="auth-field">
              <label>Email Address</label>
              <input
                className="input-field"
                type="email"
                required
                autoFocus
                placeholder="analyst@domain.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </div>

            <div className="auth-field">
              <label>Password</label>
              <div style={{ position: 'relative' }}>
                <input
                  className="input-field"
                  type={showPassword ? 'text' : 'password'}
                  required
                  placeholder={mode === 'register' ? 'At least 8 characters' : 'Enter password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  style={{ paddingRight: '60px' }}
                />
                <button
                  type="button"
                  style={{
                    position: 'absolute', right: '10px', top: '50%', transform: 'translateY(-50%)',
                    fontSize: 'var(--text-xs)', fontWeight: 600, color: 'var(--accent)',
                    background: 'none', border: 'none', cursor: 'pointer',
                  }}
                  onClick={() => setShowPassword(!showPassword)}
                  tabIndex="-1"
                >
                  {showPassword ? 'Hide' : 'Show'}
                </button>
              </div>
              {mode === 'register' && (
                <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-faint)', marginTop: '4px' }}>
                  At least 8 characters with mixed case, numbers or symbols.
                </span>
              )}
            </div>

            <button
              type="submit"
              className="btn btn-primary btn-lg auth-submit"
              disabled={loading}
              style={{ width: '100%', marginTop: 'var(--space-2)' }}
            >
              {loading ? (
                <>
                  <span className="spinner sm" style={{ borderTopColor: '#fff' }} />
                  Connecting…
                </>
              ) : mode === 'login' ? (
                <>
                  Sign In <Icon name="arrowRight" size={16} />
                </>
              ) : (
                <>
                  Create Account <Icon name="arrowRight" size={16} />
                </>
              )}
            </button>
          </form>

          <div style={{ textAlign: 'center', marginTop: 'var(--space-4)', fontSize: 'var(--text-sm)', color: 'var(--text-muted)' }}>
            {mode === 'login' ? (
              <span>
                Don't have an account?{' '}
                <button
                  type="button"
                  style={{ background: 'none', border: 'none', color: 'var(--accent)', fontWeight: 600, cursor: 'pointer', fontSize: 'inherit' }}
                  onClick={() => switchMode('register')}
                >
                  Register here
                </button>
              </span>
            ) : (
              <span>
                Already have an account?{' '}
                <button
                  type="button"
                  style={{ background: 'none', border: 'none', color: 'var(--accent)', fontWeight: 600, cursor: 'pointer', fontSize: 'inherit' }}
                  onClick={() => switchMode('login')}
                >
                  Sign In
                </button>
              </span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
