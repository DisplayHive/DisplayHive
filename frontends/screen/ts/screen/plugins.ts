/**
 * The screen side of the plugin system: loads the screen modules of the plugins that are active and
 * gives them the few things they need (see docs/developer/plugins.md).
 *
 * The server writes the active plugins into the page (`<script type="application/json" id="dh-plugins">`),
 * so a screen that is offline and shows its cached page knows the same list it had. A plugin bundled with
 * DisplayHive keeps its screen code in `plugins/<id>/screen/index.ts` (a chunk of its own, loaded only
 * when the plugin is active); an installed plugin ships a finished ES module that the server hands out under
 * `/api/plugins/<id>/assets/<version>/…`.
 */

import { getNow } from "./clock.js";
import { log } from "./logger.js";

/** A container whose content was just put on the screen. */
export interface RenderedContainer {
  id: string;
  element: HTMLElement;
  /** Its HTML differs from what it showed before (a repeat display of the same content is not "changed"). */
  changed: boolean;
}

export interface ScreenPluginHost {
  readonly pluginId: string;
  /** The current time, corrected by the offset to the server's clock. */
  getNow(): Date;
  /** Called for every container each time a scene has been put on the screen — including the one already showing when the plugin loads. */
  afterRender(callback: (container: RenderedContainer) => void): void;
  log(severity: "debug" | "info" | "warn" | "error", where: string, message: string): void;
}

export interface ActiveScreenPlugin {
  id: string;
  version: string;
  screen: string;
  source: "bundled" | "installed";
}

type ScreenPluginModule = { default: (host: ScreenPluginHost) => void | Promise<void> };

const bundled = import.meta.glob<ScreenPluginModule>("@plugins/*/screen/index.ts");

const callbacks: Array<(container: RenderedContainer) => void> = [];
let lastRendered: RenderedContainer[] = [];

/** Called by the container manager after a scene was rendered. */
export function runAfterRender(containers: RenderedContainer[]): void {
  lastRendered = containers;
  for (const callback of callbacks) {
    for (const container of containers) safely(callback, container);
  }
}

function safely(callback: (container: RenderedContainer) => void, container: RenderedContainer): void {
  try {
    callback(container);
  } catch (error) {
    log("warn", "plugins", "A plugin failed while a container was rendered:", error);
  }
}

function hostFor(pluginId: string): ScreenPluginHost {
  return {
    pluginId,
    getNow,
    afterRender(callback) {
      callbacks.push(callback);
      // The scene may be on the screen already: the plugin missed it by loading late.
      for (const container of lastRendered) safely(callback, { ...container, changed: true });
    },
    log(severity, where, message) {
      log(severity, `plugin:${pluginId}:${where}`, message);
    },
  };
}

export function readActivePlugins(): ActiveScreenPlugin[] {
  try {
    const raw = document.getElementById("dh-plugins")?.textContent;
    const list = raw ? JSON.parse(raw) : [];
    return Array.isArray(list) ? list.filter((p) => p && typeof p.id === "string" && p.screen) : [];
  } catch {
    return [];
  }
}

async function importModule(plugin: ActiveScreenPlugin): Promise<ScreenPluginModule | null> {
  if (plugin.source === "bundled") {
    const key = Object.keys(bundled).find((k) => k.includes(`/plugins/${plugin.id}/screen/`));
    return key ? await bundled[key]() : null;
  }
  const url = `${window.location.origin}/api/plugins/${plugin.id}/assets/${plugin.version}/${plugin.screen}`;
  return (await import(/* @vite-ignore */ url)) as ScreenPluginModule;
}

/** Load the screen modules of the active plugins. One that fails is logged and skipped. */
export async function loadScreenPlugins(): Promise<void> {
  await Promise.all(
    readActivePlugins().map(async (plugin) => {
      try {
        const module = await importModule(plugin);
        if (module) await module.default(hostFor(plugin.id));
      } catch (error) {
        log("warn", "plugins", `The screen part of the plugin ${plugin.id} could not be loaded:`, error);
      }
    }),
  );
}
