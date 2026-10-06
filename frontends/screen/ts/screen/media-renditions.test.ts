import { describe, expect, it } from "vitest";
import { markRenditionMissing, pickTier, preferredUrl, renditionUrl } from "./media-renditions";

describe("pickTier — the next larger image than the screen resolution", () => {
  it("chooses the smallest tier that covers the screen's long edge", () => {
    expect(pickTier(800)).toBe("fhd");
    expect(pickTier(1366)).toBe("fhd");
    expect(pickTier(1920)).toBe("fhd"); // exactly FHD
    expect(pickTier(1921)).toBe("4k");
    expect(pickTier(2560)).toBe("4k");
    expect(pickTier(3840)).toBe("4k"); // exactly 4K
    expect(pickTier(3841)).toBe("8k");
    expect(pickTier(5120)).toBe("8k");
  });

  it("caps at 8K for anything bigger", () => {
    expect(pickTier(10000)).toBe("8k");
  });
});

describe("renditionUrl / preferredUrl", () => {
  it("maps uploaded media (incl. sub-folders and absolute URLs) to the tier folder", () => {
    expect(renditionUrl("/static/media/a.png", "4k")).toBe("/static/media_renditions/4k/a.png");
    expect(renditionUrl("/static/media/logos/b%20c.jpg", "fhd")).toBe("/static/media_renditions/fhd/logos/b%20c.jpg");
    expect(renditionUrl("https://signage.example/static/media/a.png", "8k")).toBe("/static/media_renditions/8k/a.png");
  });

  it("leaves everything that is not an uploaded image alone", () => {
    expect(renditionUrl("https://cdn.example/x.png")).toBeNull();
    expect(renditionUrl("/static/demo_logos/event.png")).toBeNull();
    expect(preferredUrl("https://cdn.example/x.png")).toBe("https://cdn.example/x.png");
  });

  it("falls back to the original once a rendition is known to be missing", () => {
    const original = "/static/media/small-source.png";
    const rendition = renditionUrl(original)!;
    expect(preferredUrl(original)).toBe(rendition);
    markRenditionMissing(rendition);
    expect(preferredUrl(original)).toBe(original);
  });
});
