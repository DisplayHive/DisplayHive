import { describe, expect, it } from "vitest";
import { staticCacheName, strategyFor, strategyForResource } from "./routing";

const ORIGIN = "http://screen.test";
const get = (path: string, over: Partial<{ method: string; mode: string; hasRange: boolean }> = {}) =>
  strategyFor({ method: "GET", url: ORIGIN + path, mode: "no-cors", hasRange: false, ...over }, ORIGIN);

describe("strategyFor", () => {
  it("serves the screen page network-first, but only the plain page", () => {
    expect(get("/", { mode: "navigate" })).toBe("page");
    expect(get("/?preview=true&content_id=3", { mode: "navigate" })).toBe("bypass");
    expect(get("/?impersonate=true", { mode: "navigate" })).toBe("bypass");
    expect(get("/admin/", { mode: "navigate" })).toBe("bypass");
    expect(get("/admin/login", { mode: "navigate" })).toBe("bypass");
  });

  it("caches the bundle, assets and logos", () => {
    expect(get("/dist/screen/screen.js?v=abc")).toBe("static");
    expect(get("/dist/screen/chunks/bb.es-1.js")).toBe("static");
    expect(get("/screen/assets/screen.css?v=abc")).toBe("static");
    expect(get("/logo_bl.png")).toBe("static");
    expect(get("/favicon.ico")).toBe("static");
  });

  it("caches uploaded media, previews and renditions", () => {
    expect(get("/static/media/a/b.png")).toBe("media");
    expect(get("/static/media_previews/b_preview.jpg")).toBe("media");
    expect(get("/static/media_renditions/fhd/b.png")).toBe("media");
  });

  it("leaves everything else alone", () => {
    expect(get("/socket.io/?EIO=4&transport=polling")).toBe("bypass");
    expect(get("/screen-sw.js?v=1")).toBe("bypass");
    expect(get("/admin/api/auth/me")).toBe("bypass");
    expect(get("/dist/admin/index.js")).toBe("bypass");
  });

  it("never touches writes, ranged requests (video seeking) or other origins", () => {
    expect(get("/static/media/v.mp4", { method: "POST" })).toBe("bypass");
    expect(get("/static/media/v.mp4", { hasRange: true })).toBe("bypass");
    expect(strategyFor({ method: "GET", url: "http://elsewhere.test/static/media/x.png", mode: "no-cors", hasRange: false }, ORIGIN)).toBe("bypass");
    expect(get("not a url")).toBe("bypass");
  });
});

describe("strategyForResource", () => {
  it("accepts the page and its static resources, not media", () => {
    expect(strategyForResource(ORIGIN + "/", ORIGIN, true)).toBe("page");
    expect(strategyForResource(ORIGIN + "/dist/screen/screen.js", ORIGIN, false)).toBe("static");
    expect(strategyForResource(ORIGIN + "/static/media/a.png", ORIGIN, false)).toBeNull();
    expect(strategyForResource(ORIGIN + "/socket.io/", ORIGIN, false)).toBeNull();
  });
});

describe("staticCacheName", () => {
  it("is named for the release", () => {
    expect(staticCacheName("1.2.3-abc")).toBe("dh-screen-static-1.2.3-abc");
  });
});
