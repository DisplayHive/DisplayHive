// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Scene } from "./types";

const scene = (id: number, containers: Record<string, string>): Scene =>
  ({
    id,
    title: `scene ${id}`,
    duration: 10,
    containers: Object.fromEntries(
      Object.entries(containers).map(([cid, html]) => [cid, { name: cid, top: 0, left: 0, width: 50, height: 50, html, css: "" }]),
    ),
  }) as unknown as Scene;

let finishAnimations: Array<() => void>;
let renderScene: (scene: Scene, inPlace?: boolean) => void;
let setTransitionConfig: (raw: unknown) => void;

beforeEach(async () => {
  // The container manager keeps its elements in module state: every test starts from a fresh module and page.
  vi.resetModules();
  ({ renderScene } = await import("./container-manager"));
  ({ setTransitionConfig } = await import("./transitions"));
  document.body.innerHTML = '<div id="scene-containers"></div>';
  finishAnimations = [];
  (Element.prototype as { animate?: unknown }).animate = function () {
    let done: () => void = () => {};
    const finished = new Promise<void>((resolve) => (done = resolve));
    finishAnimations.push(done);
    return { finished, cancel: () => {} };
  };
});

afterEach(() => {
  delete (Element.prototype as { animate?: unknown }).animate;
});

const contentElements = (id: string) => document.querySelectorAll(`[data-container-id="${id}"]`);

describe("transitions in the container manager", () => {
  it("keeps the old content in place while the new one comes in over it", () => {
    setTransitionConfig({ type: "fade" });
    renderScene(scene(1, { a: "<p>one</p>" }));
    expect(contentElements("a")).toHaveLength(1);
    renderScene(scene(2, { a: "<p>two</p>" }));
    const both = contentElements("a");
    expect(both).toHaveLength(2);
    expect(both[0].innerHTML).toBe("<p>one</p>");
    expect(both[1].innerHTML).toBe("<p>two</p>");
  });

  it("leaves unchanged content alone unless the Design asks to animate it too", () => {
    setTransitionConfig({ type: "fade" });
    renderScene(scene(1, { a: "<p>same</p>" }));
    const first = contentElements("a")[0];
    renderScene(scene(2, { a: "<p>same</p>" }));
    expect(contentElements("a")).toHaveLength(1);
    expect(contentElements("a")[0]).toBe(first);

    setTransitionConfig({ type: "fade", unchanged: true });
    renderScene(scene(3, { a: "<p>same</p>" }));
    expect(contentElements("a")).toHaveLength(2);
    expect(contentElements("a")[1].innerHTML).toBe("<p>same</p>");
  });

  it("animates content that appears and keeps it until the animation is over when it disappears", () => {
    setTransitionConfig({ type: "fade" });
    renderScene(scene(1, { a: "<p>one</p>" }));
    expect(finishAnimations).toHaveLength(1); // appearing
    renderScene(scene(2, { b: "<p>two</p>" }));
    expect(contentElements("a")[0].innerHTML).toBe("<p>one</p>"); // still there, leaving
    finishAnimations.forEach((done) => done());
  });

  it("does nothing special when no transition is set", () => {
    renderScene(scene(1, { a: "<p>one</p>" }));
    renderScene(scene(2, { a: "<p>two</p>" }));
    expect(contentElements("a")).toHaveLength(1);
    expect(finishAnimations).toHaveLength(0);
  });

  it("hides a container the scene does not use, so a border or background of the Design does not stay behind", () => {
    const slotOf = (id: string) => contentElements(id)[0].parentElement as HTMLElement;

    setTransitionConfig({ type: "fade" });
    renderScene(scene(1, { a: "<p>one</p>" }));
    renderScene(scene(2, { b: "<p>two</p>" }));
    expect(slotOf("a").style.display).toBe(""); // still leaving
    finishAnimations.forEach((done) => done());
    return Promise.resolve().then(() => Promise.resolve()).then(() => {
      expect(slotOf("a").style.display).toBe("none");
      expect(contentElements("a")[0].innerHTML).toBe("");
      renderScene(scene(3, { a: "<p>again</p>" }));
      expect(slotOf("a").style.display).toBe("");
    });
  });

  it("hides it at once when there is no transition", () => {
    renderScene(scene(1, { a: "<p>one</p>" }));
    renderScene(scene(2, { b: "<p>two</p>" }));
    expect((contentElements("a")[0].parentElement as HTMLElement).style.display).toBe("none");
    renderScene(scene(3, { a: "<p>again</p>" }));
    expect((contentElements("a")[0].parentElement as HTMLElement).style.display).toBe("");
  });

  it("updates what is showing in place, without animating again or cutting the running animation short", () => {
    setTransitionConfig({ type: "fade" });
    renderScene(scene(1, { a: "<p>stale</p>" }));
    const element = contentElements("a")[0];
    const started = finishAnimations.length;

    renderScene(scene(1, { a: "<p>fresh</p>" }), true); // e.g. the refreshed data of a Pretalx table
    expect(contentElements("a")).toHaveLength(1);
    expect(contentElements("a")[0]).toBe(element);
    expect(element.innerHTML).toBe("<p>fresh</p>");
    expect(finishAnimations.length).toBe(started); // no second animation
  });
});
