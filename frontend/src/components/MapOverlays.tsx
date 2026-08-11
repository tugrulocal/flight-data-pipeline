import type { CSSProperties } from "react";

import type { Aircraft } from "../types";
import { ALTITUDE_LEGEND } from "../lib/altitudeColors";


export type RouteStatus =
  | "idle"
  | "loading"
  | "ready"
  | "empty"
  | "error";


interface RouteStatusOverlayProps {
  selectedAircraft: Aircraft | null;
  selectedRoute: Aircraft[];
  routeStatus: RouteStatus;
}


export function RouteStatusOverlay({
  selectedAircraft,
  selectedRoute,
  routeStatus,
}: RouteStatusOverlayProps) {
  if (!selectedAircraft) {
    return null;
  }

  return (
    <div className={`route-status ${routeStatus}`}>
      <strong>{selectedAircraft.callsign || selectedAircraft.icao24}</strong>
      <span>
        {routeStatus === "loading" && "Rota yükleniyor…"}
        {routeStatus === "ready"
          && `${selectedRoute.length} nokta ile irtifa renkli rota`}
        {routeStatus === "empty" && "Rota için yeterli geçmiş nokta yok"}
        {routeStatus === "error" && "Rota alınamadı"}
        {routeStatus === "idle" && "Uçak seçildi"}
      </span>
    </div>
  );
}


export function AltitudeLegend() {
  return (
    <div
      className="altitude-legend"
      aria-label="İrtifaya göre uçak renkleri"
    >
      <strong>Altitude (ft)</strong>
      <div className="altitude-legend-grid">
        {ALTITUDE_LEGEND
          .filter((item) => !("hiddenFromScale" in item))
          .map((item) => (
            <span key={item.key}>
              <i
                className="legend-swatch"
                style={{ "--legend-color": item.color } as CSSProperties}
              />
              {item.label}
            </span>
          ))}
      </div>
    </div>
  );
}
