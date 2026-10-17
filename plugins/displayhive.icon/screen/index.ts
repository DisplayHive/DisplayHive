import type { ScreenPluginHost } from "@screen/plugins";
import { resolveIcons } from "./icon-resolver";

export default (host: ScreenPluginHost) => {
  // Only containers whose content changed: resolveIcons() fetches and re-inserts unconditionally for
  // whatever it is given, so this avoids reloading an icon that already shows correctly.
  host.afterRender(({ element, changed }) => {
    if (changed) void resolveIcons(element);
  });
};
