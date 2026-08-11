import { describe, expect, it } from "vitest";

import type { Aircraft } from "../types";
import {
  isNewerAircraftUpdate,
  isRecentlyObserved,
  mergeAircraftUpdate,
} from "./useAircraftFeed";


function aircraft(
  observedAt: string,
  kafkaOffset: number,
): Aircraft {
  return {
    _id: "4baa12",
    icao24: "4baa12",
    callsign: "THY123",
    origin_country: "Turkey",
    latitude: 41,
    longitude: 29,
    baro_altitude_m: 8000,
    geo_altitude_m: 8200,
    on_ground: false,
    velocity_mps: 220,
    true_track_deg: 90,
    vertical_rate_mps: 0,
    observed_at: observedAt,
    ingested_at: observedAt,
    source: "test",
    kafka_topic: "raw",
    kafka_partition: 0,
    kafka_offset: kafkaOffset,
  };
}


describe("isNewerAircraftUpdate", () => {
  it("daha eski realtime olayının snapshot'ı ezmesini önler", () => {
    const snapshot = aircraft("2026-01-01T10:00:00Z", 100);
    const oldRealtime = aircraft("2026-01-01T09:59:00Z", 99);
    expect(isNewerAircraftUpdate(snapshot, oldRealtime)).toBe(false);
  });

  it("aynı gözlem zamanında yüksek Kafka offset'ini kabul eder", () => {
    const current = aircraft("2026-01-01T10:00:00Z", 100);
    const update = aircraft("2026-01-01T10:00:00Z", 101);
    expect(isNewerAircraftUpdate(current, update)).toBe(true);
  });

  it("mevcut kayıt yoksa mesajı kabul eder", () => {
    expect(
      isNewerAircraftUpdate(
        undefined,
        aircraft("2026-01-01T10:00:00Z", 1),
      ),
    ).toBe(true);
  });
});


describe("isRecentlyObserved", () => {
  it("null ve süresi geçmiş gözlemleri canlı kabul etmez", () => {
    const now = new Date("2026-01-01T10:20:00Z").getTime();
    expect(isRecentlyObserved(null, now, 10 * 60 * 1000)).toBe(false);
    expect(
      isRecentlyObserved("2026-01-01T10:00:00Z", now, 10 * 60 * 1000),
    ).toBe(false);
  });
});


describe("mergeAircraftUpdate", () => {
  it("aynı render karesinde yeni event'ten sonra gelen eski event'i reddeder", () => {
    const pending = new Map<string, Aircraft>();
    const newest = aircraft("2026-01-01T10:01:00Z", 101);
    const older = aircraft("2026-01-01T10:00:00Z", 100);
    mergeAircraftUpdate(pending, newest);
    mergeAircraftUpdate(pending, older);
    expect(pending.get("4baa12")).toEqual(newest);
  });
});
