import React from 'react';
import Icon from './shared/Icon';

export default function Footer() {
  return (
    <footer className="footer">
      <div className="footer-inner">
        <div className="footer-left">
          <span className="footer-brand">SYNAPSE AI</span>
          <span className="footer-tagline">· Autonomous Research Platform</span>
        </div>
        <div className="footer-tech">
          <span className="tech-chip">React</span>
          <span className="tech-chip">FastAPI</span>
          <span className="tech-chip">LangGraph</span>
          <span className="tech-chip">ChromaDB</span>
          <span className="tech-chip">Multi-Agent AI</span>
        </div>
      </div>
    </footer>
  );
}
