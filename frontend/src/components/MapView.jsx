import { memo, useEffect, useMemo } from "react";
import { CircleMarker, MapContainer, Polyline, Popup, TileLayer, Tooltip, useMap } from "react-leaflet";
import HeatLayer from "./HeatLayer.jsx";
import {
  LEVEL_COLORS, ROUTE_COLORS, buildHeatPoints, fmtDateTime, fmtTime, formatDuration,
} from "../risk.js";

function FitBounds({ routes }) {
  const map = useMap();
  useEffect(() => {
    if (!routes.length) return;
    const pts = routes.flatMap((r) => r.geometry);
    map.fitBounds(pts, { padding: [40, 40] });
  }, [routes, map]);
  return null;
}

/** Static layer for one route. Memoised so slider moves never re-render it. */
const RouteLayer = memo(function RouteLayer({ route, index, selected, onSelect }) {
  const color = ROUTE_COLORS[index % ROUTE_COLORS.length];
  const s = route.summary;
  return (
    <>
      <Polyline
        positions={route.geometry}
        pathOptions={{
          color, weight: selected ? 7 : 4, opacity: selected ? 0.9 : 0.5,
          dashArray: route.recommended ? null : "8 6",
        }}
        eventHandlers={{ click: () => onSelect(route.id) }}
      >
        <Tooltip sticky>
          <b>{route.name}{route.recommended ? " ★" : ""}</b><br />
          {route.distance_mi.toFixed(0)} mi · {formatDuration(route.duration_min)}<br />
          Arrive {fmtDateTime(route.arrival)}<br />
          Severe {s.severe_miles.toFixed(0)} mi · High {s.high_miles.toFixed(0)} mi
        </Tooltip>
      </Polyline>
      {route.checkpoints.map((c) => (
        <CircleMarker
          key={c.mile}
          center={[c.lat, c.lng]}
          radius={selected ? 7 : 4}
          pathOptions={{
            color: "#fff", weight: selected ? 2 : 1,
            fillColor: LEVEL_COLORS[c.level], fillOpacity: 1,
          }}
          eventHandlers={{ click: () => onSelect(route.id) }}
        >
          <Popup>
            <b>{route.name} · mile {c.mile.toFixed(0)}</b><br />
            ETA {fmtDateTime(c.eta)}<br />
            Risk: <b style={{ color: LEVEL_COLORS[c.level] }}>{c.level_name}</b><br />
            Wind {c.wind_mph} mph (gust {c.gust_mph}) · {c.factors.wind}<br />
            Rain {c.rain_in_hr} in/hr · {c.factors.rain}<br />
            Snow {c.snow_in_hr} in/hr · {c.factors.snow}
          </Popup>
        </CircleMarker>
      ))}
    </>
  );
});

export default function MapView({ result, selectedId, onSelect, showHeat, hour }) {
  const routes = result?.routes || [];
  // Heat points: recomputed per hour from data already in memory (no network).
  const heatPoints = useMemo(
    () => (showHeat && routes.length ? buildHeatPoints(routes, hour) : []),
    [showHeat, routes, hour]
  );
  const first = routes[0];
  const endpoints = first
    ? [
        { label: "Origin", c: first.checkpoints[0] },
        { label: "Destination", c: first.checkpoints[first.checkpoints.length - 1] },
      ]
    : [];

  return (
    <MapContainer center={[39.5, -98.35]} zoom={4} preferCanvas className="map">
      L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
    attribution: '&copy; OpenStreetMap contributors &copy; CARTO',
    subdomains: 'abcd',
    maxZoom: 19
}).addTo(map);
      <FitBounds routes={routes} />
      {showHeat && <HeatLayer points={heatPoints} />}
      {/* Draw the selected route last so it sits on top. */}
      {routes
        .map((r, i) => ({ r, i }))
        .sort((a, b) => (a.r.id === selectedId) - (b.r.id === selectedId))
        .map(({ r, i }) => (
          <RouteLayer key={r.id} route={r} index={i} selected={r.id === selectedId} onSelect={onSelect} />
        ))}
      {endpoints.map(({ label, c }) => (
        <CircleMarker key={label} center={[c.lat, c.lng]} radius={9}
                      pathOptions={{ color: "#111", weight: 3, fillColor: "#fff", fillOpacity: 1 }}>
          <Tooltip permanent direction="top" offset={[0, -8]}>{label}</Tooltip>
        </CircleMarker>
      ))}
    </MapContainer>
  );
}
