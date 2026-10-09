import { describe, expect, it } from "vitest";
import { clockIn, isDue, parseTime } from "./scheduled-reload";

describe("parseTime", () => {
  it("reads HH:MM, nothing else", () => {
    expect(parseTime("04:00")).toBe(240);
    expect(parseTime(" 23:59 ")).toBe(1439);
    expect(parseTime("00:00")).toBe(0);
    for (const bad of ["", null, undefined, "4:00", "24:00", "12:60", "noon"]) expect(parseTime(bad)).toBeNull();
  });
});

describe("clockIn", () => {
  const instant = new Date("2026-10-10T22:30:00Z");
  it("reads the time in the given zone", () => {
    expect(clockIn(instant, "UTC")).toEqual({ day: "2026-10-10", minutes: 22 * 60 + 30 });
    // Berlin is UTC+2 in October: already the next day
    expect(clockIn(instant, "Europe/Berlin")).toEqual({ day: "2026-10-11", minutes: 30 });
  });
  it("falls back to the local zone for an unknown one", () => {
    expect(() => clockIn(instant, "Not/AZone")).not.toThrow();
  });
});

describe("isDue", () => {
  const at = (iso: string) => new Date(iso);
  it("is due once the time has passed and today's reload has not happened", () => {
    expect(isDue(at("2026-10-10T03:59:00Z"), "UTC", 240, null)).toBe(false);
    expect(isDue(at("2026-10-10T04:00:00Z"), "UTC", 240, null)).toBe(true);
    expect(isDue(at("2026-10-10T09:00:00Z"), "UTC", 240, "2026-10-09")).toBe(true);
  });
  it("is not due again on the same day", () => {
    expect(isDue(at("2026-10-10T04:05:00Z"), "UTC", 240, "2026-10-10")).toBe(false);
    expect(isDue(at("2026-10-11T04:00:00Z"), "UTC", 240, "2026-10-10")).toBe(true);
  });
});
