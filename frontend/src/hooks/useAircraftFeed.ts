import { useCallback, useEffect, useRef, useState } from "react";

import type {
  Aircraft,
  AircraftListResponse,
  AircraftStatsResponse,
  ConnectionStatus,
  HealthResponse,
  RealtimeMessage,
} from "../types";


const MAX_RECONNECT_DELAY_MS = 15_000;
export const SNAPSHOT_AIRCRAFT_LIMIT = 50_000;
const DEFAULT_LIVE_WINDOW_MINUTES = 20;
const STATS_REFRESH_INTERVAL_MS = 30_000;


export function isRecentlyObserved(
  observedAt: string | null,
  nowMs: number,
  maxAgeMs: number,
) {
  if (!observedAt) {
    return false;
  }

  const observedMs = new Date(observedAt).getTime();
  return Number.isFinite(observedMs) && nowMs - observedMs <= maxAgeMs;
}


function websocketUrl() {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${window.location.host}/ws/aircraft`;
}


function sortAircraft(items: Iterable<Aircraft>) {
  return Array.from(items).sort((left, right) => {
    const leftTime = left.observed_at
      ? new Date(left.observed_at).getTime()
      : 0;
    const rightTime = right.observed_at
      ? new Date(right.observed_at).getTime()
      : 0;

    return rightTime - leftTime;
  });
}


export function isNewerAircraftUpdate(
  current: Aircraft | undefined,
  update: Aircraft,
) {
  if (!current) {
    return true;
  }

  const currentTime = current.observed_at
    ? new Date(current.observed_at).getTime()
    : 0;
  const updateTime = update.observed_at
    ? new Date(update.observed_at).getTime()
    : 0;

  if (updateTime !== currentTime) {
    return updateTime > currentTime;
  }

  return (update.kafka_offset ?? -1) >= (current.kafka_offset ?? -1);
}


export function mergeAircraftUpdate(
  target: Map<string, Aircraft>,
  update: Aircraft,
) {
  if (isNewerAircraftUpdate(target.get(update.icao24), update)) {
    target.set(update.icao24, update);
  }
}


export function useAircraftFeed() {
  const [aircraft, setAircraft] = useState<Aircraft[]>([]);
  const [connectionStatus, setConnectionStatus] =
    useState<ConnectionStatus>("connecting");
  const [backendHealth, setBackendHealth] =
    useState<HealthResponse | null>(null);
  const [lastSnapshotAt, setLastSnapshotAt] = useState<Date | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [liveWindowMinutes, setLiveWindowMinutes] =
    useState(DEFAULT_LIVE_WINDOW_MINUTES);
  const [snapshotTruncated, setSnapshotTruncated] = useState(false);
  const [statistics, setStatistics] =
    useState<AircraftStatsResponse | null>(null);

  const aircraftByIdRef = useRef(new Map<string, Aircraft>());
  const pendingUpdatesRef = useRef(new Map<string, Aircraft>());
  const animationFrameRef = useRef<number | null>(null);
  const websocketRef = useRef<WebSocket | null>(null);
  const reconnectTimerRef = useRef<number | null>(null);
  const reconnectAttemptRef = useRef(0);
  const mountedRef = useRef(false);
  const syncingRef = useRef(false);

  const flushPendingUpdates = useCallback(() => {
    animationFrameRef.current = null;

    if (pendingUpdatesRef.current.size === 0) {
      return;
    }

    const nextAircraft = new Map(aircraftByIdRef.current);

    for (const [icao24, update] of pendingUpdatesRef.current) {
      mergeAircraftUpdate(nextAircraft, update);
    }

    pendingUpdatesRef.current.clear();
    aircraftByIdRef.current = nextAircraft;
    setAircraft(sortAircraft(nextAircraft.values()));
  }, []);

  const scheduleUpdateFlush = useCallback(() => {
    if (
      syncingRef.current
      || animationFrameRef.current !== null
    ) {
      return;
    }

    animationFrameRef.current = window.requestAnimationFrame(
      flushPendingUpdates,
    );
  }, [flushPendingUpdates]);

  const refreshSnapshot = useCallback(async () => {
    if (syncingRef.current) {
      return;
    }

    syncingRef.current = true;

    if (animationFrameRef.current !== null) {
      window.cancelAnimationFrame(animationFrameRef.current);
      animationFrameRef.current = null;
    }

    try {
      const [aircraftResponse, healthResponse, statisticsResponse] = await Promise.all([
        fetch(`/api/aircraft?limit=${SNAPSHOT_AIRCRAFT_LIMIT}`),
        fetch("/health"),
        fetch("/api/stats"),
      ]);

      if (!aircraftResponse.ok) {
        throw new Error(
          `Uçak listesi alınamadı: HTTP ${aircraftResponse.status}`,
        );
      }

      const snapshot =
        await aircraftResponse.json() as AircraftListResponse;
      const nextAircraft = new Map(
        snapshot.items.map((item) => [item.icao24, item]),
      );

      for (const [icao24, update] of pendingUpdatesRef.current) {
        mergeAircraftUpdate(nextAircraft, update);
      }

      pendingUpdatesRef.current.clear();
      aircraftByIdRef.current = nextAircraft;

      if (!mountedRef.current) {
        return;
      }

      setAircraft(sortAircraft(nextAircraft.values()));
      setLastSnapshotAt(new Date());
      setLiveWindowMinutes(
        Number.isFinite(snapshot.window_minutes)
          ? snapshot.window_minutes
          : DEFAULT_LIVE_WINDOW_MINUTES,
      );
      setSnapshotTruncated(Boolean(snapshot.truncated));
      setError(null);

      if (statisticsResponse.ok) {
        setStatistics(
          await statisticsResponse.json() as AircraftStatsResponse,
        );
      }

      if (healthResponse.ok) {
        setBackendHealth(
          await healthResponse.json() as HealthResponse,
        );
      }
    } catch (requestError) {
      if (!mountedRef.current) {
        return;
      }

      setError(
        requestError instanceof Error
          ? requestError.message
          : "REST bağlantısında bilinmeyen hata.",
      );
    } finally {
      syncingRef.current = false;

      if (pendingUpdatesRef.current.size > 0) {
        scheduleUpdateFlush();
      }
    }
  }, [scheduleUpdateFlush]);

  useEffect(() => {
    const refreshStatistics = async () => {
      try {
        const response = await fetch("/api/stats");
        if (response.ok && mountedRef.current) {
          setStatistics(await response.json() as AircraftStatsResponse);
        }
      } catch {
        // Snapshot sırasında alınan son tutarlı sayaç korunur.
      }
    };

    const intervalId = window.setInterval(
      () => void refreshStatistics(),
      STATS_REFRESH_INTERVAL_MS,
    );

    return () => window.clearInterval(intervalId);
  }, []);

  useEffect(() => {
    let disposed = false;

    mountedRef.current = true;
    void refreshSnapshot();

    const connect = () => {
      if (disposed || !mountedRef.current) {
        return;
      }

      setConnectionStatus(
        reconnectAttemptRef.current === 0
          ? "connecting"
          : "reconnecting",
      );

      const websocket = new WebSocket(websocketUrl());
      websocketRef.current = websocket;

      websocket.onopen = () => {
        if (disposed || websocketRef.current !== websocket) {
          return;
        }

        reconnectAttemptRef.current = 0;
        setConnectionStatus("live");
        setError(null);

        // WebSocket açıldıktan sonra snapshot almak aradaki veri
        // boşluğunu kapatır.
        void refreshSnapshot();
      };

      websocket.onmessage = (messageEvent) => {
        if (disposed || websocketRef.current !== websocket) {
          return;
        }

        try {
          const message =
            JSON.parse(messageEvent.data) as RealtimeMessage;

          if (message.type === "aircraft.position") {
            if (!message.data?.icao24) {
              return;
            }

            mergeAircraftUpdate(
              pendingUpdatesRef.current,
              message.data,
            );
            scheduleUpdateFlush();
            return;
          }

          if (message.type === "aircraft.batch") {
            for (const item of message.items ?? []) {
              if (item.icao24) {
                mergeAircraftUpdate(pendingUpdatesRef.current, item);
              }
            }

            scheduleUpdateFlush();
          }
        } catch {
          setError("WebSocket mesajı okunamadı.");
        }
      };

      websocket.onerror = () => {
        if (!disposed) {
          websocket.close();
        }
      };

      websocket.onclose = () => {
        if (
          disposed
          || !mountedRef.current
          || websocketRef.current !== websocket
        ) {
          return;
        }

        setConnectionStatus("reconnecting");

        const delay = Math.min(
          1000 * 2 ** reconnectAttemptRef.current,
          MAX_RECONNECT_DELAY_MS,
        );

        reconnectAttemptRef.current += 1;
        reconnectTimerRef.current = window.setTimeout(
          connect,
          delay,
        );
      };
    };

    connect();

    return () => {
      disposed = true;
      mountedRef.current = false;
      setConnectionStatus("offline");

      if (animationFrameRef.current !== null) {
        window.cancelAnimationFrame(animationFrameRef.current);
      }

      if (reconnectTimerRef.current !== null) {
        window.clearTimeout(reconnectTimerRef.current);
      }

      websocketRef.current?.close();
    };
  }, [refreshSnapshot, scheduleUpdateFlush]);

  return {
    aircraft,
    backendHealth,
    connectionStatus,
    error,
    lastSnapshotAt,
    liveWindowMinutes,
    snapshotTruncated,
    statistics,
    refreshSnapshot,
  };
}
