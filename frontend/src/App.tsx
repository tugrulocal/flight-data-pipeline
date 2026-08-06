import {
  Suspense,
  lazy,
  useEffect,
  useMemo,
  useState,
} from "react";

import { AircraftMap } from "./components/AircraftMap";
import { AircraftTable } from "./components/AircraftTable";
import { useAircraftFeed } from "./hooks/useAircraftFeed";
import { formatTime } from "./lib/formatters";
import type { MapTheme } from "./components/MapLibreMap";
import type {
  Aircraft,
  AircraftHistoryResponse,
} from "./types";


const TABLE_ROW_LIMIT = 300;
const LIVE_POSITION_WINDOW_MINUTES = Number(
  import.meta.env.VITE_LIVE_POSITION_WINDOW_MINUTES ?? 10,
);
const LIVE_POSITION_MAX_AGE_MS =
  LIVE_POSITION_WINDOW_MINUTES * 60 * 1000;
const ROUTE_HISTORY_LIMIT = 120;

const MapLibreMap = lazy(() =>
  import("./components/MapLibreMap").then((module) => ({
    default: module.MapLibreMap,
  }))
);


function SunIcon() {
  return (
    <svg
      className="theme-icon sun-icon"
      viewBox="0 0 24 24"
      aria-hidden="true"
    >
      <circle cx="12" cy="12" r="4.1" />
      <path d="M12 1.8v3M12 19.2v3M4.8 4.8l2.1 2.1M17.1 17.1l2.1 2.1M1.8 12h3M19.2 12h3M4.8 19.2l2.1-2.1M17.1 6.9l2.1-2.1" />
    </svg>
  );
}


function MoonIcon() {
  return (
    <svg
      className="theme-icon moon-icon"
      viewBox="0 0 24 24"
      aria-hidden="true"
    >
      <path d="M19.4 15.4A7.8 7.8 0 0 1 8.6 4.6 8.2 8.2 0 1 0 19.4 15.4Z" />
    </svg>
  );
}


function isRecentlyObserved(observedAt: string | null, nowMs: number) {
  if (!observedAt) {
    return false;
  }

  const observedMs = new Date(observedAt).getTime();

  return (
    Number.isFinite(observedMs)
    && nowMs - observedMs <= LIVE_POSITION_MAX_AGE_MS
  );
}


function App() {
  const {
    aircraft,
    backendHealth,
    connectionStatus,
    error,
    lastSnapshotAt,
    refreshSnapshot,
  } = useAircraftFeed();
  const [search, setSearch] = useState("");
  const [selectedIcao24, setSelectedIcao24] =
    useState<string | null>(null);
  const [routeHistory, setRouteHistory] = useState<Aircraft[]>([]);
  const [routeStatus, setRouteStatus] =
    useState<"idle" | "loading" | "ready" | "empty" | "error">("idle");
  const [mapEngine, setMapEngine] =
    useState<"leaflet" | "maplibre">("maplibre");
  const [mapTheme, setMapTheme] = useState<MapTheme>("light");
  const [nowMs, setNowMs] = useState(() => Date.now());

  useEffect(() => {
    const intervalId = window.setInterval(
      () => setNowMs(Date.now()),
      60_000,
    );

    return () => window.clearInterval(intervalId);
  }, []);

  useEffect(() => {
    if (!selectedIcao24) {
      setRouteHistory([]);
      setRouteStatus("idle");
      return;
    }

    const abortController = new AbortController();

    async function loadRouteHistory() {
      setRouteStatus("loading");

      try {
        const response = await fetch(
          `/api/aircraft/${selectedIcao24}/history?limit=${ROUTE_HISTORY_LIMIT}`,
          {
            signal: abortController.signal,
          },
        );

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }

        const payload =
          await response.json() as AircraftHistoryResponse;

        if (abortController.signal.aborted) {
          return;
        }

        const routeItems = payload.items
          .filter((item) =>
            Number.isFinite(item.latitude)
            && Number.isFinite(item.longitude),
          )
          .sort((left, right) => {
            const leftTime = left.observed_at
              ? new Date(left.observed_at).getTime()
              : 0;
            const rightTime = right.observed_at
              ? new Date(right.observed_at).getTime()
              : 0;

            return leftTime - rightTime;
          });

        setRouteHistory(routeItems);
        setRouteStatus(routeItems.length > 1 ? "ready" : "empty");
      } catch (routeError) {
        if (abortController.signal.aborted) {
          return;
        }

        console.error("Uçak rotası alınamadı.", routeError);
        setRouteHistory([]);
        setRouteStatus("error");
      }
    }

    void loadRouteHistory();

    return () => abortController.abort();
  }, [selectedIcao24]);

  const liveAircraft = useMemo(
    () => aircraft.filter((item) =>
      isRecentlyObserved(item.observed_at, nowMs),
    ),
    [aircraft, nowMs],
  );

  const hiddenStaleCount = aircraft.length - liveAircraft.length;

  const filteredAircraft = useMemo(() => {
    const normalizedSearch = search.trim().toLowerCase();

    if (!normalizedSearch) {
      return liveAircraft;
    }

    return liveAircraft.filter((item) =>
      item.icao24.includes(normalizedSearch)
      || item.callsign?.toLowerCase().includes(normalizedSearch)
      || item.origin_country?.toLowerCase().includes(normalizedSearch),
    );
  }, [liveAircraft, search]);

  const selectedAircraft = useMemo(
    () => liveAircraft.find((item) => item.icao24 === selectedIcao24) ?? null,
    [liveAircraft, selectedIcao24],
  );

  const statistics = useMemo(() => {
    let airborne = 0;
    let onGround = 0;

    for (const item of liveAircraft) {
      if (item.on_ground) {
        onGround += 1;
      } else {
        airborne += 1;
      }
    }

    return {
      total: liveAircraft.length,
      airborne,
      onGround,
    };
  }, [liveAircraft]);

  const statusText = {
    connecting: "Bağlanıyor",
    live: "Canlı",
    reconnecting: "Yeniden bağlanıyor",
    offline: "Çevrimdışı",
  }[connectionStatus];

  return (
    <main className="app-shell">
      {error && (
        <aside className="error-banner" role="alert">
          <span>{error}</span>
          <button type="button" onClick={() => void refreshSnapshot()}>
            Tekrar dene
          </button>
        </aside>
      )}

      <section className="map-panel flight-map-stage">
        <div className="map-stage-head">
          <div className="brand">
            <div className="brand-mark" aria-hidden="true">
              <span />
            </div>
            <div>
              <p className="eyebrow">Canlı uçuş ağı</p>
              <h1>Flight Pulse</h1>
            </div>
          </div>

          <div className="map-top-actions">
            <div
              className="map-theme-toggle"
              aria-label="Harita tema seçimi"
            >
              <button
                type="button"
                className={mapTheme === "light" ? "active" : ""}
                aria-label="Açık harita teması"
                title="Açık tema"
                onClick={() => setMapTheme("light")}
              >
                <SunIcon />
              </button>
              <button
                type="button"
                className={mapTheme === "dark" ? "active" : ""}
                aria-label="Koyu harita teması"
                title="Koyu tema"
                onClick={() => setMapTheme("dark")}
              >
                <MoonIcon />
              </button>
            </div>

            <div className={`connection-pill ${connectionStatus}`}>
              <span className="status-dot" />
              <div>
                <strong>{statusText}</strong>
                <small>
                  {lastSnapshotAt
                    ? `Snapshot ${formatTime(lastSnapshotAt.toISOString())}`
                    : "Veri bekleniyor"}
                </small>
              </div>
            </div>
          </div>
        </div>

        <div className="map-engine-switch" aria-label="Harita motoru seçimi">
          <span>Harita motoru</span>
          <button
            type="button"
            className={mapEngine === "leaflet" ? "active" : ""}
            onClick={() => setMapEngine("leaflet")}
          >
            Leaflet
          </button>
          <button
            type="button"
            className={mapEngine === "maplibre" ? "active" : ""}
            onClick={() => setMapEngine("maplibre")}
          >
            MapLibre (WebGL)
          </button>
        </div>

        {mapEngine === "leaflet" ? (
          <AircraftMap
            aircraft={filteredAircraft}
            selectedAircraft={selectedAircraft}
            selectedRoute={routeHistory}
            routeStatus={routeStatus}
            onSelectAircraft={setSelectedIcao24}
          />
        ) : (
          <Suspense
            fallback={
              <div className="map-shell loading-fallback">
                MapLibre haritası yükleniyor…
              </div>
            }
          >
            <MapLibreMap
              aircraft={filteredAircraft}
              selectedAircraft={selectedAircraft}
              selectedRoute={routeHistory}
              routeStatus={routeStatus}
              mapTheme={mapTheme}
              onSelectAircraft={setSelectedIcao24}
            />
          </Suspense>
        )}

        <label className="search-field map-search-field">
          <span className="sr-only">Uçak ara</span>
          <input
            type="search"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Uçuş, ICAO24 veya ülke ara"
          />
        </label>

        <section className="metrics map-metrics" aria-label="Canlı uçuş istatistikleri">
          <article>
            <span>Canlı</span>
            <strong>{statistics.total}</strong>
            <small>son {LIVE_POSITION_WINDOW_MINUTES} dk</small>
          </article>
          <article>
            <span>Havada</span>
            <strong>{statistics.airborne}</strong>
            <small>aktif uçuş</small>
          </article>
          <article>
            <span>Yerde</span>
            <strong>{statistics.onGround}</strong>
            <small>son durum</small>
          </article>
          <article>
            <span>Sistem</span>
            <strong className="system-state">
              {backendHealth?.status === "ok" ? "Sağlıklı" : "Kontrol"}
            </strong>
            <small>Kafka + MongoDB</small>
          </article>
        </section>

        <div className="map-count-pill">
          Son {LIVE_POSITION_WINDOW_MINUTES} dk: {filteredAircraft.length} uçak
          {hiddenStaleCount > 0
            ? ` · ${hiddenStaleCount} daha eski son konum gizli`
            : ""}
        </div>
      </section>

      <section className="table-panel">
        <div className="section-heading table-heading">
          <div>
            <p className="eyebrow">Operasyon listesi</p>
            <h2>Uçaklar</h2>
          </div>
        </div>

        <AircraftTable
          aircraft={filteredAircraft.slice(0, TABLE_ROW_LIMIT)}
          selectedIcao24={selectedIcao24}
          onSelectAircraft={setSelectedIcao24}
        />

        {filteredAircraft.length > TABLE_ROW_LIMIT && (
          <p className="table-note">
            Akıcı kaydırma için ilk {TABLE_ROW_LIMIT} kayıt gösteriliyor.
          </p>
        )}
      </section>
    </main>
  );
}


export default App;
