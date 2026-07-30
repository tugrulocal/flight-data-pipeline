import type { Aircraft } from "../types";


const METER_TO_FEET = 3.28084;

export const ALTITUDE_LEGEND = [
  {
    key: "ft-0",
    label: "0",
    color: "#ff7816",
  },
  {
    key: "ft-500",
    label: "500",
    color: "#ff8b18",
  },
  {
    key: "ft-1000",
    label: "1 000",
    color: "#ffa51b",
  },
  {
    key: "ft-2000",
    label: "2 000",
    color: "#ffc21b",
  },
  {
    key: "ft-4000",
    label: "4 000",
    color: "#e3d812",
  },
  {
    key: "ft-6000",
    label: "6 000",
    color: "#b7dc08",
  },
  {
    key: "ft-8000",
    label: "8 000",
    color: "#52d211",
  },
  {
    key: "ft-10000",
    label: "10 000",
    color: "#1fc84a",
  },
  {
    key: "ft-20000",
    label: "20 000",
    color: "#28c7d7",
  },
  {
    key: "ft-30000",
    label: "30 000",
    color: "#3d6dff",
  },
  {
    key: "ft-40000",
    label: "40 000+",
    color: "#d313e7",
  },
  {
    key: "unknown",
    label: "N/A",
    color: "#ffffff",
    hiddenFromScale: true,
  },
] as const;


export function altitudeBucketKey(item: Aircraft) {
  if (item.on_ground) {
    return "ft-0";
  }

  const altitude = item.baro_altitude_m;

  if (altitude === null || !Number.isFinite(altitude)) {
    return "unknown";
  }

  const altitudeFt = altitude * METER_TO_FEET;

  if (altitudeFt < 500) {
    return "ft-0";
  }

  if (altitudeFt < 1_000) {
    return "ft-500";
  }

  if (altitudeFt < 2_000) {
    return "ft-1000";
  }

  if (altitudeFt < 4_000) {
    return "ft-2000";
  }

  if (altitudeFt < 6_000) {
    return "ft-4000";
  }

  if (altitudeFt < 8_000) {
    return "ft-6000";
  }

  if (altitudeFt < 10_000) {
    return "ft-8000";
  }

  if (altitudeFt < 20_000) {
    return "ft-10000";
  }

  if (altitudeFt < 30_000) {
    return "ft-20000";
  }

  if (altitudeFt < 40_000) {
    return "ft-30000";
  }

  return "ft-40000";
}


export function altitudeColor(item: Aircraft) {
  const bucket = altitudeBucketKey(item);
  return ALTITUDE_LEGEND.find((entry) => entry.key === bucket)?.color
    ?? "#ffffff";
}
