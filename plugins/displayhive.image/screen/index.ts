import type { ScreenPluginHost } from "@screen/plugins";
import { resolveRandomImages } from "./random-image-resolver";

export default (host: ScreenPluginHost) => {
  // A random-image placeholder must resolve to a *new* pick every time its scene is shown, including
  // repeat displays whose HTML is byte-identical, so this runs for every container, changed or not.
  host.afterRender(({ element }) => {
    void resolveRandomImages(element);
  });
};
