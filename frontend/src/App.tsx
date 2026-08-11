import {
  Suspense,
  lazy,
  useEffect,
  useMemo,
  useState,
} from "react";

import { AircraftMap } from "./components/AircraftMap";
import { AircraftTable } from "./components/AircraftTable";
import { MapErrorBoundary } from "./components/MapErrorBoundary";
import { TakeoffIcon } from "./components/TakeoffIcon";
import airplaneIcon from "./icons/airplane.png";
import largeAirplaneLogo from "./icons/airplane buyuk logo.png";
import {
  isRecentlyObserved,
  useAircraftFeed,
} from "./hooks/useAircraftFeed";
import { formatTime } from "./lib/formatters";
import type { MapTheme } from "./components/MapLibreMap";
import type {
  Aircraft,
  AircraftHistoryResponse,
} from "./types";


const TABLE_ROW_LIMIT = 300;
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


function SearchIcon() {
  return (
    <svg
      className="search-icon"
      viewBox="0 0 24 24"
      aria-hidden="true"
    >
      <circle cx="11" cy="11" r="6.5" />
      <path d="m16 16 4.2 4.2" />
    </svg>
  );
}

function CloseIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="m6 6 12 12M18 6 6 18" />
    </svg>
  );
}


function App() {
  const {
    aircraft,
    connectionStatus,
    error,
    lastSnapshotAt,
    liveWindowMinutes,
    refreshSnapshot,
    snapshotTruncated,
  } = useAircraftFeed();
  const [search, setSearch] = useState("");
  const [selectedIcao24, setSelectedIcao24] =
    useState<string | null>(null);
  const [routeHistory, setRouteHistory] = useState<Aircraft[]>([]);
  const [routeStatus, setRouteStatus] =
    useState<"idle" | "loading" | "ready" | "empty" | "error">("idle");
  const [mapTheme, setMapTheme] = useState<MapTheme>("light");
  const [mapFallbackReason, setMapFallbackReason] = useState<string | null>(
    null,
  );
  const [mapRetryKey, setMapRetryKey] = useState(0);
  const [isOperationsOpen, setIsOperationsOpen] = useState(false);
  const [nowMs, setNowMs] = useState(() => Date.now());
  const livePositionMaxAgeMs = liveWindowMinutes * 60 * 1000;

  useEffect(() => {
    const iconLink = document.querySelector<HTMLLinkElement>("link[rel~='icon']");
    if (!iconLink) {
      return;
    }

    const image = new Image();
    image.onload = () => {
      const canvas = document.createElement("canvas");
      canvas.width = 32;
      canvas.height = 32;
      const context = canvas.getContext("2d");
      if (!context) {
        return;
      }

      context.drawImage(image, 0, 0, canvas.width, canvas.height);
      context.globalCompositeOperation = "source-in";
      context.fillStyle = "#4de3c1";
      context.fillRect(0, 0, canvas.width, canvas.height);
      iconLink.href = canvas.toDataURL("image/png");
    };
    image.src = airplaneIcon;

    return () => {
      image.onload = null;
    };
  }, []);

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
      isRecentlyObserved(
        item.observed_at,
        nowMs,
        livePositionMaxAgeMs,
      ),
    ),
    [aircraft, livePositionMaxAgeMs, nowMs],
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
    let unknown = 0;

    for (const item of liveAircraft) {
      if (item.on_ground === true) {
        onGround += 1;
      } else if (item.on_ground === false) {
        airborne += 1;
      } else {
        unknown += 1;
      }
    }

    return {
      total: liveAircraft.length,
      airborne,
      onGround,
      unknown,
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
            <img
              className="brand-airplane-icon"
              src={largeAirplaneLogo}
              alt=""
              aria-hidden="true"
            />
            <div>
              <p className="eyebrow">Canlı uçuş ağı</p>
              <h1>Flight Pulse</h1>
            </div>
          </div>

          <div className="map-top-actions">
            {!mapFallbackReason && <div
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
            </div>}

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

        {mapFallbackReason ? (
          <AircraftMap
            aircraft={filteredAircraft}
            selectedAircraft={selectedAircraft}
            selectedRoute={routeHistory}
            routeStatus={routeStatus}
            onSelectAircraft={setSelectedIcao24}
          />
        ) : (
          <MapErrorBoundary
            resetKey={mapRetryKey}
            onError={(mapError) => setMapFallbackReason(mapError.message)}
          >
            <Suspense
              fallback={
                <div className="map-shell loading-fallback">
                  MapLibre haritası yükleniyor…
                </div>
              }
            >
              <MapLibreMap
                key={mapRetryKey}
                aircraft={filteredAircraft}
                selectedAircraft={selectedAircraft}
                selectedRoute={routeHistory}
                routeStatus={routeStatus}
                mapTheme={mapTheme}
                onSelectAircraft={setSelectedIcao24}
                onMapError={(mapError) =>
                  setMapFallbackReason(mapError.message)
                }
              />
            </Suspense>
          </MapErrorBoundary>
        )}

        {mapFallbackReason && (
          <aside className="map-fallback-notice" role="status">
            <span>
              Uyumluluk haritası aktif.
              <small>{mapFallbackReason}</small>
            </span>
            <button
              type="button"
              onClick={() => {
                setMapFallbackReason(null);
                setMapRetryKey((key) => key + 1);
              }}
            >
              WebGL'i tekrar dene
            </button>
          </aside>
        )}

        <div className="map-dashboard">
          <label className="search-field map-search-field">
            <span className="sr-only">Uçak ara</span>
            <SearchIcon />
            <input
              type="search"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Uçuş, ICAO24 veya ülke ara"
            />
          </label>

          <section className="metrics map-metrics" aria-label="Canlı uçuş istatistikleri">
            <article className="flight-summary-card">
              <div>
                <span>Canlı</span>
                <strong>{statistics.total}</strong>
                <small>son {liveWindowMinutes} dk</small>
              </div>
              <div>
                <span>Havada</span>
                <strong>{statistics.airborne}</strong>
                <small>aktif uçuş</small>
              </div>
              <div>
                <span>Yerde</span>
                <strong>{statistics.onGround}</strong>
                <small>
                  {statistics.unknown > 0
                    ? `${statistics.unknown} bilinmiyor`
                    : "son durum"}
                </small>
              </div>
            </article>
          </section>

        </div>

        <aside
          className={`operations-drawer ${
            isOperationsOpen ? "is-open" : ""
          }`}
          aria-label="Operasyon listesi"
        >
          {!isOperationsOpen && (
            <button
              type="button"
              className="operations-toggle"
              onClick={() => setIsOperationsOpen(true)}
              aria-expanded="false"
              aria-controls="operations-panel"
              aria-label="Operasyonlar"
            >
              <TakeoffIcon className="operations-takeoff-icon" />
              <span>Operasyonlar</span>
            </button>
          )}

          <div id="operations-panel" className="operations-panel">
            <div className="operations-panel-header">
              <div>
                <p className="eyebrow">Operasyon listesi</p>
                <h2>Uçaklar</h2>
              </div>
              <button
                type="button"
                className="operations-close"
                onClick={() => setIsOperationsOpen(false)}
                aria-label="Operasyon listesini kapat"
              >
                <CloseIcon />
              </button>
            </div>

            <AircraftTable
              aircraft={filteredAircraft.slice(0, TABLE_ROW_LIMIT)}
              selectedIcao24={selectedIcao24}
              onSelectAircraft={setSelectedIcao24}
            />

          </div>
        </aside>

      </section>

    </main>
  );
}


export default App;
