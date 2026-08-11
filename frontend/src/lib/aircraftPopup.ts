import {
  formatAltitude,
  formatDateTime,
  formatHeading,
  formatSpeed,
} from "./formatters";


export interface AircraftPopupData {
  icao24: string;
  callsign: string | null;
  origin_country: string | null;
  baro_altitude_m: number | null;
  velocity_mps: number | null;
  true_track_deg: number | null;
  observed_at: string | null;
}


function escapeHtml(value: string | null | undefined) {
  return (value || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll("\"", "&quot;")
    .replaceAll("'", "&#039;");
}


function popupDateTimeHtml(value: string | null) {
  const formatted = formatDateTime(value);
  const match = formatted.match(/^(.*) (\d{2}:\d{2}:\d{2})$/);

  if (!match) {
    return escapeHtml(formatted);
  }

  return `${escapeHtml(match[1])}<br /><span class="popup-time">${escapeHtml(match[2])}</span>`;
}


export function aircraftPopupHtml(item: AircraftPopupData) {
  const title = escapeHtml(item.callsign || item.icao24);
  const country = escapeHtml(item.origin_country || "Bilinmiyor");
  const observedAt = popupDateTimeHtml(item.observed_at);

  return `
    <div class="aircraft-popup">
      <strong>${title}</strong>
      <span>${country}</span>
      <dl>
        <div>
          <dt>İrtifa</dt>
          <dd>${formatAltitude(item.baro_altitude_m)}</dd>
        </div>
        <div>
          <dt>Hız</dt>
          <dd>${formatSpeed(item.velocity_mps)}</dd>
        </div>
        <div>
          <dt>Yön</dt>
          <dd>${formatHeading(item.true_track_deg)}</dd>
        </div>
        <div class="popup-observed">
          <dt>Son görülme</dt>
          <dd class="popup-observed-at">${observedAt}</dd>
        </div>
      </dl>
    </div>
  `;
}
