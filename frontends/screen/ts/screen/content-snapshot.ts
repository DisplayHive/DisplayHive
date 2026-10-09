/**
 * The last content the server sent, kept in the browser: a screen that is restarted while the
 * server is unreachable (power cut, network down) shows it again instead of a blank stage, and a
 * screen that starts while the server is slow shows it until the fresh content arrives.
 *
 * Only a device's own content is kept: a preview or an impersonation session shows something else.
 * `server_time` is dropped — it would set the clock back to the moment of saving.
 */

import { getContentSnapshot, setContentSnapshot } from "./storage.js";
import type { UpdContentMessage } from "./types.js";

/** Stay well under the browser's localStorage quota (about 5 MB for all keys together). */
const MAX_BYTES = 1_500_000;

interface Snapshot {
  deviceKey: string;
  message: UpdContentMessage;
}

/** A preview or impersonation page does not show the device's own content. */
export function isOwnContentPage(search: string = window.location.search): boolean {
  const params = new URLSearchParams(search);
  return params.get("preview") !== "true" && !params.get("impersonate");
}

export function saveContentSnapshot(deviceKey: string | null | undefined, message: UpdContentMessage): void {
  if (!deviceKey || !isOwnContentPage()) return;
  const { server_time: _ignored, ...rest } = message;
  void _ignored;
  const json = JSON.stringify({ deviceKey, message: rest } satisfies Snapshot);
  if (json.length > MAX_BYTES) return;
  setContentSnapshot(json);
}

/** The saved content for this device, or null (none saved, another device's, damaged). */
export function loadContentSnapshot(deviceKey: string | null | undefined): UpdContentMessage | null {
  if (!deviceKey || !isOwnContentPage()) return null;
  const raw = getContentSnapshot();
  if (!raw) return null;
  try {
    const snapshot = JSON.parse(raw) as Partial<Snapshot>;
    if (snapshot.deviceKey !== deviceKey || !snapshot.message || typeof snapshot.message !== "object") return null;
    if (!Array.isArray(snapshot.message.scenes ?? [])) return null;
    return snapshot.message;
  } catch {
    return null;
  }
}
