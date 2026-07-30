import {
  useEffect,
  useMemo,
  useRef,
} from "react";
import type { CSSProperties } from "react";
import L from "leaflet";

import type { Aircraft } from "../types";
import {
  formatAltitude,
  formatDateTime,
  formatHeading,
  formatSpeed,
} from "../lib/formatters";
import {
  ALTITUDE_LEGEND,
  altitudeColor,
} from "../lib/altitudeColors";


const INITIAL_CENTER: L.LatLngExpression = [39.0, 35.5];
const INITIAL_ZOOM = 6;
const MIN_ZOOM = 2;
const MAX_ZOOM = 16;
const TILE_URL = "https://tile.openstreetmap.org/{z}/{x}/{y}.png";
const TILE_ATTRIBUTION =
  "&copy; <a href=\"https://www.openstreetmap.org/copyright\">OpenStreetMap</a> contributors";


interface AircraftMapProps {
  aircraft: Aircraft[];
  selectedAircraft: Aircraft | null;
  selectedRoute: Aircraft[];
  routeStatus: "idle" | "loading" | "ready" | "empty" | "error";
  onSelectAircraft: (icao24: string | null) => void;
}


function hasValidPosition(item: Aircraft) {
  return (
    Number.isFinite(item.latitude)
    && Number.isFinite(item.longitude)
  );
}


function escapeHtml(value: string | null | undefined) {
  return (value || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll("\"", "&quot;")
    .replaceAll("'", "&#039;");
}


function routeSegmentColor(item: Aircraft) {
  return altitudeColor(item);
}


function popupHtml(item: Aircraft) {
  const title = escapeHtml(item.callsign || item.icao24);
  const country = escapeHtml(item.origin_country || "Bilinmiyor");
  const observedAt = escapeHtml(formatDateTime(item.observed_at));

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
        <div>
          <dt>Son görülme</dt>
          <dd>${observedAt}</dd>
        </div>
      </dl>
    </div>
  `;
}


function aircraftIcon(item: Aircraft) {
  const heading = Number.isFinite(item.true_track_deg)
    ? item.true_track_deg
    : 0;
  const color = altitudeColor(item);

  return L.divIcon({
    className: "aircraft-leaflet-marker",
    html: `
      <span
        class="aircraft-leaflet-glyph"
        style="--aircraft-heading: ${heading}deg; --aircraft-color: ${color}"
      >&#9992;</span>
    `,
    iconAnchor: [15, 15],
    iconSize: [30, 30],
  });
}


export function AircraftMap({
  aircraft,
  selectedAircraft,
  selectedRoute,
  routeStatus,
  onSelectAircraft,
}: AircraftMapProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapShellRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<L.Map | null>(null);
  const markerLayerRef = useRef<L.LayerGroup | null>(null);
  const routeLayerRef = useRef<L.LayerGroup | null>(null);
  const onSelectAircraftRef = useRef(onSelectAircraft);

  const visibleAircraft = useMemo(
    () => aircraft.filter(hasValidPosition),
    [aircraft],
  );

  useEffect(() => {
    onSelectAircraftRef.current = onSelectAircraft;
  }, [onSelectAircraft]);

  const updateMapDiagnostics = () => {
    const map = mapRef.current;
    const shell = mapShellRef.current;

    if (!map || !shell) {
      return;
    }

    const center = map.getCenter();
    shell.dataset.mapReady = "true";
    shell.dataset.zoom = map.getZoom().toFixed(2);
    shell.dataset.centerLng = center.lng.toFixed(5);
    shell.dataset.centerLat = center.lat.toFixed(5);
    shell.dataset.dragPanEnabled = String(map.dragging.enabled());
    shell.dataset.scrollZoomEnabled = String(
      map.scrollWheelZoom.enabled(),
    );
  };

  useEffect(() => {
    const container = containerRef.current;

    if (!container || mapRef.current) {
      return;
    }

    const map = L.map(container, {
      center: INITIAL_CENTER,
      zoom: INITIAL_ZOOM,
      minZoom: MIN_ZOOM,
      maxZoom: MAX_ZOOM,
      zoomControl: true,
      preferCanvas: true,
      worldCopyJump: true,
    });

    L.tileLayer(TILE_URL, {
      attribution: TILE_ATTRIBUTION,
      maxZoom: 19,
    }).addTo(map);

    const routeLayer = L.layerGroup().addTo(map);
    const markerLayer = L.layerGroup().addTo(map);
    mapRef.current = map;
    markerLayerRef.current = markerLayer;
    routeLayerRef.current = routeLayer;

    map.on("click", () => onSelectAircraftRef.current(null));
    map.on("move zoom moveend zoomend", updateMapDiagnostics);

    window.setTimeout(() => {
      map.invalidateSize();
      updateMapDiagnostics();
    }, 0);

    return () => {
      map.remove();
      mapRef.current = null;
      markerLayerRef.current = null;
      routeLayerRef.current = null;
    };
  }, []);

  useEffect(() => {
    const layer = routeLayerRef.current;
    const shell = mapShellRef.current;

    if (!layer) {
      return;
    }

    layer.clearLayers();

    if (shell) {
      shell.dataset.routePointCount = String(selectedRoute.length);
    }

    if (selectedRoute.length < 2) {
      return;
    }

    const coordinates = selectedRoute.map((item) =>
      [item.latitude, item.longitude] as L.LatLngTuple
    );

    for (let index = 1; index < selectedRoute.length; index += 1) {
      const previous = coordinates[index - 1];
      const current = coordinates[index];
      const currentPoint = selectedRoute[index];

      L.polyline([previous, current], {
        color: routeSegmentColor(currentPoint),
        lineCap: "round",
        lineJoin: "round",
        opacity: 0.92,
        weight: 4,
      }).addTo(layer);
    }

    L.circleMarker(coordinates[0], {
      className: "route-point route-start",
      color: routeSegmentColor(selectedRoute[0]),
      fillColor: "#071722",
      fillOpacity: 1,
      opacity: 1,
      radius: 4,
      weight: 2,
    }).addTo(layer);

    L.circleMarker(coordinates[coordinates.length - 1], {
      className: "route-point route-end",
      color: "#ffffff",
      fillColor: routeSegmentColor(
        selectedRoute[selectedRoute.length - 1],
      ),
      fillOpacity: 1,
      opacity: 1,
      radius: 5,
      weight: 2,
    }).addTo(layer);
  }, [selectedRoute]);

  useEffect(() => {
    const layer = markerLayerRef.current;
    const shell = mapShellRef.current;

    if (!layer) {
      return;
    }

    layer.clearLayers();

    for (const item of visibleAircraft) {
      const marker = L.marker([item.latitude, item.longitude], {
        bubblingMouseEvents: false,
        icon: aircraftIcon(item),
        keyboard: false,
        riseOnHover: true,
      });

      marker.bindPopup(popupHtml(item), {
        className: "aircraft-leaflet-popup",
        closeButton: true,
        offset: [0, -8],
      });

      marker.on("click", () => {
        onSelectAircraft(item.icao24);
      });

      marker.addTo(layer);

      if (selectedAircraft?.icao24 === item.icao24) {
        marker.openPopup();
      }
    }

    if (shell) {
      shell.dataset.featureCount = String(visibleAircraft.length);
      shell.dataset.drawnAircraft = String(visibleAircraft.length);
    }

    updateMapDiagnostics();
  }, [onSelectAircraft, selectedAircraft, visibleAircraft]);

  return (
    <div
      ref={mapShellRef}
      className="map-shell"
      aria-label="Canlı uçuş haritası"
      data-feature-count={visibleAircraft.length}
    >
      <div ref={containerRef} className="leaflet-map" />

      {selectedAircraft && (
        <div className={`route-status ${routeStatus}`}>
          <strong>{selectedAircraft.callsign || selectedAircraft.icao24}</strong>
          <span>
            {routeStatus === "loading" && "Rota yükleniyor…"}
            {routeStatus === "ready"
              && `${selectedRoute.length} nokta ile irtifa renkli rota`}
            {routeStatus === "empty"
              && "Rota için yeterli geçmiş nokta yok"}
            {routeStatus === "error" && "Rota alınamadı"}
            {routeStatus === "idle" && "Uçak seçildi"}
          </span>
        </div>
      )}

      <div
        className="altitude-legend"
        aria-label="İrtifaya göre uçak renkleri"
      >
        <strong>İrtifa aralıkları</strong>
        <div className="altitude-legend-grid">
          {ALTITUDE_LEGEND.map((item) => (
            <span key={item.key}>
              <i
                className="legend-swatch"
                style={{ "--legend-color": item.color } as CSSProperties}
              />
              {item.label}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}
