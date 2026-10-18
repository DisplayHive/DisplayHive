// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  beginSceneTransition, chooseTransition, computeStagger, CONCRETE_TYPES, EFFORT, getTransitionConfig, playTransition,
  setTransitionConfig, transitionWanted,
} from "./transitions";

afterEach(() => {
  setTransitionConfig(null);
  vi.unstubAllGlobals();
  delete (Element.prototype as { animate?: unknown }).animate;
});

describe("the transition config", () => {
  it("ignores what it does not know", () => {
    setTransitionConfig({ type: "explode", direction: "sideways", duration_ms: "fast" });
    expect(getTransitionConfig()).toEqual({ type: "none", direction: "left", durationMs: 600, sequential: false, unchanged: false, scope: "container", stagger: "none" });
    setTransitionConfig(null);
    expect(getTransitionConfig().type).toBe("none");
  });

  it("takes a known type, direction and a duration of at most five seconds", () => {
    setTransitionConfig({ type: "slide", direction: "up", duration_ms: 90000 });
    expect(getTransitionConfig()).toEqual({ type: "slide", direction: "up", durationMs: 5000, sequential: false, unchanged: false, scope: "container", stagger: "none" });
  });

  it("is only wanted with a type and a browser that can animate", () => {
    setTransitionConfig({ type: "fade", direction: "left", duration_ms: 400 });
    expect(transitionWanted()).toBe(false); // jsdom cannot animate
    (Element.prototype as { animate?: unknown }).animate = () => ({});
    expect(transitionWanted()).toBe(true);
    setTransitionConfig({ type: "none" });
    expect(transitionWanted()).toBe(false);
  });
});

describe("playing a transition", () => {
  const fakeAnimation = () => {
    let finish: () => void = () => {};
    const finished = new Promise<void>((resolve) => (finish = resolve));
    return { animation: { finished, cancel: vi.fn() }, finish };
  };

  it("animates both elements and calls finish once, however it ends", async () => {
    const out = fakeAnimation();
    const entering = fakeAnimation();
    const leavingEl = document.createElement("div");
    const enteringEl = document.createElement("div");
    (leavingEl as { animate: unknown }).animate = vi.fn().mockReturnValue(out.animation);
    (enteringEl as { animate: unknown }).animate = vi.fn().mockReturnValue(entering.animation);
    setTransitionConfig({ type: "slide", direction: "left", duration_ms: 500 });
    const finish = vi.fn();

    const end = playTransition(leavingEl, enteringEl, finish);
    out.finish();
    entering.finish();
    await Promise.resolve();
    await Promise.resolve();
    end();
    expect(finish).toHaveBeenCalledTimes(1);
    expect(out.animation.cancel).toHaveBeenCalled();
  });

  it("only animates the entering element for a cover, and puts the old one on top for a reveal", () => {
    const leavingEl = document.createElement("div");
    const enteringEl = document.createElement("div");
    const leavingAnimate = vi.fn().mockReturnValue(fakeAnimation().animation);
    (leavingEl as { animate: unknown }).animate = leavingAnimate;
    const enteringAnimate = vi.fn().mockReturnValue(fakeAnimation().animation);
    (enteringEl as { animate: unknown }).animate = enteringAnimate;

    setTransitionConfig({ type: "cover", direction: "left" });
    playTransition(leavingEl, enteringEl, () => {})();
    expect(leavingAnimate).not.toHaveBeenCalled();
    expect(enteringAnimate).toHaveBeenCalledTimes(1);

    setTransitionConfig({ type: "reveal", direction: "left" });
    playTransition(leavingEl, enteringEl, () => {});
    expect(leavingEl.style.zIndex).toBe("1");
  });

  it("animates content that appears on its own and content that disappears on its own", () => {
    const el = document.createElement("div");
    const animate = vi.fn().mockReturnValue(fakeAnimation().animation);
    (el as { animate: unknown }).animate = animate;

    for (const type of ["fade", "slide", "cover", "reveal", "zoom-in", "zoom-out", "wipe", "circle"]) {
      setTransitionConfig({ type, direction: "left" });
      animate.mockClear();
      playTransition(null, el, () => {})(); // appears
      expect(animate, `appearing ${type}`).toHaveBeenCalledTimes(1);
      animate.mockClear();
      playTransition(el, null, () => {})(); // disappears
      expect(animate, `disappearing ${type}`).toHaveBeenCalledTimes(1);
    }
  });

  it("finishes at once when there is nothing to animate", () => {
    setTransitionConfig({ type: "fade" });
    const finish = vi.fn();
    playTransition(null, null, finish);
    expect(finish).toHaveBeenCalledTimes(1);
  });

  it("uses one random transition for everything in a scene change, or one per container", () => {
    const frames = (animate: ReturnType<typeof vi.fn>) => JSON.stringify(animate.mock.calls[0][0]);
    const container = () => {
      const el = document.createElement("div");
      const animate = vi.fn().mockReturnValue(fakeAnimation().animation);
      (el as { animate: unknown }).animate = animate;
      return { el, animate };
    };
    const picks = (type: string) => {
      setTransitionConfig({ type });
      beginSceneTransition();
      return Array.from({ length: 12 }, () => {
        const c = container();
        playTransition(null, c.el, () => {})();
        return frames(c.animate);
      });
    };
    expect(new Set(picks("random")).size).toBe(1);
    expect(new Set(picks("random-container")).size).toBeGreaterThan(1);
    // the next scene change picks again
    const seen = new Set<string>();
    for (let i = 0; i < 30; i++) seen.add(picks("random")[0]);
    expect(seen.size).toBeGreaterThan(1);
  });

  it("in sequential mode the old content leaves in the first half and the new one comes in in the second", () => {
    const leavingEl = document.createElement("div");
    const enteringEl = document.createElement("div");
    const leavingAnimate = vi.fn().mockReturnValue(fakeAnimation().animation);
    const enteringAnimate = vi.fn().mockReturnValue(fakeAnimation().animation);
    (leavingEl as { animate: unknown }).animate = leavingAnimate;
    (enteringEl as { animate: unknown }).animate = enteringAnimate;

    for (const type of ["fade", "slide", "cover", "reveal", "zoom-in", "wipe", "circle"]) {
      setTransitionConfig({ type, direction: "left", duration_ms: 800, sequential: true });
      leavingAnimate.mockClear();
      enteringAnimate.mockClear();
      playTransition(leavingEl, enteringEl, () => {})();
      expect(leavingAnimate.mock.calls[0][1], type).toMatchObject({ duration: 400 });
      expect(leavingAnimate.mock.calls[0][1].delay, type).toBeUndefined();
      expect(enteringAnimate.mock.calls[0][1], type).toMatchObject({ duration: 400, delay: 400 });
    }
  });

  it("plays the outro alone, holds it until it is ended, and the intro alone without delay", async () => {
    setTransitionConfig({ type: "slide", direction: "left", duration_ms: 800, sequential: true });
    const out = fakeAnimation();
    const oldEl = document.createElement("div");
    const oldAnimate = vi.fn().mockReturnValue(out.animation);
    (oldEl as { animate: unknown }).animate = oldAnimate;
    const finish = vi.fn();

    const end = playTransition(oldEl, null, finish, { phase: "out" });
    expect(oldAnimate.mock.calls[0][1]).toMatchObject({ duration: 400, fill: "both" });
    out.finish();
    await Promise.resolve();
    await Promise.resolve();
    expect(finish).not.toHaveBeenCalled(); // held in its final state
    expect(out.animation.cancel).not.toHaveBeenCalled();
    end();
    expect(finish).toHaveBeenCalledTimes(1);
    expect(out.animation.cancel).toHaveBeenCalled();

    const newEl = document.createElement("div");
    const newAnimate = vi.fn().mockReturnValue(fakeAnimation().animation);
    (newEl as { animate: unknown }).animate = newAnimate;
    playTransition(null, newEl, () => {}, { phase: "in" })();
    expect(newAnimate.mock.calls[0][1]).toMatchObject({ duration: 400 });
    expect(newAnimate.mock.calls[0][1].delay).toBeUndefined();
  });

  it("clips the container's box only along the movement, and never for fades, zooms and wipes", () => {
    const clipOf = (type: string, direction: string) => {
      setTransitionConfig({ type, direction });
      const slot = document.createElement("div");
      const el = document.createElement("div");
      (el as { animate: unknown }).animate = vi.fn().mockReturnValue(fakeAnimation().animation);
      const end = playTransition(null, el, () => {}, { slot });
      const during = slot.style.clipPath;
      end();
      expect(slot.style.clipPath).toBe(""); // given back
      return during;
    };
    expect(clipOf("slide", "left")).toBe("inset(-100vmax 0 -100vmax 0)"); // horizontal: top and bottom stay open
    expect(clipOf("cover", "down")).toBe("inset(0 -100vmax 0 -100vmax)"); // vertical: left and right stay open
    for (const type of ["fade", "zoom-in", "zoom-out", "wipe", "circle"]) expect(clipOf(type, "left"), type).toBe("");
  });

  it("ends by itself when the browser never reports the animation as finished", () => {
    vi.useFakeTimers();
    setTransitionConfig({ type: "fade", duration_ms: 500 });
    const stuck = { finished: new Promise<void>(() => {}), cancel: vi.fn() };
    const leavingEl = document.createElement("div");
    const enteringEl = document.createElement("div");
    (leavingEl as { animate: unknown }).animate = vi.fn().mockReturnValue(stuck);
    (enteringEl as { animate: unknown }).animate = vi.fn().mockReturnValue(stuck);
    const finish = vi.fn();
    playTransition(leavingEl, enteringEl, finish);
    vi.advanceTimersByTime(700);
    expect(finish).not.toHaveBeenCalled();
    vi.advanceTimersByTime(100);
    expect(finish).toHaveBeenCalledTimes(1);
    vi.useRealTimers();
  });

  describe("an effect across the whole slide", () => {
    // A container at (200, 100), 400 x 300, on a 1920 x 1080 stage.
    const geometry = { left: 200, top: 100, width: 400, height: 300, stageWidth: 1920, stageHeight: 1080 };
    const framesOf = (type: string, direction: string, side: "leaving" | "entering") => {
      vi.stubGlobal("CSS", { supports: () => true }); // jsdom does not know clip-path
      setTransitionConfig({ type, direction, scope: "slide" });
      const slot = document.createElement("div");
      const leavingEl = document.createElement("div");
      const enteringEl = document.createElement("div");
      const leavingAnimate = vi.fn().mockReturnValue(fakeAnimation().animation);
      const enteringAnimate = vi.fn().mockReturnValue(fakeAnimation().animation);
      (leavingEl as { animate: unknown }).animate = leavingAnimate;
      (enteringEl as { animate: unknown }).animate = enteringAnimate;
      playTransition(leavingEl, enteringEl, () => {}, { slot, geometry })();
      expect(slot.style.clipPath).toBe(""); // nothing is clipped to the container's own box
      return (side === "leaving" ? leavingAnimate : enteringAnimate).mock.calls[0]?.[0];
    };

    it("moves every container by the size of the screen, so the whole slide travels as one", () => {
      expect(framesOf("slide", "left", "leaving")[1].transform).toBe("translate(-1920px, 0px)");
      expect(framesOf("slide", "left", "entering")[0].transform).toBe("translate(1920px, 0px)");
      expect(framesOf("slide", "down", "leaving")[1].transform).toBe("translate(0px, 1080px)");
    });

    it("zooms and opens the circle around the middle of the screen, seen from the container", () => {
      expect(framesOf("zoom-in", "left", "entering")[0].transformOrigin).toBe("760px 440px");
      const circle = framesOf("circle", "left", "entering") as Array<{ clipPath: string }>;
      expect(circle[0].clipPath).toBe("circle(0px at 760px 440px)");
      expect(circle[1].clipPath).toMatch(/^circle\(11\d\d(\.\d+)?px at 760px 440px\)$/); // reaches the corners: half the diagonal
    });

    it("wipes with one front across the screen", () => {
      const right = framesOf("wipe", "right", "entering") as Array<{ clipPath: string }>;
      expect(right[0].clipPath).toBe("inset(-100vmax 600px -100vmax -100vmax)"); // front at the left edge of the screen
      expect(right[1].clipPath).toBe("inset(-100vmax -1320px -100vmax -100vmax)"); // front past the right edge
    });
  });
});

describe("all effects", () => {
  const geometry = { left: 200, top: 100, width: 400, height: 300, stageWidth: 1920, stageHeight: 1080 };
  const element = () => {
    const el = document.createElement("div");
    const animate = vi.fn().mockReturnValue({ finished: new Promise<void>(() => {}), cancel: vi.fn() });
    (el as { animate: unknown }).animate = animate;
    return { el, animate };
  };

  it("every effect plays in each direction and scope, replacing, appearing and disappearing", () => {
    vi.stubGlobal("CSS", { supports: () => true });
    const directions = ["left", "right", "up", "down"];
    for (const type of CONCRETE_TYPES) {
      for (const direction of directions) {
        for (const scope of ["container", "slide"]) {
          setTransitionConfig({ type, direction, scope });
          const options = scope === "slide" ? { geometry, size: { width: 400, height: 300 } } : { size: { width: 400, height: 300 } };
          const label = `${type} ${direction} ${scope}`;
          const a = element();
          const b = element();
          playTransition(a.el, b.el, () => {}, options)();
          expect(a.animate.mock.calls.length + b.animate.mock.calls.length, `${label} replacing`).toBeGreaterThan(0);
          const appearing = element();
          playTransition(null, appearing.el, () => {}, options)();
          expect(appearing.animate, `${label} appearing`).toHaveBeenCalledTimes(1);
          const leaving = element();
          playTransition(leaving.el, null, () => {}, options)();
          expect(leaving.animate, `${label} disappearing`).toHaveBeenCalledTimes(1);
          // keyframes are well formed: at least two, every value a string or number
          for (const call of [...a.animate.mock.calls, ...b.animate.mock.calls]) {
            const frames = call[0] as Array<Record<string, unknown>>;
            expect(frames.length, label).toBeGreaterThanOrEqual(2);
            for (const frame of frames) for (const value of Object.values(frame)) expect(["string", "number"], label).toContain(typeof value);
          }
        }
      }
    }
  });

  it("falls back to a fade where the browser cannot do what an effect needs", () => {
    vi.stubGlobal("CSS", { supports: () => false });
    for (const type of CONCRETE_TYPES.filter((t) => EFFORT[t] !== "light")) {
      setTransitionConfig({ type });
      expect(chooseTransition().type, type).toBe("fade");
    }
    setTransitionConfig({ type: "slide" });
    expect(chooseTransition().type).toBe("slide");
  });

  it("limits the random types by effort", () => {
    vi.stubGlobal("CSS", { supports: () => true });
    let seed = 12345;
    vi.spyOn(Math, "random").mockImplementation(() => (seed = (seed * 1664525 + 1013904223) % 4294967296) / 4294967296);
    // the per-container types draw every time; the per-scene ones draw once per scene change
    const seen = (type: string) => {
      setTransitionConfig({ type });
      beginSceneTransition();
      const efforts = new Set<string>();
      for (let i = 0; i < 400; i++) efforts.add(EFFORT[chooseTransition().type]);
      return efforts;
    };
    const perScene = (type: string) => {
      setTransitionConfig({ type });
      const efforts = new Set<string>();
      for (let i = 0; i < 400; i++) {
        beginSceneTransition();
        efforts.add(EFFORT[chooseTransition().type]);
      }
      return efforts;
    };
    expect([...seen("random-container-light")]).toEqual(["light"]);
    expect([...seen("random-container-medium")].sort()).toEqual(["light", "medium"]);
    expect([...seen("random-container")].sort()).toEqual(["heavy", "light", "medium"]);
    expect([...perScene("random-light")]).toEqual(["light"]);
    expect([...perScene("random-medium")].sort()).toEqual(["light", "medium"]);
    expect([...perScene("random")].sort()).toEqual(["heavy", "light", "medium"]);
    vi.restoreAllMocks();
  });

  it("orders containers for a stagger", () => {
    const boxes = [
      { id: "a", top: 0, left: 0, width: 20, height: 20 },
      { id: "b", top: 40, left: 40, width: 20, height: 20 },
      { id: "c", top: 80, left: 80, width: 20, height: 20 },
    ];
    setTransitionConfig({ type: "fade", stagger: "none" });
    expect(computeStagger(boxes)).toEqual({});
    setTransitionConfig({ type: "fade", stagger: "top-bottom" });
    expect(computeStagger(boxes)).toEqual({ a: 0, b: 0.5, c: 1 });
    setTransitionConfig({ type: "fade", stagger: "centre-out" });
    const ranks = computeStagger(boxes);
    expect(ranks.b).toBe(0);
    expect(ranks.a).toBe(1);
    expect(ranks.c).toBe(1);
    setTransitionConfig({ type: "fade", stagger: "order" });
    expect(computeStagger(boxes)).toEqual({ a: 0, b: 0.5, c: 1 });
    setTransitionConfig({ type: "fade", stagger: "random" });
    expect(Object.keys(computeStagger(boxes)).sort()).toEqual(["a", "b", "c"]);
  });

  it("a staggered container starts later and runs shorter, the last one still ends with the transition", () => {
    setTransitionConfig({ type: "fade", duration_ms: 1000 });
    const first = element();
    const last = element();
    playTransition(null, first.el, () => {}, { stagger: 0 })();
    playTransition(null, last.el, () => {}, { stagger: 1 })();
    expect(first.animate.mock.calls[0][1]).toMatchObject({ duration: 600 });
    expect(first.animate.mock.calls[0][1].delay).toBeUndefined();
    expect(last.animate.mock.calls[0][1]).toMatchObject({ duration: 600, delay: 400 });
  });
});
