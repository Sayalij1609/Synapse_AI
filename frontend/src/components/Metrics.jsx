import Icon from './shared/Icon';

export default function Metrics({ metrics }) {
  if (!metrics) return null;

  return (
    <div className="metrics-dock">
      <div className="metric-tile">
        <div className="metric-icon sources">
          <Icon name="globe" size={18} />
        </div>
        <div>
          <div className="metric-value">{metrics.sources}</div>
          <div className="metric-label">Verified Sources</div>
        </div>
      </div>

      <div className="metric-tile">
        <div className="metric-icon words">
          <Icon name="document" size={18} />
        </div>
        <div>
          <div className="metric-value">{metrics.words}</div>
          <div className="metric-label">Report Words</div>
        </div>
      </div>

      <div className="metric-tile">
        <div className="metric-icon time">
          <Icon name="clock" size={18} />
        </div>
        <div>
          <div className="metric-value">{metrics.duration}</div>
          <div className="metric-label">Elapsed Time</div>
        </div>
      </div>

      <div className="metric-tile">
        <div className="metric-icon score">
          <Icon name="star" size={18} />
        </div>
        <div>
          <div className="metric-value">{metrics.score}</div>
          <div className="metric-label">QA Score</div>
        </div>
      </div>
    </div>
  );
}
