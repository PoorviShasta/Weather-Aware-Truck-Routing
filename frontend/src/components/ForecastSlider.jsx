import { useEffect, useState } from "react";
import { LEVELS, LEVEL_COLORS, hourLabel } from "../risk.js";

export default function ForecastSlider({ baseIso, maxHour, hour, onChange, show, onToggle }) {
  const [playing, setPlaying] = useState(false);

  useEffect(() => {
    if (!playing) return;
    const t = setInterval(() => onChange((h) => (h >= maxHour ? 0 : h + 1)), 700);
    return () => clearInterval(t);
  }, [playing, maxHour, onChange]);

  return (
    <div className="slider card">
      <div className="slider-top">
        <label className="toggle">
          <input type="checkbox" checked={show} onChange={(e) => onToggle(e.target.checked)} />
          Weather heatmap
        </label>
        <span className="when">+{hour}h · {hourLabel(baseIso, hour)}</span>
        <button type="button" onClick={() => setPlaying((p) => !p)} disabled={!show}
                aria-label={playing ? "Pause animation" : "Play animation"}>
          {playing ? "❚❚" : "▶"}
        </button>
      </div>
      <input type="range" min="0" max={maxHour} step="1" value={hour} disabled={!show}
             aria-label="Forecast hour" onChange={(e) => onChange(Number(e.target.value))} />
      <div className="legend">
        {LEVELS.map((l, i) => (
          <span key={l}><i style={{ background: LEVEL_COLORS[i] }} />{l}</span>
        ))}
      </div>
    </div>
  );
}
