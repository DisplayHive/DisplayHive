import type { ScreenPluginHost } from "@screen/plugins";
import { startCountdownTicker, tickCountdown } from "./countdown";

export default (host: ScreenPluginHost) => {
  startCountdownTicker(() => host.getNow());
  // A new scene's countdowns show their time at once, not up to a second later.
  host.afterRender(() => tickCountdown());
};
