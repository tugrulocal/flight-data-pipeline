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
import type {
  Aircraft,
  AircraftHistoryResponse,
} from "./types";


const TABLE_ROW_LIMIT = 200;
const LIVE_POSITION_MAX_AGE_MS = 10 * 60 * 1000;
const ROUTE_HISTORY_LIMIT = 120;

const MapLibreMap = lazy(() =>
  import("./components/MapLibreMap").then((module) => ({
    default: module.MapLibreMap,
  }))
);


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
    useState<"leaflet" | "maplibre">("leaflet");
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
      <header className="topbar">
        <div className="brand">
          <div className="brand-mark" aria-hidden="true">
            <span />
          </div>
          <div>
            <p className="eyebrow">Canlı uçuş ağı</p>
            <h1>Flight Pulse</h1>
          </div>
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
      </header>

      {error && (
        <aside className="error-banner" role="alert">
          <span>{error}</span>
          <button type="button" onClick={() => void refreshSnapshot()}>
            Tekrar dene
          </button>
        </aside>
      )}

      <section className="metrics" aria-label="Canlı uçuş istatistikleri">
        <article>
          <span>Canlı görülen</span>
          <strong>{statistics.total}</strong>
          <small>canlı pencere: 10 dk</small>
        </article>
        <article>
          <span>Havada</span>
          <strong>{statistics.airborne}</strong>
          <small>aktif uçuş</small>
        </article>
        <article>
          <span>Yerde</span>
          <strong>{statistics.onGround}</strong>
          <small>son bilinen durum</small>
        </article>
        <article>
          <span>Sistem</span>
          <strong className="system-state">
            {backendHealth?.status === "ok" ? "Sağlıklı" : "Kontrol ediliyor"}
          </strong>
          <small>Kafka + MongoDB</small>
        </article>
      </section>

      <section className="map-panel">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Gerçek zamanlı görünüm</p>
            <h2>Canlı uçuş haritası</h2>
          </div>
          <span>
            {filteredAircraft.length} canlı uçak
            {hiddenStaleCount > 0
              ? `, ${hiddenStaleCount} 10 dk penceresi dışında gizli`
              : ""}
          </span>
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
              onSelectAircraft={setSelectedIcao24}
            />
          </Suspense>
        )}
      </section>

      <section className="table-panel">
        <div className="section-heading table-heading">
          <div>
            <p className="eyebrow">Operasyon listesi</p>
            <h2>Uçaklar</h2>
          </div>

          <label className="search-field">
            <span className="sr-only">Uçak ara</span>
            <input
              type="search"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Uçuş, ICAO24 veya ülke ara"
            />
          </label>
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
