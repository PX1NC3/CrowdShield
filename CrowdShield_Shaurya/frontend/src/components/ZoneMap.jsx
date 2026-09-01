/**
 * ZoneMap — 3×3 interactive grid showing density/risk per zone.
 */
import { riskColor, riskBg, trendIcon, trendClass } from '../utils';
import './ZoneMap.css';

const ZONE_LABELS = ['Z1','Z2','Z3','Z4','Z5','Z6','Z7','Z8','Z9'];

export default function ZoneMap({ zones, onZoneClick, highlightZone }) {
  if (!zones || zones.length === 0) {
    return (
      <div className="zone-map zone-map--loading">
        {ZONE_LABELS.map(z => (
          <div key={z} className="zone-cell zone-cell--skeleton">
            <span className="skeleton" style={{ width: 28, height: 12, borderRadius: 4 }} />
          </div>
        ))}
      </div>
    );
  }

  return (
    <div className="zone-map" role="grid" aria-label="3×3 zone density map">
      {zones.map((z, i) => {
        const level = z.risk_level || 'LOW';
        const isHighlighted = highlightZone === z.zone;
        return (
          <button
            key={z.zone}
            className={`zone-cell zone-cell--${level.toLowerCase()} ${isHighlighted ? 'zone-cell--active' : ''}`}
            onClick={() => onZoneClick?.(z)}
            aria-label={`Zone ${z.zone}: density ${z.density}, risk ${level}`}
            role="gridcell"
            style={{ '--zone-color': riskColor(level), '--zone-bg': riskBg(level) }}
          >
            <span className="zone-cell__label">{z.zone}</span>
            <span className="zone-cell__density">{z.density ?? 0}</span>
            <span className={`zone-cell__trend ${trendClass(z.trend)}`}>
              {trendIcon(z.trend)}
            </span>
            <div
              className="zone-cell__bar"
              style={{
                height: `${Math.min((z.density ?? 0) / 80 * 100, 100)}%`,
                background: riskColor(level),
              }}
            />
          </button>
        );
      })}
    </div>
  );
}
