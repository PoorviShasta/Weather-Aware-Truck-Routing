// leaflet.heat expects a global `L`; ES-module Leaflet does not always set one.
import L from "leaflet";

window.L = window.L || L;
export default L;
