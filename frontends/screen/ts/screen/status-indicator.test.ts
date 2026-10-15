// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("./logger.js", () => ({ log: vi.fn() }));

import {
  activeCodes,
  setContentMissing,
  setStatus,
  setStatusIndicatorEnabled,
  setStatusIndicatorStyle,
  statusLevel,
} from "./status-indicator";
import { log } from "./logger.js";

const dot = () => document.getElementById("status-indicator");

describe("status indicator", () => {
  beforeEach(() => {
    document.body.innerHTML = '<div id="main-container"></div>';
    for (const code of ["con", "mim", "js"] as const) setStatus(code, null);
    setStatusIndicatorEnabled(true);
    setStatusIndicatorStyle("dot");
    vi.mocked(log).mockClear();
  });

  it("is hidden while everything is fine", () => {
    expect(statusLevel()).toBeNull();
    expect(dot()?.hidden ?? true).toBe(true);
  });

  it("missing content is yellow, a lost connection red, and red wins", () => {
    setContentMissing(true);
    expect(statusLevel()).toBe("yellow");
    expect(dot()?.dataset.level).toBe("yellow");
    setStatus("con", "disconnected");
    expect(statusLevel()).toBe("red");
    expect(activeCodes()).toEqual(["con", "mim"]);
    expect(dot()?.textContent).toBe("con mim");
    setStatus("con", null);
    expect(statusLevel()).toBe("yellow");
    setContentMissing(false);
    expect(dot()?.hidden).toBe(true);
  });

  it("writes a code to the log once, when it switches on", () => {
    setStatus("con", "a");
    setStatus("con", "b");
    expect(log).toHaveBeenCalledTimes(1);
    expect(log).toHaveBeenCalledWith("error", "status-indicator", "con: a");
    setStatus("js", "boom");
    expect(log).toHaveBeenLastCalledWith("warn", "status-indicator", "js: boom");
  });

  it("the admin's switch hides the dot but the state is still tracked", () => {
    setStatus("con", "down");
    setStatusIndicatorEnabled(false);
    expect(dot()?.hidden).toBe(true);
    expect(statusLevel()).toBe("red");
    setStatusIndicatorEnabled(true);
    expect(dot()?.hidden).toBe(false);
  });

  it("icon style shows a pictogram per problem instead of the codes, red first", () => {
    setStatusIndicatorStyle("icons");
    setContentMissing(true);
    setStatus("con", "disconnected");
    const el = dot()!;
    expect(el.dataset.style).toBe("icons");
    expect(el.textContent).toBe("");
    const icons = Array.from(el.querySelectorAll("svg.status-icon"));
    expect(icons.map((i) => i.getAttribute("class"))).toEqual(["status-icon status-icon--con", "status-icon status-icon--mim"]);
    expect(icons[0]!.getAttribute("aria-label")).toMatch(/connection/i);
    expect(el.title).toContain("con: disconnected");
  });

  it("switching the style back restores the codes", () => {
    setStatus("js", "boom");
    setStatusIndicatorStyle("icons");
    expect(dot()?.querySelectorAll("svg").length).toBe(1);
    setStatusIndicatorStyle("dot");
    expect(dot()?.dataset.style).toBe("dot");
    expect(dot()?.textContent).toBe("js");
  });
});
