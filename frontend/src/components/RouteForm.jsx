import { useState } from "react";
import LocationInput from "./LocationInput.jsx";

function defaultDeparture() {
  const d = new Date(Date.now() + 3600_000);
  d.setMinutes(0, 0, 0);
  d.setMinutes(d.getMinutes() - d.getTimezoneOffset()); // to local for datetime-local
  return d.toISOString().slice(0, 16);
}

export default function RouteForm({ onSubmit, loading }) {
  const [origin, setOrigin] = useState(null);
  const [destination, setDestination] = useState(null);
  const [departure, setDeparture] = useState(defaultDeparture);
  const [load, setLoad] = useState(35000);
  const [interval, setInterval] = useState("auto");
  const [error, setError] = useState("");

  const submit = (e) => {
    e.preventDefault();
    if (!origin || !destination) return setError("Pick origin and destination from the suggestions.");
    if (!departure) return setError("Choose a departure date and time.");
    const lb = Number(load);
    if (!Number.isFinite(lb) || lb < 0 || lb > 80000) return setError("Load must be 0–80,000 lb.");
    setError("");
    onSubmit({
      origin,
      destination,
      departure: new Date(departure).toISOString(),
      load_lb: lb,
      interval_miles: interval === "auto" ? null : Number(interval),
    });
  };

  return (
    <form className="card form" onSubmit={submit}>
      <LocationInput id="origin" label="Origin" value={origin} onChange={setOrigin} />
      <LocationInput id="dest" label="Destination" value={destination} onChange={setDestination} />
      <div className="row">
        <div className="field">
          <label htmlFor="dep">Departure</label>
          <input id="dep" type="datetime-local" value={departure}
                 onChange={(e) => setDeparture(e.target.value)} />
        </div>
        <div className="field">
          <label htmlFor="load">Load (lb)</label>
          <input id="load" type="number" min="0" max="80000" step="500" value={load}
                 onChange={(e) => setLoad(e.target.value)} />
        </div>
      </div>
      <div className="field">
        <label htmlFor="interval">Weather checkpoint every</label>
        <select id="interval" value={interval} onChange={(e) => setInterval(e.target.value)}>
          <option value="auto">Auto (by trip length)</option>
          <option value="10">10 miles</option>
          <option value="25">25 miles</option>
          <option value="50">50 miles</option>
        </select>
      </div>
      {error && <p className="error">{error}</p>}
      <button type="submit" className="primary" disabled={loading}>
        {loading ? "Analysing routes & weather…" : "Find safest route"}
      </button>
    </form>
  );
}
