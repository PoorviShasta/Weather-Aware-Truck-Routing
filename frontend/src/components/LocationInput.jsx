import { useEffect, useRef, useState } from "react";
import { geocode } from "../api.js";

/** Text box with debounced geocoding suggestions. `value` is {label, lat, lng} | null. */
export default function LocationInput({ id, label, value, onChange }) {
  const [text, setText] = useState(value?.label || "");
  const [options, setOptions] = useState([]);
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const wrapRef = useRef(null);

  useEffect(() => {
    // Skip lookups for an already-selected value or short text.
    if (text.trim().length < 3 || text === value?.label) {
      setOptions([]);
      return;
    }
    const controller = new AbortController();
    const timer = setTimeout(async () => {
      setBusy(true);
      setError("");
      try {
        setOptions(await geocode(text.trim(), controller.signal));
        setOpen(true);
      } catch (e) {
        if (e.name !== "AbortError") setError("Could not look up places.");
      } finally {
        setBusy(false);
      }
    }, 350);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [text, value]);

  useEffect(() => {
    const close = (e) => wrapRef.current && !wrapRef.current.contains(e.target) && setOpen(false);
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, []);

  const choose = (opt) => {
    setText(opt.label);
    setOpen(false);
    onChange(opt);
  };

  return (
    <div className="field" ref={wrapRef}>
      <label htmlFor={id}>{label}</label>
      <input
        id={id}
        value={text}
        autoComplete="off"
        placeholder="Search a city or address"
        onChange={(e) => {
          setText(e.target.value);
          onChange(null); // typing invalidates the previous selection
        }}
        onFocus={() => options.length && setOpen(true)}
      />
      {busy && <span className="hint">Searching…</span>}
      {error && <span className="hint error">{error}</span>}
      {open && options.length > 0 && (
        <ul className="suggestions" role="listbox">
          {options.map((o, i) => (
            <li key={`${o.lat},${o.lng},${i}`} role="option" onMouseDown={() => choose(o)}>
              {o.label}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
