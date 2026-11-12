import { LEVELS, LEVEL_COLORS, ROUTE_COLORS, fmtDateTime, fmtTime, formatDuration } from "../risk.js";

function LevelBar({ summary }) {
  const parts = [
    summary.low_miles, summary.moderate_miles, summary.high_miles,
    summary.severe_miles, summary.no_travel_miles,
  ];
  const total = parts.reduce((a, b) => a + b, 0) || 1;
  return (
    <div className="levelbar" role="img"
         aria-label={parts.map((m, i) => `${LEVELS[i]} ${m.toFixed(0)} miles`).join(", ")}>
      {parts.map((m, i) =>
        m > 0 ? <span key={i} style={{ width: `${(m / total) * 100}%`, background: LEVEL_COLORS[i] }} /> : null
      )}
    </div>
  );
}

function RouteCard({ route, index, selected, onSelect }) {
  const s = route.summary;
  return (
    <article className={`card route ${selected ? "selected" : ""}`}
             style={{ borderLeftColor: ROUTE_COLORS[index % ROUTE_COLORS.length] }}
             onClick={() => onSelect(route.id)}>
      <header>
        <h3>
          {route.recommended && <span title="Recommended">★ </span>}
          {route.name}
        </h3>
        <div className="tags">
          {route.tags.map((t) => (
            <span key={t} className={`tag ${t === "Recommended" ? "good" : ""}`}>{t}</span>
          ))}
          <span className="chip" style={{ background: LEVEL_COLORS[s.max_level] }}>
            Max: {s.max_level_name}
          </span>
        </div>
      </header>
      <p className="meta">
        {route.distance_mi.toFixed(0)} mi · {formatDuration(route.duration_min)} · arrive {fmtDateTime(route.arrival)}
      </p>
      <LevelBar summary={s} />
      <dl className="stats">
        <div><dt>No Travel</dt><dd>{s.no_travel_miles.toFixed(0)} mi</dd></div>
        <div><dt>Severe</dt><dd>{s.severe_miles.toFixed(0)} mi</dd></div>
        <div><dt>High</dt><dd>{s.high_miles.toFixed(0)} mi</dd></div>
        <div><dt>Avg risk</dt><dd>{s.avg_risk.toFixed(2)}</dd></div>
      </dl>
      {selected && (
        <details open>
          <summary>{route.checkpoints.length} checkpoints (every {route.interval_miles} mi)</summary>
          <div className="tablewrap">
            <table>
              <thead>
                <tr><th>Mile</th><th>ETA</th><th>Wind</th><th>Rain</th><th>Snow</th><th>Risk</th></tr>
              </thead>
              <tbody>
                {route.checkpoints.map((c) => (
                  <tr key={c.mile}>
                    <td>{c.mile.toFixed(0)}</td>
                    <td>{fmtTime(c.eta)}</td>
                    <td>{c.wind_mph}</td>
                    <td>{c.rain_in_hr}</td>
                    <td>{c.snow_in_hr}</td>
                    <td><span className="dot" style={{ background: LEVEL_COLORS[c.level] }} />{c.level_name}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="hint">Wind mph · rain in/hr · snow in/hr at the truck's estimated arrival time.</p>
        </details>
      )}
    </article>
  );
}

export default function RouteCards({ result, selectedId, onSelect }) {
  const { recommendation, routes } = result;
  return (
    <section>
      <div className={`card banner ${recommendation.warnings.length ? "warn" : ""}`}>
        <strong>Recommended: {routes.find((r) => r.id === recommendation.route_id).name}</strong>
        <p>{recommendation.reason}</p>
        {recommendation.warnings.map((w) => <p key={w} className="warning">⚠ {w}</p>)}
      </div>
      {routes.map((r, i) => (
        <RouteCard key={r.id} route={r} index={i} selected={r.id === selectedId} onSelect={onSelect} />
      ))}
    </section>
  );
}
