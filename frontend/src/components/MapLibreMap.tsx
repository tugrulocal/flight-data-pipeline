import {
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import * as maplibregl from "maplibre-gl";
import mapLibreWorkerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url";
import type {
  Feature,
  FeatureCollection,
  LineString,
  Point,
} from "geojson";

import type { Aircraft } from "../types";
import { aircraftPopupHtml } from "../lib/aircraftPopup";
import {
  ALTITUDE_LEGEND,
  altitudeBucketKey,
  altitudeColor,
} from "../lib/altitudeColors";
import { AltitudeLegend } from "./MapOverlays";
import type { RouteStatus } from "./MapOverlays";


maplibregl.setWorkerUrl(mapLibreWorkerUrl);


/* ------------------------------------------------------------------ */
/*  Sabitler                                                          */
/* ------------------------------------------------------------------ */

const INITIAL_CENTER: [number, number] = [28.0, 20.0];
const MERCATOR_ZOOM = 2.5;
const GLOBE_ZOOM = 1.8;

export type MapTheme = "light" | "dark";

const MAPLIBRE_STYLES: Record<MapTheme, maplibregl.StyleSpecification> = {
  light: {
    version: 8,
    sources: {
      basemap: {
        type: "raster",
        tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
        tileSize: 256,
        attribution: "© OpenStreetMap contributors",
      },
    },
    layers: [
      {
        id: "basemap",
        type: "raster",
        source: "basemap",
      },
    ],
  },
  dark: {
    version: 8,
    sources: {
      basemap: {
        type: "raster",
        tiles: ["https://basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png"],
        tileSize: 256,
        attribution: "© OpenStreetMap contributors © CARTO",
      },
    },
    layers: [
      {
        id: "basemap",
        type: "raster",
        source: "basemap",
      },
    ],
  },
};



/** Uçak ikonu boyutu (px) */
const ICON_SIZE = 48;
const HOVER_POPUP_DELAY_MS = 1_500;
const DEFAULT_ROUTE_GRADIENT = [
  "interpolate",
  ["linear"],
  ["line-progress"],
  0,
  "#28f3ff",
  1,
  "#28f3ff",
] as unknown as maplibregl.ExpressionSpecification;


/* ------------------------------------------------------------------ */
/*  Tip tanımları                                                     */
/* ------------------------------------------------------------------ */

interface MapLibreMapProps {
  aircraft: Aircraft[];
  selectedAircraft: Aircraft | null;
  selectedRoute: Aircraft[];
  routeStatus: RouteStatus;
  mapTheme: MapTheme;
  onSelectAircraft: (icao24: string | null) => void;
  onMapError: (error: Error) => void;
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
  return altitudeBucketKey(item);
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
 * Canvas API ile küçük ama okunaklı bir uçak silüeti çizer.
 * MapLibre sembol katmanı bu bitmap'i WebGL içinde binlerce kez basar.
 */
function createAircraftIconImage(color: string): ImageData {
  const canvas = document.createElement("canvas");
  canvas.width = ICON_SIZE;
  canvas.height = ICON_SIZE;

  const ctx = canvas.getContext("2d")!;
  const cx = ICON_SIZE / 2;
  const cy = ICON_SIZE / 2;

  ctx.clearRect(0, 0, ICON_SIZE, ICON_SIZE);

  // Kuzeye bakan, geniş kanatlı uçak silüeti.
  ctx.fillStyle = color;
  ctx.strokeStyle = "#06131d";
  ctx.lineWidth = 3.4;
  ctx.lineJoin = "round";
  ctx.lineCap = "round";

  ctx.beginPath();
  ctx.moveTo(cx, cy - 22);       // Burun
  ctx.lineTo(cx + 4, cy - 15);
  ctx.lineTo(cx + 5, cy - 5);
  ctx.lineTo(cx + 20, cy + 4);   // Sağ ana kanat
  ctx.lineTo(cx + 20, cy + 9);
  ctx.lineTo(cx + 5, cy + 5);
  ctx.lineTo(cx + 4, cy + 13);
  ctx.lineTo(cx + 11, cy + 19);  // Sağ kuyruk kanadı
  ctx.lineTo(cx + 11, cy + 23);
  ctx.lineTo(cx + 1, cy + 18);
  ctx.lineTo(cx, cy + 22);       // Kuyruk ucu
  ctx.lineTo(cx - 1, cy + 18);
  ctx.lineTo(cx - 11, cy + 23);
  ctx.lineTo(cx - 11, cy + 19);  // Sol kuyruk kanadı
  ctx.lineTo(cx - 4, cy + 13);
  ctx.lineTo(cx - 5, cy + 5);
  ctx.lineTo(cx - 20, cy + 9);
  ctx.lineTo(cx - 20, cy + 4);   // Sol ana kanat
  ctx.lineTo(cx - 5, cy - 5);
  ctx.lineTo(cx - 4, cy - 15);
  ctx.closePath();

  ctx.stroke();
  ctx.fill();

  // Gövde çizgisi ikonu "ok" gibi değil, uçak gibi okutuyor.
  ctx.beginPath();
  ctx.moveTo(cx, cy - 17);
  ctx.lineTo(cx, cy + 15);
  ctx.strokeStyle = "rgba(6, 19, 29, 0.45)";
  ctx.lineWidth = 1.7;
  ctx.stroke();

  return ctx.getImageData(0, 0, ICON_SIZE, ICON_SIZE);
}


function featurePropertiesToPopupProps(
  properties: Record<string, unknown> | null | undefined,
): AircraftPointProperties | null {
  if (!properties || typeof properties.icao24 !== "string") {
    return null;
  }

  const nullableNumber = (value: unknown) => {
    const numberValue = Number(value);
    return Number.isFinite(numberValue) ? numberValue : null;
  };

  return {
    icao24: properties.icao24,
    callsign: typeof properties.callsign === "string"
      ? properties.callsign
      : properties.icao24,
    origin_country: typeof properties.origin_country === "string"
      ? properties.origin_country
      : "Bilinmiyor",
    altitude_bucket: typeof properties.altitude_bucket === "string"
      ? properties.altitude_bucket
      : "unknown",
    altitude_m: nullableNumber(properties.altitude_m),
    heading_deg: nullableNumber(properties.heading_deg),
    velocity_mps: nullableNumber(properties.velocity_mps),
    observed_at: typeof properties.observed_at === "string"
      ? properties.observed_at
      : null,
    on_ground: typeof properties.on_ground === "boolean"
      ? properties.on_ground
      : null,
  };
}


function popupHtml(properties: AircraftPointProperties) {
  return aircraftPopupHtml({
    icao24: properties.icao24,
    callsign: properties.callsign,
    origin_country: properties.origin_country,
    baro_altitude_m: properties.altitude_m,
    velocity_mps: properties.velocity_mps,
    true_track_deg: properties.heading_deg,
    observed_at: properties.observed_at,
  });
}


/**
 * Rota noktalarından tek bir LineString üretir.
 * Renk geçişini ayrı segmentlerle değil, MapLibre line-gradient ile yapıyoruz.
 */
function routeToGeoJson(
  route: Aircraft[],
): FeatureCollection<LineString> {
  const coordinates = route
    .filter(hasValidPosition)
    .map((item) => [item.longitude, item.latitude]);

  return {
    type: "FeatureCollection",
    features: coordinates.length > 1
      ? [{
          type: "Feature",
          geometry: {
            type: "LineString",
            coordinates,
          },
          properties: {},
        }]
      : [],
  };
}


function routeGradientExpression(route: Aircraft[]) {
  const validRoute = route.filter(hasValidPosition);

  if (validRoute.length < 2) {
    return DEFAULT_ROUTE_GRADIENT;
  }

  const expression: unknown[] = [
    "interpolate",
    ["linear"],
    ["line-progress"],
  ];

  validRoute.forEach((item, index) => {
    const progress = validRoute.length === 1
      ? 0
      : index / (validRoute.length - 1);

    expression.push(progress, altitudeColor(item));
  });

  return expression as maplibregl.ExpressionSpecification;
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
  mapTheme,
  onSelectAircraft,
  onMapError,
}: MapLibreMapProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const popupRef = useRef<maplibregl.Popup | null>(null);
  const hoverPopupRef = useRef<maplibregl.Popup | null>(null);
  const hoverTimerRef = useRef<number | null>(null);
  const onSelectRef = useRef(onSelectAircraft);
  const onMapErrorRef = useRef(onMapError);
  const currentThemeRef = useRef<MapTheme>("light");
  const styleReadyRef = useRef(false);
  const [projectionMode, setProjectionMode] =
    useState<"mercator" | "globe">("mercator");
  const [styleRevision, setStyleRevision] = useState(0);

  // onSelectAircraft referansını güncel tut (closure tuzağı önlenir)
  useEffect(() => {
    onSelectRef.current = onSelectAircraft;
  }, [onSelectAircraft]);

  useEffect(() => {
    onMapErrorRef.current = onMapError;
  }, [onMapError]);

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

  const routeGradient = useMemo(
    () => routeGradientExpression(selectedRoute),
    [selectedRoute],
  );

  const routeGeoJsonRef = useRef(routeGeoJson);
  const routeEndpointsRef = useRef(routeEndpoints);
  const routeGradientRef = useRef(routeGradient);
  const projectionModeRef = useRef(projectionMode);

  useEffect(() => {
    routeGeoJsonRef.current = routeGeoJson;
  }, [routeGeoJson]);

  useEffect(() => {
    routeEndpointsRef.current = routeEndpoints;
  }, [routeEndpoints]);

  useEffect(() => {
    routeGradientRef.current = routeGradient;
  }, [routeGradient]);

  useEffect(() => {
    projectionModeRef.current = projectionMode;
  }, [projectionMode]);


  /* ================================================================ */
  /*  Harita başlatma (mount'ta bir kere)                             */
  /* ================================================================ */

  useEffect(() => {
    const container = containerRef.current;

    if (!container || mapRef.current) {
      return;
    }

    const supportCanvas = document.createElement("canvas");
    if (!supportCanvas.getContext("webgl2")) {
      onMapErrorRef.current(new Error("WebGL2 desteklenmiyor."));
      return;
    }

    let map: maplibregl.Map;
    try {
      map = new maplibregl.Map({
        container,
        style: MAPLIBRE_STYLES.light,
        center: INITIAL_CENTER,
        zoom: MERCATOR_ZOOM,
        minZoom: 1,
        maxZoom: 18,
      });
    } catch (error) {
      onMapErrorRef.current(
        error instanceof Error ? error : new Error("MapLibre başlatılamadı."),
      );
      return;
    }

    map.addControl(
      new maplibregl.NavigationControl({ visualizePitch: true }),
      "top-left",
    );

    mapRef.current = map;
    let interactionsBound = false;
    let failureReported = false;
    const canvas = map.getCanvas();
    const reportMapFailure = (error: Error) => {
      if (failureReported) {
        return;
      }

      failureReported = true;
      onMapErrorRef.current(error);
    };
    const handleMapError = (event: { error?: Error }) => {
      // Stil kurulduktan sonraki tekil raster tile hataları haritanın
      // tamamının bozulduğu anlamına gelmez. İlk stil kurulumu başarısızsa
      // Leaflet fallback devreye girer.
      if (!styleReadyRef.current) {
        reportMapFailure(
          event.error ?? new Error("MapLibre haritası yüklenemedi."),
        );
      }
    };
    const handleContextLost = (event: Event) => {
      event.preventDefault();
      reportMapFailure(new Error("WebGL bağlamı kayboldu."));
    };
    map.on("error", handleMapError);
    canvas.addEventListener("webglcontextlost", handleContextLost);

    map.on("style.load", () => {
      setStyleRevision((revision) => revision + 1);
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
          data: routeGeoJsonRef.current,
          lineMetrics: true,
        });
      }

      if (!map.getLayer("route-lines-layer")) {
        map.addLayer({
          id: "route-lines-layer",
          type: "line",
          source: "route-lines",
          paint: {
            "line-gradient": routeGradientRef.current,
            "line-width": 3.5,
            "line-opacity": 0.94,
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
          data: routeEndpointsRef.current,
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
              "ft-0", "aircraft-ft-0",
              "ft-500", "aircraft-ft-500",
              "ft-1000", "aircraft-ft-1000",
              "ft-2000", "aircraft-ft-2000",
              "ft-4000", "aircraft-ft-4000",
              "ft-6000", "aircraft-ft-6000",
              "ft-8000", "aircraft-ft-8000",
              "ft-10000", "aircraft-ft-10000",
              "ft-20000", "aircraft-ft-20000",
              "ft-30000", "aircraft-ft-30000",
              "ft-40000", "aircraft-ft-40000",
              "unknown", "aircraft-unknown",
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

      const clearHoverPopup = () => {
        if (hoverTimerRef.current !== null) {
          window.clearTimeout(hoverTimerRef.current);
          hoverTimerRef.current = null;
        }

        hoverPopupRef.current?.remove();
        hoverPopupRef.current = null;
      };

      map.setProjection({ type: projectionModeRef.current });

      if (interactionsBound) {
        styleReadyRef.current = true;
        return;
      }

      interactionsBound = true;

      /* ----- Etkileşim ----- */
      map.on("mouseenter", "aircraft-icons", (event) => {
        map.getCanvas().style.cursor = "pointer";

        const feature = event.features?.[0];
        const props = featurePropertiesToPopupProps(
          feature?.properties as Record<string, unknown> | undefined,
        );

        if (!feature || !props || feature.geometry.type !== "Point") {
          return;
        }

        const coordinates = feature.geometry.coordinates as [number, number];

        hoverTimerRef.current = window.setTimeout(() => {
          hoverPopupRef.current?.remove();
          hoverPopupRef.current = new maplibregl.Popup({
            closeButton: false,
            closeOnClick: false,
            offset: 14,
            className: "maplibre-aircraft-popup hover-popup",
          })
            .setLngLat(coordinates)
            .setHTML(popupHtml(props))
            .addTo(map);
        }, HOVER_POPUP_DELAY_MS);
      });

      map.on("mouseleave", "aircraft-icons", () => {
        map.getCanvas().style.cursor = "";
        clearHoverPopup();
      });

      map.on("click", "aircraft-icons", (event) => {
        const feature = event.features?.[0];
        const icao24 = feature?.properties?.icao24 as string | undefined;

        if (!icao24) {
          return;
        }

        clearHoverPopup();
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

      styleReadyRef.current = true;
    });

    return () => {
      if (hoverTimerRef.current !== null) {
        window.clearTimeout(hoverTimerRef.current);
      }
      hoverPopupRef.current?.remove();
      popupRef.current?.remove();
      map.off("error", handleMapError);
      canvas.removeEventListener("webglcontextlost", handleContextLost);
      try {
        map.remove();
      } catch {
        // Kısmen kurulmuş WebGL context temizliği fallback'i engellememeli.
      }
      mapRef.current = null;
      styleReadyRef.current = false;
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);


  /* ================================================================ */
  /*  Harita tema değişimi                                            */
  /* ================================================================ */

  useEffect(() => {
    const map = mapRef.current;

    if (!map) {
      return;
    }

    if (currentThemeRef.current === mapTheme) {
      return;
    }

    currentThemeRef.current = mapTheme;
    styleReadyRef.current = false;

    hoverPopupRef.current?.remove();
    hoverPopupRef.current = null;
    popupRef.current?.remove();
    popupRef.current = null;

    map.setStyle(MAPLIBRE_STYLES[mapTheme]);
  }, [mapTheme]);


  /* ================================================================ */
  /*  Projection değişimi                                             */
  /* ================================================================ */

  useEffect(() => {
    const map = mapRef.current;

    if (!map || !styleReadyRef.current) {
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

    if (!map || !styleReadyRef.current) {
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

    if (!map || !styleReadyRef.current) {
      return;
    }

    const lineSource =
      map.getSource("route-lines") as maplibregl.GeoJSONSource | undefined;
    const pointSource =
      map.getSource("route-endpoints") as maplibregl.GeoJSONSource | undefined;

    if (lineSource) {
      lineSource.setData(routeGeoJson);
    }

    if (map.getLayer("route-lines-layer")) {
      map.setPaintProperty(
        "route-lines-layer",
        "line-gradient",
        routeGradient,
      );
    }

    if (pointSource) {
      pointSource.setData(routeEndpoints);
    }
  }, [routeGeoJson, routeEndpoints, routeGradient]);


  /* ================================================================ */
  /*  Popup — seçili uçak                                            */
  /* ================================================================ */

  useEffect(() => {
    const map = mapRef.current;

    if (!map || !styleReadyRef.current) {
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
  }, [selectedAircraft, styleRevision]);


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

      <AltitudeLegend />
    </div>
  );
}
