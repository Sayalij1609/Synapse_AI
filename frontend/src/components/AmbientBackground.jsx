import React from 'react';

/**
 * AmbientBackground
 * High-performance, GPU-accelerated atmospheric background with:
 * - Fluid aurora light waves
 * - Animated grid mesh with subtle depth pulse
 * - Subtle floating starlight motes
 * Automatically adapts across Dark, Night (OLED), and Light themes.
 */
export default function AmbientBackground() {
  return (
    <div className="ambient-background" aria-hidden="true">
      {/* Dynamic Aurora Light Gradients */}
      <div className="ambient-aurora">
        <div className="aurora-beam beam-cobalt" />
        <div className="aurora-beam beam-cyan" />
        <div className="aurora-beam beam-seafoam" />
        <div className="aurora-beam beam-indigo" />
      </div>

      {/* Cyber Grid with Scanning Sweep */}
      <div className="ambient-grid" />
      <div className="ambient-scanline" />

      {/* Floating Starlight Motes */}
      <div className="ambient-motes">
        <span className="mote mote-1" />
        <span className="mote mote-2" />
        <span className="mote mote-3" />
        <span className="mote mote-4" />
        <span className="mote mote-5" />
        <span className="mote mote-6" />
      </div>
    </div>
  );
}
