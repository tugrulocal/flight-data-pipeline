import {
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import type { CSSProperties } from "react";
import * as maplibregl from "maplibre-gl";
import mapLibreWorkerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url";
import type {
  Feature,
  FeatureCollection,
  LineString,
  Point,
} from "geojson";

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


maplibregl.setWorkerUrl(mapLibreWorkerUrl);


/* ------------------------------------------------------------------ */
/*  Sabitler                                                          */
/* ------------------------------------------------------------------ */

const INITIAL_CENTER: [number, number] = [28.0, 20.0];
const MERCATOR_ZOOM = 2.5;
const GLOBE_ZOOM = 1.8;

const MAPLIBRE_STYLE_URL = "https://demotiles.maplibre.org/style.json";



/** Uçak ikonu boyutu (px) */
const ICON_SIZE = 48;


/* ------------------------------------------------------------------ */
/*  Tip tanımları                                                     */
/* ------------------------------------------------------------------ */

interface MapLibreMapProps {
  aircraft: Aircraft[];
  selectedAircraft: Aircraft | null;
  selectedRoute: Aircraft[];
  routeStatus: "idle" | "loading" | "ready" | "empty" | "error";
  onSelectAircraft: (icao24: string | null) => void;
}

type AircraftPointProperties = {
  icao24: string;
  callsign: string;
  origin_country: string;
  altitude_bucket: string;
  altitude_m: number | null;
  heading_deg: number | null;
  velocity_mps: number | null;
  observed_at: string | null;
  on_ground: boolean | null;
};


/* ------------------------------------------------------------------ */
/*  Yardımcı fonksiyonlar                                             */
/* ------------------------------------------------------------------ */

function hasValidPosition(item: Aircraft) {
  return (
    Number.isFinite(item.latitude)
    && Number.isFinite(item.longitude)
  );
}


function altitudeBucket(item: Aircraft) {
  if (item.on_ground) {
    return "ground";
  }

  const altitude = item.baro_altitude_m;

  if (altitude === null || !Number.isFinite(altitude)) {
    return "unknown";
  }

  if (altitude < 1_500) {
    return "low";
  }

  if (altitude < 4_500) {
    return "lower-mid";
  }

  if (altitude < 9_000) {
    return "mid";
  }

  if (altitude < 11_500) {
    return "high";
  }

  return "very-high";
}


function aircraftToFeature(
  item: Aircraft,
): Feature<Point, AircraftPointProperties> {
  return {
    type: "Feature",
    geometry: {
      type: "Point",
      coordinates: [item.longitude, item.latitude],
    },
    properties: {
      icao24: item.icao24,
      callsign: item.callsign || item.icao24,
      origin_country: item.origin_country || "Bilinmiyor",
      altitude_bucket: altitudeBucket(item),
      altitude_m: item.baro_altitude_m,
      heading_deg: item.true_track_deg,
      velocity_mps: item.velocity_mps,
      observed_at: item.observed_at,
      on_ground: item.on_ground,
    },
  };
}


/**
 * Canvas API ile uçak silüeti (✈ benzeri ok şekli) çizer.
 * Her irtifa rengi için ayrı bir icon üretilir.
 */
function createAircraftIconImage(color: string): ImageData {
  const canvas = document.createElement("canvas");
  canvas.width = ICON_SIZE;
  canvas.height = ICON_SIZE;

  const ctx = canvas.getContext("2d")!;
  const cx = ICON_SIZE / 2;
  const cy = ICON_SIZE / 2;

  ctx.clearRect(0, 0, ICON_SIZE, ICON_SIZE);
  
  // Dış çerçeve (halo efekti için kalın kontur)
  ctx.fillStyle = color;
  ctx.strokeStyle = "#06131d"; // Koyu arka plan
  ctx.lineWidth = 3;
  ctx.lineJoin = "round";

  ctx.beginPath();
  // Kuzeye bakan uçak silüeti — üçgen gövde + kanatlar
  ctx.moveTo(cx, cy - 20);       // Burun (üst)
  ctx.lineTo(cx + 5, cy - 8);    // Sağ gövde
  ctx.lineTo(cx + 18, cy + 2);   // Sağ kanat ucu
  ctx.lineTo(cx + 5, cy + 0);    // Sağ kanat iç
  ctx.lineTo(cx + 4, cy + 10);   // Sağ gövde alt
  ctx.lineTo(cx + 9, cy + 16);   // Sağ kuyruk
  ctx.lineTo(cx + 2, cy + 12);   // Sağ kuyruk iç
  ctx.lineTo(cx, cy + 14);       // Kuyruk merkez
  ctx.lineTo(cx - 2, cy + 12);   // Sol kuyruk iç
  ctx.lineTo(cx - 9, cy + 16);   // Sol kuyruk
  ctx.lineTo(cx - 4, cy + 10);   // Sol gövde alt
  ctx.lineTo(cx - 5, cy + 0);    // Sol kanat iç
  ctx.lineTo(cx - 18, cy + 2);   // Sol kanat ucu
  ctx.lineTo(cx - 5, cy - 8);    // Sol gövde
  ctx.closePath();
  
  ctx.fill();
  ctx.stroke();

  return ctx.getImageData(0, 0, ICON_SIZE, ICON_SIZE);
}


function escapeHtml(value: string | null | undefined) {
  return (value || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll("\"", "&quot;")
    .replaceAll("'", "&#039;");
}


function popupHtml(properties: AircraftPointProperties) {
  const title = escapeHtml(properties.callsign || properties.icao24);
  const country = escapeHtml(properties.origin_country || "Bilinmiyor");
  const observedAt = escapeHtml(
    formatDateTime(properties.observed_at),
  );

  return `
    <div class="aircraft-popup">
      <strong>${title}</strong>
      <span>${country}</span>
      <dl>
        <div>
          <dt>İrtifa</dt>
          <dd>${formatAltitude(properties.altitude_m)}</dd>
        </div>
        <div>
          <dt>Hız</dt>
          <dd>${formatSpeed(properties.velocity_mps)}</dd>
        </div>
        <div>
          <dt>Yön</dt>
          <dd>${formatHeading(properties.heading_deg)}</dd>
        </div>
        <div>
          <dt>Son görülme</dt>
          <dd>${observedAt}</dd>
        </div>
      </dl>
    </div>
  `;
}


/**
 * Rota noktalarından irtifa renkli segment GeoJSON'ı üretir.
 * Her segment ayrı bir Feature olarak oluşturulur, böylece
 * her birinin kendi rengi olabilir.
 */
function routeToGeoJson(
  route: Aircraft[],
): FeatureCollection<LineString, { color: string }> {
  const features: Feature<LineString, { color: string }>[] = [];

  for (let i = 1; i < route.length; i += 1) {
    const prev = route[i - 1];
    const curr = route[i];

    if (!hasValidPosition(prev) || !hasValidPosition(curr)) {
      continue;
    }

    features.push({
      type: "Feature",
      geometry: {
        type: "LineString",
        coordinates: [
          [prev.longitude, prev.latitude],
          [curr.longitude, curr.latitude],
        ],
      },
      properties: {
        color: altitudeColor(curr),
      },
    });
  }

  return { type: "FeatureCollection", features };
}


function routeEndpointsGeoJson(
  route: Aircraft[],
): FeatureCollection<Point, { role: string; color: string }> {
  const features: Feature<Point, { role: string; color: string }>[] = [];

  if (route.length < 2) {
    return { type: "FeatureCollection", features };
  }

  const first = route[0];
  const last = route[route.length - 1];

  if (hasValidPosition(first)) {
    features.push({
      type: "Feature",
      geometry: {
        type: "Point",
        coordinates: [first.longitude, first.latitude],
      },
      properties: {
        role: "start",
        color: altitudeColor(first),
      },
    });
  }

  if (hasValidPosition(last)) {
    features.push({
      type: "Feature",
      geometry: {
        type: "Point",
        coordinates: [last.longitude, last.latitude],
      },
      properties: {
        role: "end",
        color: altitudeColor(last),
      },
    });
  }

  return { type: "FeatureCollection", features };
}


const EMPTY_FC_POINT: FeatureCollection<Point> = {
  type: "FeatureCollection",
  features: [],
};

const EMPTY_FC_LINE: FeatureCollection<LineString> = {
  type: "FeatureCollection",
  features: [],
};


/* ------------------------------------------------------------------ */
/*  MapLibreMap bileşeni                                              */
/* ------------------------------------------------------------------ */

export function MapLibreMap({
  aircraft,
  selectedAircraft,
  selectedRoute,
  routeStatus,
  onSelectAircraft,
}: MapLibreMapProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const popupRef = useRef<maplibregl.Popup | null>(null);
  const onSelectRef = useRef(onSelectAircraft);
  const [projectionMode, setProjectionMode] =
    useState<"mercator" | "globe">("mercator");

  // onSelectAircraft referansını güncel tut (closure tuzağı önlenir)
  useEffect(() => {
    onSelectRef.current = onSelectAircraft;
  }, [onSelectAircraft]);

  /* ---- Uçak GeoJSON memo ---- */
  const aircraftGeoJson = useMemo<FeatureCollection<Point>>(() => ({
    type: "FeatureCollection",
    features: aircraft
      .filter(hasValidPosition)
      .map(aircraftToFeature),
  }), [aircraft]);

  /* Ref ile de tut — style.load callback'i içinde kullanılabilsin */
  const aircraftGeoJsonRef = useRef(aircraftGeoJson);
  useEffect(() => {
    aircraftGeoJsonRef.current = aircraftGeoJson;
  }, [aircraftGeoJson]);

  /* ---- Rota GeoJSON memo ---- */
  const routeGeoJson = useMemo(
    () => routeToGeoJson(selectedRoute),
    [selectedRoute],
  );

  const routeEndpoints = useMemo(
    () => routeEndpointsGeoJson(selectedRoute),
    [selectedRoute],
  );


  /* ================================================================ */
  /*  Harita başlatma (mount'ta bir kere)                             */
  /* ================================================================ */

  useEffect(() => {
    const container = containerRef.current;

    if (!container || mapRef.current) {
      return;
    }

    const map = new maplibregl.Map({
      container,
      style: MAPLIBRE_STYLE_URL,
      center: INITIAL_CENTER,
      zoom: MERCATOR_ZOOM,
      minZoom: 1,
      maxZoom: 18,
    });

    map.addControl(
      new maplibregl.NavigationControl({ visualizePitch: true }),
      "top-left",
    );

    mapRef.current = map;

    map.on("style.load", () => {
      /* Her irtifa rengi için ayrı bir Canvas ikonu ekle */
      for (const item of ALTITUDE_LEGEND) {
        const iconName = `aircraft-${item.key}`;
        if (!map.hasImage(iconName)) {
          map.addImage(iconName, createAircraftIconImage(item.color), { pixelRatio: 2 });
        }
      }

      /* ----- Rota katmanları (altta) ----- */
      if (!map.getSource("route-lines")) {
        map.addSource("route-lines", {
          type: "geojson",
          data: EMPTY_FC_LINE,
        });
      }

      if (!map.getLayer("route-lines-layer")) {
        map.addLayer({
          id: "route-lines-layer",
          type: "line",
          source: "route-lines",
          paint: {
            "line-color": ["get", "color"],
            "line-width": 3.5,
            "line-opacity": 0.88,
          },
          layout: {
            "line-cap": "round",
            "line-join": "round",
          },
        });
      }

      if (!map.getSource("route-endpoints")) {
        map.addSource("route-endpoints", {
          type: "geojson",
          data: EMPTY_FC_POINT,
        });
      }

      if (!map.getLayer("route-endpoints-layer")) {
        map.addLayer({
          id: "route-endpoints-layer",
          type: "circle",
          source: "route-endpoints",
          paint: {
            "circle-color": [
              "match",
              ["get", "role"],
              "start", "#071722",
              "end",   ["get", "color"],
              "#ffffff",
            ],
            "circle-radius": [
              "match",
              ["get", "role"],
              "start", 4,
              "end",   5,
              4,
            ],
            "circle-stroke-color": [
              "match",
              ["get", "role"],
              "start", ["get", "color"],
              "end",   "#ffffff",
              "#ffffff",
            ],
            "circle-stroke-width": 2,
            "circle-opacity": 1,
          },
        });
      }

      /* ----- Uçak katmanı (üstte) ----- */
      if (!map.getSource("aircraft")) {
        map.addSource("aircraft", {
          type: "geojson",
          data: aircraftGeoJsonRef.current,
        });
      }

      if (!map.getLayer("aircraft-icons")) {
        map.addLayer({
          id: "aircraft-icons",
          type: "symbol",
          source: "aircraft",
          layout: {
            "icon-image": [
              "match",
              ["get", "altitude_bucket"],
              "ground", "aircraft-ground",
              "unknown", "aircraft-unknown",
              "low", "aircraft-low",
              "lower-mid", "aircraft-lower-mid",
              "mid", "aircraft-mid",
              "high", "aircraft-high",
              "very-high", "aircraft-very-high",
              "aircraft-unknown",
            ],
            "icon-size": [
              "interpolate",
              ["linear"],
              ["zoom"],
              1, 0.45,
              4, 0.6,
              8, 0.85,
              12, 1.0,
            ],
            "icon-rotate": [
              "coalesce",
              ["get", "heading_deg"],
              0,
            ],
            "icon-rotation-alignment": "map",
            "icon-allow-overlap": true,
            "icon-ignore-placement": true,
            /* İkon padding — tıklanabilir alan büyüsün */
            "icon-padding": 0,
          },
          paint: {
            "icon-opacity": 1,
          },
        });
      }

      /* ----- Etkileşim ----- */
      map.on("mouseenter", "aircraft-icons", () => {
        map.getCanvas().style.cursor = "pointer";
      });

      map.on("mouseleave", "aircraft-icons", () => {
        map.getCanvas().style.cursor = "";
      });

      map.on("click", "aircraft-icons", (event) => {
        const feature = event.features?.[0];
        const icao24 = feature?.properties?.icao24 as string | undefined;

        if (!icao24) {
          return;
        }

        onSelectRef.current(icao24);
      });

      map.on("click", (event) => {
        const features = map.queryRenderedFeatures(event.point, {
          layers: ["aircraft-icons"],
        });

        if (features.length === 0) {
          onSelectRef.current(null);
        }
      });
    });

    return () => {
      map.remove();
      mapRef.current = null;
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);


  /* ================================================================ */
  /*  Projection değişimi                                             */
  /* ================================================================ */

  useEffect(() => {
    const map = mapRef.current;

    if (!map || !map.isStyleLoaded()) {
      return;
    }

    map.setProjection({ type: projectionMode });

    if (projectionMode === "globe") {
      map.easeTo({
        center: INITIAL_CENTER,
        zoom: GLOBE_ZOOM,
        pitch: 0,
        duration: 800,
      });
    } else {
      map.easeTo({
        center: INITIAL_CENTER,
        zoom: MERCATOR_ZOOM,
        pitch: 0,
        duration: 800,
      });
    }
  }, [projectionMode]);


  /* ================================================================ */
  /*  Uçak verisini güncelle                                         */
  /* ================================================================ */

  useEffect(() => {
    const map = mapRef.current;

    if (!map || !map.isStyleLoaded()) {
      return;
    }

    const source =
      map.getSource("aircraft") as maplibregl.GeoJSONSource | undefined;

    if (source) {
      source.setData(aircraftGeoJson);
    }
  }, [aircraftGeoJson]);


  /* ================================================================ */
  /*  Rota verisini güncelle                                         */
  /* ================================================================ */

  useEffect(() => {
    const map = mapRef.current;

    if (!map || !map.isStyleLoaded()) {
      return;
    }

    const lineSource =
      map.getSource("route-lines") as maplibregl.GeoJSONSource | undefined;
    const pointSource =
      map.getSource("route-endpoints") as maplibregl.GeoJSONSource | undefined;

    if (lineSource) {
      lineSource.setData(routeGeoJson);
    }

    if (pointSource) {
      pointSource.setData(routeEndpoints);
    }
  }, [routeGeoJson, routeEndpoints]);


  /* ================================================================ */
  /*  Popup — seçili uçak                                            */
  /* ================================================================ */

  useEffect(() => {
    const map = mapRef.current;

    if (!map || !map.isStyleLoaded()) {
      return;
    }

    // Önceki popup'ı kapat
    popupRef.current?.remove();
    popupRef.current = null;

    if (!selectedAircraft || !hasValidPosition(selectedAircraft)) {
      return;
    }

    const props: AircraftPointProperties = {
      icao24: selectedAircraft.icao24,
      callsign: selectedAircraft.callsign || selectedAircraft.icao24,
      origin_country: selectedAircraft.origin_country || "Bilinmiyor",
      altitude_bucket: altitudeBucket(selectedAircraft),
      altitude_m: selectedAircraft.baro_altitude_m,
      heading_deg: selectedAircraft.true_track_deg,
      velocity_mps: selectedAircraft.velocity_mps,
      observed_at: selectedAircraft.observed_at,
      on_ground: selectedAircraft.on_ground,
    };

    popupRef.current = new maplibregl.Popup({
      closeButton: true,
      offset: 14,
      className: "maplibre-aircraft-popup",
    })
      .setLngLat([selectedAircraft.longitude, selectedAircraft.latitude])
      .setHTML(popupHtml(props))
      .addTo(map);
  }, [selectedAircraft]);


  /* ================================================================ */
  /*  Render                                                         */
  /* ================================================================ */

  return (
    <div
      className="map-shell maplibre-shell"
      aria-label="Canlı uçuş haritası — MapLibre"
      data-feature-count={aircraftGeoJson.features.length}
    >
      <div ref={containerRef} className="maplibre-map" />

      {/* Projection toggle */}
      <div
        className="maplibre-projection-bar"
        aria-label="Harita projeksiyonu seçimi"
      >
        <button
          type="button"
          className={projectionMode === "mercator" ? "active" : ""}
          onClick={() => setProjectionMode("mercator")}
        >
          Düz
        </button>
        <button
          type="button"
          className={projectionMode === "globe" ? "active" : ""}
          onClick={() => setProjectionMode("globe")}
        >
          Küre
        </button>
      </div>

      {/* Rota durumu */}
      {selectedAircraft && (
        <div className={`route-status ${routeStatus}`}>
          <strong>
            {selectedAircraft.callsign || selectedAircraft.icao24}
          </strong>
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

      {/* İrtifa renk efsanesi */}
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
