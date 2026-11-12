import { useEffect, useRef } from "react";
import { useMap } from "react-leaflet";
import "../leafletGlobal.js"; // must run before leaflet.heat
import "leaflet.heat";
import L from "leaflet";

const GRADIENT = { 0.1: "#2e9e5b", 0.35: "#e6b800", 0.6: "#f28c28", 0.85: "#d62f2f", 1.0: "#6a1b9a" };

/** Thin wrapper: one heat layer is created once, then only its points change. */
export default function HeatLayer({ points }) {
  const map = useMap();
  const layerRef = useRef(null);

  useEffect(() => {
    layerRef.current = L.heatLayer([], {
      radius: 32, blur: 26, max: 1.0, minOpacity: 0.35, maxZoom: 9, gradient: GRADIENT,
    }).addTo(map);
    return () => {
      map.removeLayer(layerRef.current);
      layerRef.current = null;
    };
  }, [map]);

  useEffect(() => {
    layerRef.current?.setLatLngs(points);
  }, [points]);

  return null;
}
