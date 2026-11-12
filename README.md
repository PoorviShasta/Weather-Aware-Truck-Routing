# Weather-Aware Truck Routing

React + Django app that generates 3 driving routes, samples weather at checkpoints
(10 / 25 / 50 mi) at the truck's **estimated arrival time**, scores risk with the
load-aware rules, and recommends the best route. Includes a 0–48 h weather heatmap.

**Live demo:** _<paste hosted URL>_ · **Walkthrough:** _<paste Loom URL>_

## Stack & APIs (no API keys needed)
| Need | Service |
|---|---|
| Routing + alternatives | OSRM public server (`router.project-osrm.org`) |
| Geocoding autocomplete | Photon / OpenStreetMap (`photon.komoot.io`) |
| Hourly weather (wind, rain, snow) | Open-Meteo |
| Map / heatmap | Leaflet + leaflet.heat, OSM tiles |

## Run locally
```bash
# backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
DEBUG=1 python manage.py runserver        # http://localhost:8000

# frontend (new terminal)
cd frontend
npm install
npm run dev                               # http://localhost:5173 (proxies /api to :8000)
```
Tests: `cd backend && python -m unittest discover -s routing/tests -t .`

## How it works
1. **Routes** – OSRM returns up to 3 alternatives. If fewer than 3 distinct ones come back,
   extra routes are generated via detour waypoints beside the main route (near-duplicates are dropped).
   OSRM only has a car profile, so durations are multiplied by `TRUCK_SPEED_FACTOR` (1.12).
2. **Checkpoints** – every 10/25/50 mi (or Auto: ≤150 mi→10, ≤500→25, else 50) plus the destination.
   ETA at each = departure + cumulative driving time (per-segment OSRM durations).
3. **Weather** – one batched Open-Meteo call per ~40 checkpoints (parallel, cached 15 min) for hourly wind,
   rain (rain+showers) and snowfall in mph / in·hr⁻¹. The value used is the hour nearest each ETA.
4. **Risk** (`backend/routing/risk.py`) – per checkpoint = worst of wind, rain, snow. Load rules:
   ≥55 mph → No Travel; 45–54 mph & >30,000 lb → No Travel; 35–44 mph & >40,000 lb → Severe.
   Each checkpoint represents the road halfway to its neighbours, so risk is measured in **miles**.
5. **Recommendation** – lexicographic: fewest Severe miles → fewest High miles → lowest mileage-weighted
   average risk (0–4) → shortest time. The response explains the deciding criterion.
6. **Heatmap** – the API returns the 0–48 h hourly risk for every checkpoint; the slider just picks an index
   client-side, so scrubbing never hits the network.

### Assumptions
- Table edges overlap (e.g. rain 0.25 appears in Moderate and High): Low→Moderate lower edge is inclusive,
  other edges use "greater than"; so exactly 0.25 in/hr is Moderate, >1.00 is No Travel.
- **No Travel miles are ranked before Severe miles** (a closed stretch is worse than a Severe one). If every
  route has some, the UI warns to delay departure.
- Miles and average risk are rounded (0.1 mi / 0.01) before comparing so float noise cannot beat travel time.
- Sustained wind is used for risk; gusts are shown in the popup.
- Forecast window: departure within the next 12 days. Not modelled: hours-of-service, road closures, truck restrictions.

## Deploy (single URL)
Push to GitHub → Render → *New → Blueprint* → pick the repo (uses `render.yaml`).
Django serves the built React app and the API from the same origin.
Alternative split hosting: set `VITE_API_URL` on the frontend host and `CORS_ALLOWED_ORIGINS` on the backend.

## Structure
```
backend/routing/  risk.py (rules+ranking) · planner.py (pipeline) · providers.py (APIs) · geo.py · views.py · tests/
frontend/src/     App · components/{RouteForm,LocationInput,RouteCards,MapView,HeatLayer,ForecastSlider}
```
