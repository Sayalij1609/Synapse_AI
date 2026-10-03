import React from 'react';

/**
 * Skeleton — Shimmer loading placeholder.
 * Variants: text, title, circle, card, custom (via width/height props)
 */
export default function Skeleton({ variant = 'text', width, height, count = 1, className = '' }) {
  const items = Array.from({ length: count }, (_, i) => i);

  if (variant === 'card') {
    return (
      <div className={`skeleton skeleton-card ${className}`} style={{ width, height }} />
    );
  }

  if (variant === 'circle') {
    return (
      <div
        className={`skeleton skeleton-circle ${className}`}
        style={{ width: width || 40, height: height || 40 }}
      />
    );
  }

  if (variant === 'title') {
    return (
      <div className={`skeleton skeleton-title ${className}`} style={{ width }} />
    );
  }

  // Default: text lines
  return (
    <div className={className}>
      {items.map((i) => (
        <div
          key={i}
          className="skeleton skeleton-text"
          style={{
            width: i === count - 1 ? (width || '60%') : '100%',
            height,
          }}
        />
      ))}
    </div>
  );
}

/**
 * SkeletonGroup — Renders a realistic loading placeholder for a section.
 */
export function SkeletonGroup({ lines = 4, showTitle = true, className = '' }) {
  return (
    <div className={className} style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
      {showTitle && <Skeleton variant="title" />}
      <Skeleton variant="text" count={lines} />
    </div>
  );
}
