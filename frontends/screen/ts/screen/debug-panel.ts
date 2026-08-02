import { getNow } from './clock';

/**
 * Debug panel initialization.
 *
 * Registers the `window.debugPanel` API, wires the toggle button, and
 * starts the uptime timers shown in the panel.
 */

function ready(fn: () => void): void {
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", fn);
  } else {
    fn();
  }
}

export function initDebugPanel(): void {
  ready(() => {
    try {
      const debugPanel = document.getElementById("debug-panel");
      const debugToggle = document.getElementById("debug-toggle");
      const collapseHandle = document.getElementById("debug-collapse-handle");

      // Both the header ("⚙ Debug Panel") and the handle on the panel's left
      // edge drive the same `collapsed` class on #debug-panel, so they can
      // never disagree about the panel's state.
      const toggleCollapsed = () => {
        if (!debugPanel) return;
        const collapsed = debugPanel.classList.toggle("collapsed");
        if (collapseHandle) collapseHandle.textContent = collapsed ? "›" : "‹";
      };
      debugToggle?.addEventListener("click", toggleCollapsed);
      collapseHandle?.addEventListener("click", toggleCollapsed);

      const commitEl = document.getElementById("debug-commit");
      if (commitEl) commitEl.textContent = `Commit: ${__GIT_COMMIT__}`;
    } catch (e) {
      /* intentional: DOM may not be ready in test environments */
    }

    const store: Record<string, Record<string, Record<string, string>>> = {};

    function ensure(section: string, group: string) {
      store[section] = store[section] || {};
      store[section][group] = store[section][group] || {};
      return store[section][group];
    }

    function renderSection(section: string) {
      const sec = store[section];
      if (!sec) return;
      const root = document.getElementById("debug-containers");
      if (!root) return;
      let wrapper = document.getElementById(`debug-section-${section}`);
      if (!wrapper) {
        wrapper = document.createElement("div");
        wrapper.id = `debug-section-${section}`;
        wrapper.className = "debug-section debug-section-generic";
        root.appendChild(wrapper);
      }
      const wrapperEl = wrapper as HTMLElement;
      wrapperEl.innerHTML = `<h4>${section}</h4>`;
      Object.keys(sec).forEach((group) => {
        const groupObj = sec[group];
        const title = document.createElement("div");
        title.className = "debug-group-title";
        title.innerHTML = ` <div class="debug-item"><span class="debug-label"><strong>${group}</strong></span></div>`;
        wrapperEl.appendChild(title);
        Object.keys(groupObj).forEach((k) => {
          const v = groupObj[k];
          const item = document.createElement("div");
          item.className = "debug-container-entry";
          if (k === "_value")
            item.innerHTML = `<span class="debug-container-value">${String(v)}</span>`;
          else
            item.innerHTML = `   <div class="debug-item"><span class="debug-label">${k}</span><span class="debug-value">${String(v)}</span></div>`;
          wrapperEl.appendChild(item);
        });
      });
    }

    function push(section: string, group: string, key: string, value: string) {
      if (!section || !group) return;
      const g = ensure(section, group);
      if (key === "") {
        delete g[key];
        if (Object.keys(g).length === 0) {
          delete store[section][group];
          if (Object.keys(store[section]).length === 0) delete store[section];
        }
      } else {
        g[key] = value;
      }
      renderSection(section);
    }

    function pushPlaylist(
      containerName: string,
      items: Array<{ id: number; title?: string; duration: number }>,
      currentId: number | null,
      startTime?: number | null,
      stopped?: boolean,
    ): void {
      const root = document.getElementById("debug-containers");
      if (!root) return;

      const sectionId = `debug-playlist-${containerName}`;
      let wrapper = document.getElementById(sectionId);
      if (!wrapper) {
        wrapper = document.createElement("div");
        wrapper.id = sectionId;
        wrapper.className = "debug-section debug-section-playlist";
        root.appendChild(wrapper);
      }
      const wrapperEl = wrapper as HTMLElement;
      wrapperEl.innerHTML = `<h4>Playlist: ${containerName} <span class="debug-playlist-count">(${items.length})</span></h4>`;

      const controls = document.createElement("div");
      controls.className = "debug-playlist-controls";
      const startBtn = document.createElement("button");
      startBtn.className = "debug-btn debug-btn-start";
      startBtn.textContent = "▶ Start";
      startBtn.style.display = stopped ? "" : "none";
      startBtn.addEventListener("click", () => {
        try { (window as any).debugPanel?.resumeSceneRotation?.(); } catch (e) {}
      });
      const stopBtn = document.createElement("button");
      stopBtn.className = "debug-btn debug-btn-stop";
      stopBtn.textContent = "■ Stop";
      stopBtn.style.display = stopped ? "none" : "";
      stopBtn.addEventListener("click", () => {
        try { (window as any).debugPanel?.stopSceneRotation?.(); } catch (e) {}
      });
      controls.appendChild(startBtn);
      controls.appendChild(stopBtn);
      wrapperEl.appendChild(controls);

      const list = document.createElement("div");
      list.className = "debug-playlist-list";
      items.forEach((item) => {
        const isActive = item.id === currentId;
        const row = document.createElement("div");
        row.className =
          "debug-playlist-item" +
          (isActive ? " debug-playlist-item--active" : "");

        if (isActive && item.duration > 0) {
          const elapsedSec =
            startTime != null ? (Date.now() - startTime) / 1000 : 0;
          row.style.animationDuration = `${item.duration}s`;
          row.style.animationDelay = `-${elapsedSec}s`;
        }

        const label = item.title || `#${item.id}`;
        row.innerHTML =
          `<span class="debug-playlist-title">${label}</span>` +
          `<span class="debug-playlist-duration">${item.duration}s</span>`;
        row.style.cursor = "pointer";
        row.title = "Click to jump to this item";
        row.addEventListener("click", () => {
          try {
            (window as any).debugPanel?.jumpToScene?.(item.id);
          } catch (e) {}
        });
        list.appendChild(row);
      });
      wrapperEl.appendChild(list);
    }

    try {
      if ((window as any).debugPanel) {
        (window as any).debugPanel.push = push;
        (window as any).debugPanel.pushPlaylist = pushPlaylist;
      } else {
        (window as any).debugPanel = { push, pushPlaylist };
      }
    } catch (e) {
      /* intentional: window may be unavailable in SSR/test contexts */
    }

    // ── Uptime timers ────────────────────────────────────────────────────
    const _pageLoadTime = Date.now();
    let _lastUpdContentTime: number | null = null;

    function formatElapsed(ms: number): string {
      const totalSec = Math.floor(ms / 1000);
      const h = Math.floor(totalSec / 3600);
      const m = Math.floor((totalSec % 3600) / 60);
      const s = totalSec % 60;
      if (h > 0) return `${h}h ${m}m ${s}s`;
      if (m > 0) return `${m}m ${s}s`;
      return `${s}s`;
    }

    function tickTimers(): void {
      const now = Date.now();
      push(
        "Screen Info",
        "Uptime",
        "Since page load",
        formatElapsed(now - _pageLoadTime),
      );
      push(
        "Screen Info",
        "Uptime",
        "Since last upd_content",
        _lastUpdContentTime !== null
          ? formatElapsed(now - _lastUpdContentTime)
          : "—",
      );
      const playerNow = getNow();
      push(
        "Screen Info",
        "Clock",
        "playertime",
        playerNow.toLocaleString('de-DE', { hour12: false }),
      );
    }

    tickTimers();
    setInterval(tickTimers, 1000);

    const markUpdContent = () => {
      _lastUpdContentTime = Date.now();
    };
    try {
      (window as any).debugPanel.markUpdContent = markUpdContent;
    } catch (e) {
      /* intentional */
    }
  });
}
