import { describe, expect, it } from "vitest";
import { RECONNECT_MAX_MS, reconnectDelay, reconnectionOptions } from "./reconnect";

describe("reconnectDelay", () => {
  it("doubles from one second up to the cap", () => {
    const at = (n: number) => reconnectDelay(n, 0.5); // random 0.5 = no jitter
    expect([0, 1, 2, 3, 4].map(at)).toEqual([1000, 2000, 4000, 8000, 16000]);
    expect(at(5)).toBe(RECONNECT_MAX_MS);
    expect(at(50)).toBe(RECONNECT_MAX_MS);
  });

  it("varies by a quarter either way, so screens spread out", () => {
    expect(reconnectDelay(2, 0)).toBe(3000);
    expect(reconnectDelay(2, 0.999999)).toBe(5000);
  });

  it("treats a negative attempt like the first", () => {
    expect(reconnectDelay(-3, 0.5)).toBe(1000);
  });
});

describe("reconnectionOptions", () => {
  it("retries forever with the same backoff", () => {
    expect(reconnectionOptions()).toMatchObject({
      reconnection: true,
      reconnectionAttempts: Infinity,
      reconnectionDelay: 1000,
      reconnectionDelayMax: 30000,
    });
  });
});
