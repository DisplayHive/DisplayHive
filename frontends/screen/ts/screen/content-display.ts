/**
 * Scene rotation logic.
 *
 * A screen has one shared rotation queue of Scenes (each Scene = one
 * ContentElement) rather than independent per-container playlists — when a
 * Scene is showing, all the containers its Contenttype's handlers map to
 * switch together; containers not in the current Scene go blank.
 */

import type { Scene } from "./types.js";
import { renderScene, clearAllContainers, getSocketEmitter } from "./container-manager.js";
import { log } from "./logger.js";

let scenes: Scene[] = [];
let currentSceneId: number | null = null;
let advanceTimer: ReturnType<typeof setTimeout> | null = null;
let stopped = false;
let startTime: number | null = null;

/**
 * Returns true when a scene is within its scheduled window.
 * Scenes without start_time / end_time are always considered active.
 */
function isSceneActive(scene: Scene): boolean {
  const now = Date.now();
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

function clearAdvanceTimer(): void {
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
    (window as any).debugPanel?.pushPlaylist?.(
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

/** Schedule the next `advanceScene` call based on the current scene's duration. */
function scheduleAdvance(): void {
  const scene = scenes.find((s) => s.id === currentSceneId);
  if (scene && scene.duration > 0) {
    advanceTimer = setTimeout(() => advanceScene(), scene.duration * 1000);
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

  const next = scenes[nextIdx];
  if (next.id === currentSceneId) {
    log("debug", "advanceScene", `Next scene (${next.id}) is already displayed — skipping re-render`);
    scheduleAdvance();
    return;
  }

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
    renderScene(scene);
  }
}

/**
 * (Re)start the shared rotation from a freshly-received scenes array
 * (called on every `upd_content` push). Starts from the first currently
 * active scene; if none are active, retries after 60 s.
 */
export function startSceneRotation(newScenes: Scene[]): void {
  scenes = newScenes;
  clearAdvanceTimer();
  stopped = false;

  if (scenes.length === 0) {
    log("info", "startSceneRotation", "No scenes to show");
    currentSceneId = null;
    clearAllContainers();
    return;
  }

  const firstActive = scenes.find(isSceneActive);
  if (!firstActive) {
    log("warn", "startSceneRotation", "All scenes are outside their scheduled window — retrying in 60 s");
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

  if (boundaries.length === 0) return; // no scheduled scenes — nothing to watch

  const nextBoundary = Math.min(...boundaries);
  const delay = nextBoundary - now + 500; // +500 ms so we fire just after the boundary

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
