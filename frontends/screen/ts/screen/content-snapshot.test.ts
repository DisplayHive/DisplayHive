// @vitest-environment jsdom
import { beforeEach, describe, expect, it } from "vitest";
import { loadContentSnapshot, saveContentSnapshot } from "./content-snapshot";
import { getContentSnapshot, setContentSnapshot } from "./storage";
import type { UpdContentMessage } from "./types";

const message = (): UpdContentMessage => ({ server_time: "2026-10-10T00:00:00Z", scenes: [{ id: 1, duration: 5, containers: {} } as never] });

describe("content snapshot", () => {
  beforeEach(() => setContentSnapshot(""));

  it("round-trips the content of the same device, without the server time", () => {
    saveContentSnapshot("key-1", message());
    const loaded = loadContentSnapshot("key-1");
    expect(loaded?.scenes).toHaveLength(1);
    expect(loaded?.server_time).toBeUndefined();
  });

  it("is only for the device that saved it", () => {
    saveContentSnapshot("key-1", message());
    expect(loadContentSnapshot("key-2")).toBeNull();
    expect(loadContentSnapshot(null)).toBeNull();
  });

  it("ignores damaged data", () => {
    setContentSnapshot("{not json");
    expect(loadContentSnapshot("key-1")).toBeNull();
    setContentSnapshot(JSON.stringify({ deviceKey: "key-1", message: { scenes: "no" } }));
    expect(loadContentSnapshot("key-1")).toBeNull();
  });

  it("keeps nothing for a preview or an impersonation page", () => {
    window.history.pushState({}, "", "/?preview=true&content_id=3");
    saveContentSnapshot("key-1", message());
    expect(getContentSnapshot()).toBeFalsy();
    window.history.pushState({}, "", "/");
    saveContentSnapshot("key-1", message());
    window.history.pushState({}, "", "/?impersonate=true");
    expect(loadContentSnapshot("key-1")).toBeNull();
    window.history.pushState({}, "", "/");
  });
});
