import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.jsx'

/* ── New modular design system (replaces monolithic App.css) ── */
import './styles/globals.css'
import './styles/components.css'
import './styles/topbar.css'
import './styles/landing.css'
import './styles/dashboard.css'
import './styles/dashboard-panel.css'
import './styles/agents.css'
import './styles/results.css'
import './styles/modals.css'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
