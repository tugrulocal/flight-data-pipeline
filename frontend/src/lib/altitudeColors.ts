import type { Aircraft } from "../types";


export const ALTITUDE_LEGEND = [
  {
    key: "ground",
    label: "Yerde",
    color: "#ffb000",
  },
  {
    key: "unknown",
    label: "İrtifa yok",
    color: "#ffffff",
  },
  {
    key: "low",
    label: "0–1.500 m",
    color: "#ff2d55",
  },
  {
    key: "lower-mid",
    label: "1.500–4.500 m",
    color: "#ff7a00",
  },
  {
    key: "mid",
    label: "4.500–9.000 m",
    color: "#00e5ff",
  },
  {
    key: "high",
    label: "9.000–11.500 m",
    color: "#2979ff",
  },
  {
    key: "very-high",
    label: "11.500 m+",
    color: "#d500f9",
  },
] as const;


export function altitudeColor(item: Aircraft) {
  if (item.on_ground) {
    return "#ffb000";
  }

  const altitude = item.baro_altitude_m;

  if (altitude === null || !Number.isFinite(altitude)) {
    return "#ffffff";
  }

  if (altitude < 1_500) {
    return "#ff2d55";
  }

  if (altitude < 4_500) {
    return "#ff7a00";
  }

  if (altitude < 9_000) {
    return "#00e5ff";
  }

  if (altitude < 11_500) {
    return "#2979ff";
  }

  return "#d500f9";
}
