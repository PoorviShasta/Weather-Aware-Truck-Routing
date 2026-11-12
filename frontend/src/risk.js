export const LEVELS = ["Low", "Moderate", "High", "Severe", "No Travel"];
export const LEVEL_COLORS = ["#2e9e5b", "#e6b800", "#f28c28", "#d62f2f", "#6a1b9a"];
// Heat intensity per level (0..1) fed to the heat layer.
export const LEVEL_HEAT = [0.12, 0.35, 0.6, 0.85, 1.0];
export const ROUTE_COLORS = ["#1565c0", "#00838f", "#5e35b1"];

export function formatDuration(min) {
  const h = Math.floor(min / 60);
  const m = min % 60;
  return h ? `${h}h ${String(m).padStart(2, "0")}m` : `${m}m`;
}

const dateTime = new Intl.DateTimeFormat(undefined, {
  weekday: "short", day: "numeric", month: "short", hour: "numeric", minute: "2-digit",
});
const timeOnly = new Intl.DateTimeFormat(undefined, { hour: "numeric", minute: "2-digit" });

export const fmtDateTime = (iso) => dateTime.format(new Date(iso));
export const fmtTime = (iso) => timeOnly.format(new Date(iso));

export function hourLabel(baseIso, hour) {
  return dateTime.format(new Date(new Date(baseIso).getTime() + hour * 3600_000));
}

/** Heat-layer points [lat, lng, intensity] for forecast hour `hour`.
 *  Adds one interpolated point between neighbouring checkpoints so the
 *  corridor reads as a continuous band instead of dots. */
export function buildHeatPoints(routes, hour) {
  const pts = [];
  for (const route of routes) {
    const cps = route.checkpoints;
    for (let i = 0; i < cps.length; i++) {
      const a = cps[i];
      const ia = LEVEL_HEAT[a.forecast.level[hour]];
      pts.push([a.lat, a.lng, ia]);
      const b = cps[i + 1];
      if (b) {
        const ib = LEVEL_HEAT[b.forecast.level[hour]];
        pts.push([(a.lat + b.lat) / 2, (a.lng + b.lng) / 2, (ia + ib) / 2]);
      }
    }
  }
  return pts;
}
