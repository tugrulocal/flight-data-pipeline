import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const MOCK_TILE = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=",
  "base64",
);

test.beforeEach(async ({ page }) => {
  const now = new Date().toISOString();
  // Testler public harita sunucularına istek göndermemeli.
  for (const url of ["https://tile.openstreetmap.org/**", "https://basemaps.cartocdn.com/**"]) {
    await page.route(url, (route) => route.fulfill({
      contentType: "image/png",
      body: MOCK_TILE,
    }));
  }

  await page.addInitScript(() => {
    class MockWebSocket extends EventTarget {
      static OPEN = 1;
      readyState = MockWebSocket.OPEN;
      onopen: ((event: Event) => void) | null = null;
      onmessage: ((event: MessageEvent) => void) | null = null;
      onerror: ((event: Event) => void) | null = null;
      onclose: ((event: CloseEvent) => void) | null = null;

      constructor(_url: string) {
        super();
        const sockets = (
          window as typeof window & { __flightSockets?: MockWebSocket[] }
        ).__flightSockets ?? [];
        sockets.push(this);
        Object.defineProperty(window, "__flightSockets", {
          configurable: true,
          value: sockets,
        });
        setTimeout(() => this.onopen?.(new Event("open")), 0);
      }

      close() {
        this.readyState = 3;
      }

      send(_data: string) {}
    }

    Object.defineProperty(window, "WebSocket", {
      configurable: true,
      value: MockWebSocket,
    });
  });

  await page.route("**/api/aircraft?*", (route) => route.fulfill({
    contentType: "application/json",
    body: JSON.stringify({
      count: 2,
      window_minutes: 20,
      truncated: false,
      items: [
        {
          _id: "4baa12",
          icao24: "4baa12",
          callsign: "THY123",
          origin_country: "Turkey",
          latitude: 41,
          longitude: 29,
          baro_altitude_m: null,
          geo_altitude_m: null,
          on_ground: false,
          velocity_mps: null,
          true_track_deg: null,
          vertical_rate_mps: null,
          observed_at: now,
          ingested_at: now,
          source: null,
          kafka_topic: null,
          kafka_partition: null,
          kafka_offset: null,
        },
        {
          _id: "4baa13",
          icao24: "4baa13",
          callsign: null,
          origin_country: "Turkey",
          latitude: 40,
          longitude: 30,
          baro_altitude_m: null,
          geo_altitude_m: null,
          on_ground: null,
          velocity_mps: null,
          true_track_deg: null,
          vertical_rate_mps: null,
          observed_at: now,
          ingested_at: now,
          source: null,
          kafka_topic: null,
          kafka_partition: null,
          kafka_offset: null,
        },
      ],
    }),
  }));
  await page.route("**/api/stats", (route) => route.fulfill({
    contentType: "application/json",
    body: JSON.stringify({
      total_aircraft: 2,
      airborne: 1,
      on_ground: 0,
      unknown_ground_state: 1,
      last_observed_at: now,
    }),
  }));
  await page.route("**/health", (route) => route.fulfill({
    contentType: "application/json",
    body: JSON.stringify({ status: "ok", version: "test" }),
  }));
  await page.route("**/api/aircraft/*/history?*", (route) => route.fulfill({
    contentType: "application/json",
    body: JSON.stringify({
      count: 2,
      items: [
        {
          _id: "route-1",
          icao24: "4baa12",
          callsign: "THY123",
          origin_country: "Turkey",
          latitude: 40.8,
          longitude: 28.8,
          baro_altitude_m: 7000,
          on_ground: false,
          observed_at: new Date(Date.now() - 60_000).toISOString(),
          ingested_at: new Date().toISOString(),
        },
        {
          _id: "route-2",
          icao24: "4baa12",
          callsign: "THY123",
          origin_country: "Turkey",
          latitude: 41,
          longitude: 29,
          baro_altitude_m: 8000,
          on_ground: false,
          observed_at: new Date().toISOString(),
          ingested_at: new Date().toISOString(),
        },
      ],
    }),
  }));
});


test("harita zemini hatası görünür olur ve uçuş verisi korunarak tekrar yüklenir", async ({ page }) => {
  let failTiles = true;
  let loadedTiles = 0;
  // Gerçek harita sunucusuna yük bindirmeden bağlantı hatasını taklit et.
  await page.route("https://tile.openstreetmap.org/**", async (route) => {
    if (failTiles) {
      await route.fulfill({ status: 503, body: "unavailable" });
    } else {
      loadedTiles += 1;
      await route.fulfill({ contentType: "image/png", body: MOCK_TILE });
    }
  });
  await page.goto("/");
  await expect(page.getByText("Harita zemininin bazı parçaları alınamadı.")).toBeVisible();
  await expect(page.getByText("Uyumluluk haritası aktif.")).toHaveCount(0);
  await page.getByRole("button", { name: "Operasyonlar" }).click();
  await page.getByRole("listitem").filter({ hasText: "THY123" }).click();
  await expect(page.getByText("2 nokta ile irtifa renkli rota")).toBeVisible();

  failTiles = false;
  await page.getByRole("button", { name: "Haritayı yeniden yükle" }).click();
  await expect.poll(() => loadedTiles).toBeGreaterThan(0);
  await expect(page.getByText("Harita zemininin bazı parçaları alınamadı.")).toHaveCount(0);
  await expect(page.getByText("2 nokta ile irtifa renkli rota")).toBeVisible();
  await expect(page.locator(".maplibregl-popup")).toBeVisible();
});

test("snapshot, arama, null ground state ve otomatik fallback", async ({ page }) => {
  await page.addInitScript(() => {
    const original = HTMLCanvasElement.prototype.getContext;
    HTMLCanvasElement.prototype.getContext = function (type, ...args) {
      if (String(type).toLowerCase().includes("webgl")) {
        return null;
      }
      return original.call(this, type, ...args);
    } as typeof original;
  });

  await page.goto("/");

  await expect(page.getByRole("heading", { name: "Flight Pulse" })).toBeVisible();
  await expect(page.getByText("THY123", { exact: true })).toBeVisible();
  await expect(page.getByText("Bilinmiyor", { exact: true })).toBeVisible();
  await expect(page.getByText("Uyumluluk haritası aktif.")).toBeVisible();
  await expect(page.getByRole("button", { name: "WebGL'i tekrar dene" })).toBeVisible();

  const operationsToggle = page.getByRole("button", { name: "Operasyonlar" });
  await expect(operationsToggle).toHaveAttribute("aria-expanded", "false");
  await operationsToggle.click();
  await expect(page.locator("#operations-panel")).toContainText("THY123");
  await page.getByRole("button", { name: "Operasyon listesini kapat" }).click();
  await expect(page.getByRole("button", { name: "Operasyonlar" }))
    .toHaveAttribute("aria-expanded", "false");

  const search = page.getByPlaceholder("Uçuş, ICAO24 veya ülke ara");
  await expect(page.locator(".search-icon")).toBeVisible();

  const metrics = page.locator(".map-metrics");
  if (await metrics.isVisible()) {
    const searchBox = await search.boundingBox();
    const metricsBox = await metrics.boundingBox();

    expect(searchBox).not.toBeNull();
    expect(metricsBox).not.toBeNull();
    expect(Math.abs(searchBox!.x - metricsBox!.x)).toBeLessThanOrEqual(1);
    expect(Math.abs(searchBox!.width - metricsBox!.width)).toBeLessThanOrEqual(1);
    expect(metricsBox!.y - (searchBox!.y + searchBox!.height)).toBeLessThanOrEqual(9);
  }

  await search.fill("THY123");
  await expect(page.getByText("4baa13", { exact: true })).toHaveCount(0);

  const seriousViolations = (await new AxeBuilder({ page }).analyze())
    .violations.filter((item) => ["critical", "serious"].includes(item.impact ?? ""));
  expect(seriousViolations).toEqual([]);
});


test("tema seçili uçak ve rotayı korur; WebSocket yeniden bağlanır", async ({ page }) => {
  await page.goto("/");

  await expect(page.getByText("Uyumluluk haritası aktif.")).toHaveCount(0);
  await page.getByRole("button", { name: "Operasyonlar" }).click();
  await page.getByRole("listitem").filter({ hasText: "THY123" }).click();
  await expect(page.getByText("2 nokta ile irtifa renkli rota")).toBeVisible();
  await expect(page.locator(".maplibregl-popup")).toBeVisible();

  await page.getByRole("button", { name: "Koyu harita teması" }).click();
  await expect(page.getByText("2 nokta ile irtifa renkli rota")).toBeVisible();
  await expect(page.locator(".maplibregl-popup")).toBeVisible();

  await page.evaluate(() => {
    const sockets = (
      window as typeof window & {
        __flightSockets?: Array<{
          onclose: ((event: CloseEvent) => void) | null;
        }>;
      }
    ).__flightSockets;
    sockets?.at(-1)?.onclose?.(new CloseEvent("close"));
  });

  const connectionState = page.locator(".connection-pill strong");
  await expect(connectionState)
    .toHaveText("Yeniden bağlanıyor");
  await expect(connectionState)
    .toBeVisible();
  await expect(connectionState)
    .toHaveText("Canlı", { timeout: 3_000 });
});
