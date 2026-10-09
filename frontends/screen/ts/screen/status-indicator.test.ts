// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("./logger.js", () => ({ log: vi.fn() }));

import { activeCodes, setContentMissing, setStatus, setStatusIndicatorEnabled, statusLevel } from "./status-indicator";
import { log } from "./logger.js";

const dot = () => document.getElementById("status-indicator");

describe("status indicator", () => {
  beforeEach(() => {
    document.body.innerHTML = '<div id="main-container"></div>';
    for (const code of ["con", "mim", "js"] as const) setStatus(code, null);
    setStatusIndicatorEnabled(true);
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
});
