import React from 'react';

/**
 * GlassCard — Reusable glassmorphic card container.
 * Supports hover glow variants: accent, teal, rose.
 */
export default function GlassCard({
  children,
  className = '',
  glow = '',
  interactive = false,
  padding = true,
  style = {},
  onClick,
  ...props
}) {
  const classes = [
    'glass-card',
    glow && `glow-${glow}`,
    interactive && 'interactive',
    className,
  ].filter(Boolean).join(' ');

  return (
    <div
      className={classes}
      style={padding ? { padding: 'var(--space-6)', ...style } : style}
      onClick={onClick}
      {...props}
    >
      {children}
    </div>
  );
}
