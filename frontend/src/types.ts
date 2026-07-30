export interface Aircraft {
  _id: string;
  icao24: string;
  callsign: string | null;
  origin_country: string | null;
  latitude: number;
  longitude: number;
  baro_altitude_m: number | null;
  geo_altitude_m: number | null;
  on_ground: boolean | null;
  velocity_mps: number | null;
  true_track_deg: number | null;
  vertical_rate_mps: number | null;
  observed_at: string | null;
  ingested_at: string | null;
  source: string;
  kafka_offset: number;
}

export interface AircraftListResponse {
  count: number;
  items: Aircraft[];
}

export interface AircraftHistoryResponse {
  icao24: string;
  count: number;
  items: Aircraft[];
}

export interface HealthResponse {
  status: "ok" | "degraded";
  components: {
    mongodb: "up" | "down";
    kafka_realtime: "up" | "down";
  };
}

export interface RealtimeMessage {
  type: "connection.ready" | "aircraft.position";
  data?: Aircraft;
}

export type ConnectionStatus =
  | "connecting"
  | "live"
  | "reconnecting"
  | "offline";
