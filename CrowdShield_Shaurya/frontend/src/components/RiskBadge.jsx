/**
 * RiskBadge — shows a risk level pill with colour coding.
 */
import { riskClass, riskColor, riskBg } from '../utils';
import './RiskBadge.css';

export default function RiskBadge({ level = 'LOW', score, pulse = false, size = 'md' }) {
  const cls = riskClass(level);
  return (
    <span
      className={`risk-badge risk-badge--${cls} risk-badge--${size} ${pulse ? 'risk-badge--pulse' : ''}`}
      role="status"
      aria-label={`Risk level: ${level}`}
    >
      {pulse && <span className="risk-badge__dot" style={{ background: riskColor(level) }} />}
      <span className="risk-badge__label">{level}</span>
      {score !== undefined && (
        <span className="risk-badge__score">{Math.round(score)}</span>
      )}
    </span>
  );
}
