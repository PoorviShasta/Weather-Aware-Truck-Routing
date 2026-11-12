import { useDeferredValue, useState } from "react";
import { planRoutes } from "./api.js";
import RouteForm from "./components/RouteForm.jsx";
import RouteCards from "./components/RouteCards.jsx";
import MapView from "./components/MapView.jsx";
import ForecastSlider from "./components/ForecastSlider.jsx";

export default function App() {
  const [result, setResult] = useState(null);
  const [selectedId, setSelectedId] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [showHeat, setShowHeat] = useState(true);
  const [hour, setHour] = useState(0);
  // Keeps the slider thumb instant; the heat layer catches up without blocking.
  const deferredHour = useDeferredValue(hour);

  const handleSubmit = async (payload) => {
    setLoading(true);
    setError("");
    try {
      const data = await planRoutes(payload);
      setResult(data);
      setSelectedId(data.recommendation.route_id);
      setHour(0);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="layout">
      <aside className="sidebar">
        <h1>Weather-Aware Truck Routing</h1>
        <RouteForm onSubmit={handleSubmit} loading={loading} />
        {error && <div className="card error" role="alert">{error}</div>}
        {result && <RouteCards result={result} selectedId={selectedId} onSelect={setSelectedId} />}
      </aside>
      <main className="mapwrap">
        <MapView result={result} selectedId={selectedId} onSelect={setSelectedId}
                 showHeat={showHeat} hour={deferredHour} />
        {result && (
          <ForecastSlider baseIso={result.heat_base} maxHour={result.heat_hours} hour={hour}
                          onChange={setHour} show={showHeat} onToggle={setShowHeat} />
        )}
        {loading && <div className="overlay">Fetching routes and weather…</div>}
      </main>
    </div>
  );
}
