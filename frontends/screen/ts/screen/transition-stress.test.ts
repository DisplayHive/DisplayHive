// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Scene } from "./types";

const scene = (id: number, containers: Record<string, string>): Scene =>
  ({
    id, title: `s${id}`, duration: 10,
    containers: Object.fromEntries(
      Object.entries(containers).map(([cid, html]) => [cid, { name: cid, top: 0, left: 0, width: 50, height: 50, html, css: html ? `.x-${cid}{color:red}` : "" }]),
    ),
  }) as unknown as Scene;

type Pending = { done: () => void; fail: () => void; settled: boolean };
let pending: Pending[];
let cm: typeof import("./container-manager");
let tr: typeof import("./transitions");

beforeEach(async () => {
  vi.resetModules();
  document.body.innerHTML = '<div id="scene-containers"></div>';
  pending = [];
  (Element.prototype as { animate?: unknown }).animate = function () {
    let done = () => {};
    let fail = () => {};
    const finished = new Promise<void>((res, rej) => { done = res; fail = () => rej(new Error("cancelled")); });
    finished.catch(() => {});
    const p: Pending = { done, fail, settled: false };
    pending.push(p);
    return { finished, cancel: () => { if (!p.settled) { p.settled = true; fail(); } } };
  };
  cm = await import("./container-manager");
  tr = await import("./transitions");
});
afterEach(() => { delete (Element.prototype as { animate?: unknown }).animate; });

const rnd = (seed: number) => () => (seed = (seed * 1664525 + 1013904223) % 4294967296) / 4294967296;
const flush = async () => { for (let i = 0; i < 5; i++) await Promise.resolve(); };

describe("random scene changes never leave stale content behind", () => {
  for (const cfg of [
    { type: "fade" }, { type: "slide", direction: "left" }, { type: "reveal" }, { type: "wipe" },
    { type: "random-container" }, { type: "slide", sequential: true }, { type: "fade", sequential: true, unchanged: true },
    { type: "cover", unchanged: true },
  ]) {
    it(JSON.stringify(cfg), async () => {
      tr.setTransitionConfig({ duration_ms: 400, ...cfg });
      const r = rnd(7);
      const ids = ["a", "b", "c"];
      let last: Scene | null = null;
      for (let step = 0; step < 60; step++) {
        const containers: Record<string, string> = {};
        for (const id of ids) if (r() < 0.6) containers[id] = r() < 0.5 ? `<p>${id}-${Math.floor(r() * 3)}</p>` : `<p>${id}-same</p>`;
        const next = scene(step, containers);
        if (cfg.sequential && last && r() < 0.8) cm.playOutro(next);
        cm.renderScene(next);
        last = next;
        // sometimes let animations finish, sometimes cut the next change in
        if (r() < 0.5) { pending.forEach((p) => { if (!p.settled) { p.settled = true; p.done(); } }); await flush(); }
      }
      pending.forEach((p) => { if (!p.settled) { p.settled = true; p.done(); } });
      await flush();
      for (const id of ids) {
        const els = document.querySelectorAll(`[data-container-id="${id}"]`);
        expect(els.length, `${id} content elements`).toBe(1);
        expect(els[0].innerHTML, id).toBe(last!.containers[id]?.html ?? "");
        const css = document.getElementById(`content-type-css-${id}`);
        expect(css?.textContent ?? "", `css ${id}`).toBe(last!.containers[id] ? `.x-${id}{color:red}` : "");
      }
      expect(document.querySelectorAll('[id$="-leaving"]').length, "leftover leaving styles").toBe(0);
      expect((document.getElementById("scene-containers") as HTMLElement).querySelectorAll("[style*='opacity']").length).toBe(0);
    });
  }
});
