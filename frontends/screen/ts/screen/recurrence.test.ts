import { describe, expect, it } from "vitest";
import { isInWindows, minutesToNextBoundary, weekMinute, type WeeklyWindow } from "./recurrence";

// 2026-10-12 is a Monday. Berlin is UTC+2 then (summer time until 2026-10-25).
const at = (iso: string) => new Date(iso);
const office: WeeklyWindow[] = [{ days: [1, 2, 3, 4, 5], from: "08:00", to: "18:00" }];

describe("weekMinute", () => {
  it("counts from Monday 00:00 in the given time zone", () => {
    expect(weekMinute(at("2026-10-12T00:00:00Z"), "UTC")).toBe(0);
    expect(weekMinute(at("2026-10-12T06:30:00Z"), "Europe/Berlin")).toBe(8 * 60 + 30);
    expect(weekMinute(at("2026-10-18T22:30:00Z"), "Europe/Berlin")).toBe(0 * 24 * 60 + 30); // Sunday 22:30 UTC = Monday 00:30 Berlin
  });
});

describe("isInWindows", () => {
  it("is always true without windows", () => {
    expect(isInWindows([], at("2026-10-12T12:00:00Z"), "UTC")).toBe(true);
    expect(isInWindows(undefined, at("2026-10-12T12:00:00Z"), "UTC")).toBe(true);
  });

  it("is true only on the listed days, between from (inclusive) and to (exclusive)", () => {
    expect(isInWindows(office, at("2026-10-12T08:00:00Z"), "UTC")).toBe(true);
    expect(isInWindows(office, at("2026-10-12T17:59:59Z"), "UTC")).toBe(true);
    expect(isInWindows(office, at("2026-10-12T18:00:00Z"), "UTC")).toBe(false);
    expect(isInWindows(office, at("2026-10-12T07:59:00Z"), "UTC")).toBe(false);
    expect(isInWindows(office, at("2026-10-17T12:00:00Z"), "UTC")).toBe(false); // Saturday
  });

  it("reads the times in the time zone", () => {
    // 06:30 UTC is 08:30 in Berlin: inside; 17:00 UTC is 19:00 in Berlin: outside
    expect(isInWindows(office, at("2026-10-12T06:30:00Z"), "Europe/Berlin")).toBe(true);
    expect(isInWindows(office, at("2026-10-12T17:00:00Z"), "Europe/Berlin")).toBe(false);
  });

  it("a window that ends before it starts runs past midnight, also over the end of the week", () => {
    const night: WeeklyWindow[] = [{ days: [5, 7], from: "22:00", to: "02:00" }];
    expect(isInWindows(night, at("2026-10-16T23:00:00Z"), "UTC")).toBe(true); // Friday 23:00
    expect(isInWindows(night, at("2026-10-17T01:30:00Z"), "UTC")).toBe(true); // Saturday 01:30
    expect(isInWindows(night, at("2026-10-17T02:00:00Z"), "UTC")).toBe(false);
    expect(isInWindows(night, at("2026-10-12T01:30:00Z"), "UTC")).toBe(true); // Monday 01:30, from Sunday 22:00
    expect(isInWindows(night, at("2026-10-13T01:30:00Z"), "UTC")).toBe(false);
  });

  it("does not hide content because of unusable windows", () => {
    expect(isInWindows([{ days: [1], from: "nope", to: "18:00" }], at("2026-10-12T12:00:00Z"), "UTC")).toBe(true);
  });
});

describe("minutesToNextBoundary", () => {
  it("is null without windows", () => {
    expect(minutesToNextBoundary([], at("2026-10-12T12:00:00Z"), "UTC")).toBeNull();
  });

  it("is the time to the next start or end", () => {
    expect(minutesToNextBoundary(office, at("2026-10-12T07:00:00Z"), "UTC")).toBe(60); // start 08:00
    expect(minutesToNextBoundary(office, at("2026-10-12T17:30:00Z"), "UTC")).toBe(30); // end 18:00
    // Friday evening: next is Monday 08:00
    expect(minutesToNextBoundary(office, at("2026-10-16T19:00:00Z"), "UTC")).toBe(2 * 24 * 60 + 13 * 60);
  });
});
