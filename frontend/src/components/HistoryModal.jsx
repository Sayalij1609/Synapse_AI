import React, { useEffect, useState, useCallback, useMemo } from 'react';
import { fetchHistory, deleteHistoryEntry } from '../api';
import Icon from './shared/Icon';

function timeAgo(iso) {
  const diff = (Date.now() - new Date(iso).getTime()) / 1000;
  if (diff < 60) return 'Just now';
  if (diff < 3600) return Math.floor(diff / 60) + 'm ago';
  if (diff < 86400) return Math.floor(diff / 3600) + 'h ago';
  return Math.floor(diff / 86400) + 'd ago';
}

export default function HistoryModal({ isOpen, onClose, onSelectEntry, refreshSignal }) {
  const [history, setHistory] = useState([]);
  const [filterQuery, setFilterQuery] = useState('');

  const loadHistory = useCallback(async () => {
    try {
      const items = await fetchHistory();
      setHistory(items);
    } catch {
      setHistory([]);
    }
  }, []);

  useEffect(() => {
    if (isOpen) loadHistory();
  }, [isOpen, loadHistory, refreshSignal]);

  const filteredHistory = useMemo(() => {
    if (!filterQuery.trim()) return history;
    return history.filter((h) =>
      h.topic.toLowerCase().includes(filterQuery.toLowerCase())
    );
  }, [history, filterQuery]);

  const handleDelete = async (e, id) => {
    e.stopPropagation();
    try {
      await deleteHistoryEntry(id);
      loadHistory();
    } catch (err) {
      console.error('Delete failed:', err);
    }
  };

  if (!isOpen) return null;

  return (
    <>
      <div className="history-drawer-overlay" onClick={onClose} />
      <div className="history-drawer">
        <div className="drawer-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)' }}>
            <div className="section-icon cyan">
              <Icon name="clock" size={18} />
            </div>
            <div>
              <div className="drawer-title">Research History</div>
              <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>
                {history.length} saved entries
              </div>
            </div>
          </div>
          <button className="modal-close" onClick={onClose}>
            <Icon name="x" size={18} />
          </button>
        </div>

        {/* Search */}
        <div style={{ padding: 'var(--space-4)', borderBottom: '1px solid var(--border)' }}>
          <div className="search-input-wrap" style={{ padding: 'var(--space-2) var(--space-3)' }}>
            <Icon name="search" size={15} />
            <input
              type="text"
              className="search-input"
              placeholder="Search past research…"
              value={filterQuery}
              onChange={(e) => setFilterQuery(e.target.value)}
              style={{ fontSize: 'var(--text-sm)', padding: 'var(--space-2) 0' }}
            />
          </div>
        </div>

        {/* List */}
        <div className="drawer-body">
          {filteredHistory.length === 0 ? (
            <div className="history-empty">
              <Icon name="clock" size={32} />
              <p style={{ fontSize: 'var(--text-sm)' }}>
                {filterQuery ? 'No matching queries found.' : 'No research history yet.'}
              </p>
            </div>
          ) : (
            <div className="history-list">
              {filteredHistory.map((h) => (
                <div
                  className="history-item"
                  key={h.id}
                  onClick={() => { onSelectEntry(h.id); onClose(); }}
                >
                  <div style={{ flex: 1 }}>
                    <div className="history-topic">{h.topic}</div>
                    <div className="history-meta">
                      <span className="chip" style={{ fontSize: '10px', padding: '1px 6px' }}>Archived</span>
                      <span>{timeAgo(h.timestamp)}</span>
                    </div>
                  </div>
                  <button
                    className="btn btn-ghost btn-icon"
                    onClick={(e) => handleDelete(e, h.id)}
                    title="Delete"
                    style={{ color: 'var(--text-faint)' }}
                  >
                    <Icon name="x" size={14} />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </>
  );
}
