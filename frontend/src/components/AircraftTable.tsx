import type { Aircraft } from "../types";
import {
  formatAltitude,
  formatHeading,
  formatRelativeTime,
  formatSpeed,
} from "../lib/formatters";


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
    <div className="table-scroll">
      <table>
        <thead>
          <tr>
            <th>Uçuş</th>
            <th>Durum</th>
            <th>İrtifa</th>
            <th>Hız</th>
            <th>Yön</th>
            <th>Son sinyal</th>
          </tr>
        </thead>
        <tbody>
          {aircraft.map((item) => (
            <tr
              key={item.icao24}
              className={
                selectedIcao24 === item.icao24
                  ? "selected-row"
                  : undefined
              }
            >
              <td>
                <button
                  type="button"
                  className="aircraft-link"
                  onClick={() => onSelectAircraft(item.icao24)}
                >
                  <strong>{item.callsign || "Çağrı kodu yok"}</strong>
                  <span>{item.icao24}</span>
                </button>
              </td>
              <td>
                <span className={`flight-state ${item.on_ground ? "ground" : "air"}`}>
                  {item.on_ground ? "Yerde" : "Havada"}
                </span>
              </td>
              <td>{formatAltitude(item.baro_altitude_m)}</td>
              <td>{formatSpeed(item.velocity_mps)}</td>
              <td>{formatHeading(item.true_track_deg)}</td>
              <td>{formatRelativeTime(item.observed_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>

      {aircraft.length === 0 && (
        <div className="empty-state">
          Filtreyle eşleşen uçak bulunamadı.
        </div>
      )}
    </div>
  );
}
