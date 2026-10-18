/**
 * Scene rotation logic.
 *
 * A screen has one shared rotation queue of Scenes (each Scene = one
 * ContentElement) rather than independent per-container playlists — when a
 * Scene is showing, all the containers its Contenttype's handlers map to
 * switch together; containers not in the current Scene go blank.
 */

import type { Scene } from "./types.js";
import { renderScene, clearAllContainers, getSocketEmitter, playOutro } from "./container-manager.js";
import { getTransitionConfig, transitionWanted } from "./transitions.js";
import { log } from "./logger.js";
import { setContentMissing } from "./status-indicator.js";
import { setIndicatorSuppressed, startIndicator, stopIndicator } from "./indicator.js";
import { isInWindows, minutesToNextBoundary } from "./recurrence.js";

let scenes: Scene[] = [];
let currentSceneId: number | null = null;
let advanceTimer: ReturnType<typeof setTimeout> | null = null;
let outroTimer: ReturnType<typeof setTimeout> | null = null;
let stopped = false;
let startTime: number | null = null;

/**
 * Returns true when a scene is within its schedule: between start_time and end_time (when set)
 * and inside one of its weekly windows (when it has any).
 * Scenes without any of these are always considered active.
 */
function isSceneActive(scene: Scene): boolean {
  const now = Date.now();
  if (!isInWindows(scene.recurrence, new Date(now), scene.recurrence_tz)) return false;
  if (scene.start_time) {
    const start = new Date(scene.start_time).getTime();
    if (!isNaN(start) && now < start) return false;
  }
  if (scene.end_time) {
    const end = new Date(scene.end_time).getTime();
    if (!isNaN(end) && now >= end) return false;
  }
  return true;
}

/** The indicator bar only makes sense when the rotation actually has somewhere to go. */
function syncIndicatorVisibility(): void {
  setIndicatorSuppressed(scenes.filter(isSceneActive).length <= 1);
}

function clearAdvanceTimer(): void {
  if (outroTimer) {
    clearTimeout(outroTimer);
    outroTimer = null;
  }
  if (advanceTimer) {
    clearTimeout(advanceTimer);
    advanceTimer = null;
  }
}

/** Find the next active scene index after `fromId` by rotating through `scenes`. */
function findNextActiveIndex(fromId: number | null): number | null {
  const total = scenes.length;
  if (total === 0) return null;
  const start = scenes.findIndex((s) => s.id === fromId);
  for (let offset = 1; offset <= total; offset++) {
    const idx = (start + offset) % total;
    if (isSceneActive(scenes[idx])) return idx;
  }
  return null;
}

function pushDebugPlaylist(): void {
  try {
    window.debugPanel?.pushPlaylist?.(
      "scenes",
      scenes.map((s) => ({ id: s.id, title: s.title, duration: s.duration })),
      currentSceneId,
      startTime,
      stopped,
    );
  } catch (e) {}
}

/** Display *sceneId* immediately (does not touch the advance timer). */
export function displayScene(sceneId: number): void {
  const scene = scenes.find((s) => s.id === sceneId);
  if (!scene) {
    log("error", "displayScene", "Scene not found: " + sceneId);
    return;
  }

  renderScene(scene);
  currentSceneId = sceneId;
  startTime = Date.now();
  syncIndicatorVisibility();
  startIndicator(scene.duration);
  pushDebugPlaylist();

  if (scene.update_after_show) {
    const emitter = getSocketEmitter();
    if (emitter) {
      emitter("displayhive:screen:cts:refresh_content", { id: sceneId });
      log("debug", "displayScene", `Requested refresh for scene ${sceneId}`);
    }
  }

  log("debug", "displayScene", `Displayed scene ${sceneId} (duration: ${scene.duration}s)`);
}

/**
 * With the Design's sequential transition the old content leaves in the last half of its scene: shortly before the
 * advance, tell the container manager which scene follows so it can animate out what is about to change.
 */
function scheduleOutro(scene: Scene): void {
  const config = getTransitionConfig();
  if (!config.sequential || !transitionWanted()) return;
  const delay = Math.max(0, scene.duration * 1000 - config.durationMs / 2);
  outroTimer = setTimeout(() => {
    outroTimer = null;
    const nextIdx = findNextActiveIndex(currentSceneId);
    if (nextIdx !== null) playOutro(scenes[nextIdx]);
  }, delay);
}

/** Schedule the next `advanceScene` call based on the current scene's duration. */
function scheduleAdvance(): void {
  const scene = scenes.find((s) => s.id === currentSceneId);
  if (scene && scene.duration > 0) {
    advanceTimer = setTimeout(() => advanceScene(), scene.duration * 1000);
    scheduleOutro(scene);
  }
}

/**
 * Advance to the next scene in the shared rotation.
 * Skips scenes outside their scheduled window. If none are active, retries after 60 s.
 */
export function advanceScene(): void {
  if (scenes.length === 0) {
    log("warn", "advanceScene", "No scenes to advance");
    return;
  }

  clearAdvanceTimer();

  const nextIdx = findNextActiveIndex(currentSceneId);
  if (nextIdx === null) {
    log("warn", "advanceScene", "All scenes are outside their scheduled window — retrying in 60 s");
    advanceTimer = setTimeout(() => advanceScene(), 60_000);
    return;
  }

  // When the only active scene is the one already showing, its turn still
  // comes around again: re-show it rather than skipping, so things that must
  // be fresh on every display (a random-image pick, `update_after_show` live
  // data) refresh at the end of its screen time. renderScene() only touches
  // the DOM for whatever actually changed, so unchanged content doesn't flicker.
  const next = scenes[nextIdx];
  displayScene(next.id);
  scheduleAdvance();
}

/** Immediately jump to a specific scene and continue rotation from there. */
export function jumpToScene(sceneId: number): void {
  clearAdvanceTimer();
  stopped = false;
  displayScene(sceneId);
  scheduleAdvance();
}

/** Stop the rotation by clearing the advance timer. */
export function stopSceneRotation(): void {
  clearAdvanceTimer();
  stopped = true;
  log("info", "stopSceneRotation", "Stopped scene rotation");
  pushDebugPlaylist();
}

/** Resume a previously-stopped rotation, restarting from the first active scene. */
export function resumeSceneRotation(): void {
  startSceneRotation(scenes);
}

/**
 * Patch a scene's container HTML in place (e.g. after a background
 * random-image refresh) without disturbing the rotation timer. Re-renders
 * immediately only if that scene is currently showing.
 */
export function patchCurrentScene(sceneId: number, containerHtml: Record<string, string>): void {
  const scene = scenes.find((s) => s.id === sceneId);
  if (!scene) return;

  for (const [containerId, html] of Object.entries(containerHtml)) {
    if (scene.containers[containerId]) {
      scene.containers[containerId] = { ...scene.containers[containerId], html };
    }
  }

  if (sceneId === currentSceneId) {
    renderScene(scene, true); // an update of what is showing, not a scene change: no transition
  }
}

/**
 * (Re)start the shared rotation from a freshly-received scenes array
 * (called on every `upd_content` push — which resends the full scene list
 * from scratch on ANY change anywhere, not just a change to what's currently
 * showing; see upd_content.py). If the scene currently on screen is still
 * present and active in the new list, it is left running undisturbed —
 * neither its timer nor its rendering are touched — and the rotation simply
 * continues to whichever scene naturally comes next once its own duration
 * elapses (via advanceScene()'s existing position-based walk through
 * `scenes`, which by then is already the fresh list). Only when the current
 * scene has actually disappeared or gone inactive (or nothing is showing
 * yet) does this jump straight to the first active scene.
 */
export function startSceneRotation(newScenes: Scene[]): void {
  scenes = newScenes;
  syncIndicatorVisibility();
  setContentMissing(newScenes.length === 0);

  if (scenes.length === 0) {
    clearAdvanceTimer();
    stopped = false;
    log("info", "startSceneRotation", "No scenes to show");
    currentSceneId = null;
    clearAllContainers();
    stopIndicator();
    return;
  }

  if (!stopped && currentSceneId !== null) {
    const stillCurrent = scenes.find((s) => s.id === currentSceneId);
    if (stillCurrent && isSceneActive(stillCurrent)) {
      log(
        "debug", "startSceneRotation",
        `Current scene ${currentSceneId} still present and active in the new playlist — continuing without interrupting it`,
      );
      _lastActiveIds = activeIdsKey();
      armScheduleWatcher();
      return;
    }
  }

  clearAdvanceTimer();
  stopped = false;

  const firstActive = scenes.find(isSceneActive);
  if (!firstActive) {
    log("warn", "startSceneRotation", "All scenes are outside their scheduled window — retrying in 60 s");
    // Whatever was on screen has run out of its window: take it down instead of leaving it up.
    currentSceneId = null;
    clearAllContainers();
    stopIndicator();
    advanceTimer = setTimeout(() => startSceneRotation(scenes), 60_000);
    return;
  }

  _lastActiveIds = activeIdsKey();
  displayScene(firstActive.id);
  scheduleAdvance();
  armScheduleWatcher();
}

// ---------------------------------------------------------------------------
// Schedule watcher
// ---------------------------------------------------------------------------
// Keeps a timeout that fires at the next start_time / end_time boundary
// across all scenes. When it fires it compares the current active set
// against the previously known active set; if they differ it restarts the
// rotation so the screen picks up newly active scenes or drops expired ones
// without waiting for a server push.

let scheduleTimer: ReturnType<typeof setTimeout> | null = null;
let _lastActiveIds = "";
/** While a scene has weekly windows the watcher looks again at least this often (time changes). */
const WINDOW_RECHECK_MS = 5 * 60 * 1000;

function activeIdsKey(): string {
  return JSON.stringify(scenes.filter(isSceneActive).map((s) => s.id).sort((a, b) => a - b));
}

/** (Re-)arm the schedule watcher for the shared rotation. */
export function armScheduleWatcher(): void {
  if (scheduleTimer) {
    clearTimeout(scheduleTimer);
    scheduleTimer = null;
  }
  if (scenes.length === 0) return;

  const now = Date.now();
  const boundaries: number[] = [];
  for (const scene of scenes) {
    if (scene.start_time) {
      const t = new Date(scene.start_time).getTime();
      if (!isNaN(t) && t > now) boundaries.push(t);
    }
    if (scene.end_time) {
      const t = new Date(scene.end_time).getTime();
      if (!isNaN(t) && t > now) boundaries.push(t);
    }
  }

  // Weekly windows: the next start or end of any of them. Their arithmetic is in wall-clock
  // minutes, so a time change can make one long wait an hour off — look again at least every few
  // minutes while a scene has windows.
  let hasWindows = false;
  for (const scene of scenes) {
    const minutes = minutesToNextBoundary(scene.recurrence, new Date(now), scene.recurrence_tz);
    if (minutes !== null) {
      hasWindows = true;
      boundaries.push(now + minutes * 60_000);
    }
  }

  if (boundaries.length === 0) return; // no scheduled scenes — nothing to watch

  const nextBoundary = Math.min(...boundaries);
  let delay = nextBoundary - now + 500; // +500 ms so we fire just after the boundary
  if (hasWindows) delay = Math.min(delay, WINDOW_RECHECK_MS);

  log("debug", "armScheduleWatcher", `Next boundary in ${Math.round(delay / 1000)} s`);

  scheduleTimer = setTimeout(() => {
    const activeIds = activeIdsKey();
    if (activeIds !== _lastActiveIds) {
      log("info", "scheduleWatcher", "Active scene set changed, restarting rotation");
      _lastActiveIds = activeIds;
      startSceneRotation(scenes);
    }
    armScheduleWatcher();
  }, delay);
}
