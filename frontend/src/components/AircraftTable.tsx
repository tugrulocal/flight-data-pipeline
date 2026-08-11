import type { Aircraft } from "../types";
import {
  formatAltitude,
  formatHeading,
  formatRelativeTime,
  formatSpeed,
} from "../lib/formatters";
import { TakeoffIcon } from "./TakeoffIcon";


interface AircraftTableProps {
  aircraft: Aircraft[];
  selectedIcao24: string | null;
  onSelectAircraft: (icao24: string) => void;
}


export function AircraftTable({
  aircraft,
  selectedIcao24,
  onSelectAircraft,
}: AircraftTableProps) {
  return (
    <div className="aircraft-list" role="list">
      {aircraft.map((item) => {
        const flightState =
          item.on_ground === true
            ? "ground"
            : item.on_ground === false
              ? "air"
              : "unknown";
        const flightStateLabel =
          item.on_ground === true
            ? "Yerde"
            : item.on_ground === false
              ? "Havada"
              : "Bilinmiyor";

        return (
          <button
            key={item.icao24}
            type="button"
            role="listitem"
            className={`aircraft-list-item ${
              selectedIcao24 === item.icao24 ? "selected-row" : ""
            }`}
            onClick={() => onSelectAircraft(item.icao24)}
          >
            <span className="aircraft-list-heading">
              <span className="aircraft-list-identity">
                <TakeoffIcon className="takeoff-icon" />
                <span>
                <strong>{item.callsign || "Çağrı kodu yok"}</strong>
                <small>{item.icao24}</small>
                </span>
              </span>
              <span className={`flight-state ${flightState}`}>
                {flightStateLabel}
              </span>
            </span>
            <span className="aircraft-list-details">
              <span>{formatAltitude(item.baro_altitude_m)}</span>
              <span>{formatSpeed(item.velocity_mps)}</span>
              <span>{formatHeading(item.true_track_deg)}</span>
              <span>{formatRelativeTime(item.observed_at)}</span>
            </span>
          </button>
        );
      })}

      {aircraft.length === 0 && (
        <div className="empty-state">Filtreyle eşleşen uçak bulunamadı.</div>
      )}
    </div>
  );
}
