/**
 * Transitions between the content of a container when a new scene replaces it.
 *
 * The Design picks one (`design.transition` in the upd_content payload, see
 * application/admin/designs/helper.py's transition_payload): a type, a direction for the types that have one,
 * and a duration. container-manager.ts keeps the old content's element in place, puts the new content in a fresh
 * element on top of it and calls playTransition(); when it ends the old element is removed. Most effects animate only
 * `opacity`, `transform` and `clip-path` (cheap on weak hardware); the ones marked heavy in EFFORT use masks, filters or
 * 3D. A browser that cannot do what an effect needs fades instead, and one that cannot animate shows the new content
 * at once.
 */

/** The effects themselves. How much a browser has to do for each: see EFFORT. */
export const CONCRETE_TYPES = [
  "fade", "slide", "push-fade", "bounce", "cover", "reveal", "parallax", "stack", "zoom-in", "zoom-out",
  "rotate", "hinge", "skew",
  "wipe", "diagonal", "split-open", "split-close", "circle", "corner-circle", "diamond", "box",
  "blinds", "flash", "flip", "cube", "blur", "glitch",
] as const;
export type ConcreteType = (typeof CONCRETE_TYPES)[number];

/**
 * How demanding an effect is for the browser. light: opacity and transform only. medium: also clip-path shapes.
 * heavy: masks, filters or 3D — fine on a PC, but they can stutter on weak hardware (old Raspberry Pi, smart TVs).
 */
export type Effort = "light" | "medium" | "heavy";
export const EFFORT: Record<ConcreteType, Effort> = {
  fade: "light", slide: "light", "push-fade": "light", bounce: "light", cover: "light", reveal: "light",
  parallax: "light", stack: "light", "zoom-in": "light", "zoom-out": "light", rotate: "light", hinge: "light",
  skew: "light",
  wipe: "medium", diagonal: "medium", "split-open": "medium", "split-close": "medium", circle: "medium",
  "corner-circle": "medium", diamond: "medium", box: "medium",
  blinds: "heavy", flash: "heavy", flip: "heavy", cube: "heavy", blur: "heavy", glitch: "heavy",
};

/** One random pick per scene change ("random…") or one per container ("random-container…"), limited by effort. */
export const RANDOM_TYPES = [
  "random-light", "random-medium", "random", "random-container-light", "random-container-medium", "random-container",
] as const;

export const TRANSITION_TYPES = ["none", ...CONCRETE_TYPES, ...RANDOM_TYPES] as const;
export type TransitionType = (typeof TRANSITION_TYPES)[number];
export type TransitionDirection = "left" | "right" | "up" | "down";
const DIRECTIONS: TransitionDirection[] = ["left", "right", "up", "down"];

/** In which order the containers of one scene change start (a delay between them). */
export const STAGGERS = ["none", "order", "top-bottom", "left-right", "centre-out", "random"] as const;
export type TransitionStagger = (typeof STAGGERS)[number];

export interface TransitionConfig {
  type: TransitionType;
  direction: TransitionDirection;
  durationMs: number;
  /** The new content comes in only after the old has left; each takes half of the duration. */
  sequential: boolean;
  /** Containers whose content stays the same at a scene change are animated too. */
  unchanged: boolean;
  /** "container": each container moves or fades on its own; "slide": one effect across the whole screen. */
  scope: "container" | "slide";
  /** The containers start one after another instead of all at once. */
  stagger: TransitionStagger;
}

const DEFAULT_DURATION_MS = 600;
const MAX_DURATION_MS = 5000;

let config: TransitionConfig = {
  type: "none", direction: "left", durationMs: DEFAULT_DURATION_MS, sequential: false, unchanged: false,
  scope: "container", stagger: "none",
};

/** Takes the design's (untrusted) transition block; anything unusable means no transition. */
export function setTransitionConfig(raw: unknown): void {
  const c = raw as Record<string, unknown> | null | undefined;
  const type = TRANSITION_TYPES.find((t) => t === c?.type) ?? "none";
  const direction = DIRECTIONS.find((d) => d === c?.direction) ?? "left";
  const duration = Number(c?.duration_ms);
  config = {
    type,
    direction,
    durationMs: Number.isFinite(duration) && duration > 0 ? Math.min(duration, MAX_DURATION_MS) : DEFAULT_DURATION_MS,
    sequential: c?.sequential === true,
    unchanged: c?.unchanged === true,
    scope: c?.scope === "slide" ? "slide" : "container",
    stagger: STAGGERS.find((t) => t === c?.stagger) ?? "none",
  };
}

export function getTransitionConfig(): TransitionConfig {
  return config;
}

type Frames = Keyframe[];
interface Plan {
  /** Keyframes for the leaving element (omitted: it stays as it is until the end). */
  out?: Frames;
  /** Keyframes for the entering element. */
  in?: Frames;
  /** The leaving element is drawn above the entering one (reveal). */
  oldOnTop?: boolean;
  /** Timing function for both (default ease-in-out). */
  easing?: string;
}

/** A container's box inside the stage, in px, and the stage's size: what an effect across the whole slide needs. */
export interface StageGeometry {
  left: number;
  top: number;
  width: number;
  height: number;
  stageWidth: number;
  stageHeight: number;
}

/** The container's own size in px (for effects that need real distances, like the cube). */
export interface BoxSize {
  width: number;
  height: number;
}

/** Where the content travels to: the unit vector of a direction. */
function unit(direction: TransitionDirection): [number, number] {
  return direction === "left" ? [-1, 0] : direction === "right" ? [1, 0] : direction === "up" ? [0, -1] : [0, 1];
}

const horizontal = (direction: TransitionDirection): boolean => direction === "left" || direction === "right";

// Content may overflow its container on purpose, so a clip must not cut it off on the sides it does not work along:
// those insets are negative (outside the box), and the open state is "no clipping at all".
const OUT = "-100vmax";

/** A clip-path inset that is fully closed along the wipe's axis, starting from the edge the wipe comes from. */
function closedInset(direction: TransitionDirection): string {
  // Moving right: the new content grows from the left edge, so its right side is clipped away first.
  return direction === "right" ? `inset(${OUT} 100% ${OUT} ${OUT})`
    : direction === "left" ? `inset(${OUT} ${OUT} ${OUT} 100%)`
    : direction === "down" ? `inset(${OUT} ${OUT} 100% ${OUT})`
    : `inset(100% ${OUT} ${OUT} ${OUT})`;
}

/** The effects that move content along an axis: the container's box then clips along that axis (see slotClip). */
const MOVING: ReadonlySet<ConcreteType> = new Set<ConcreteType>(["slide", "push-fade", "bounce", "cover", "reveal", "parallax", "stack", "skew"]);

/**
 * What the container's box must clip while content slides through it, so it does not travel over its neighbours.
 * Only along the axis of the movement: content that overflows the box on the other axis stays visible.
 */
function slotClip(type: ConcreteType, direction: TransitionDirection): string {
  if (!MOVING.has(type)) return "";
  return horizontal(direction) ? `inset(${OUT} 0 ${OUT} 0)` : `inset(0 ${OUT} 0 ${OUT})`;
}

/**
 * Wipe across the whole stage, seen from one container: the front runs over the screen and reveals the part of the
 * container it has passed. Insets are in px, relative to the container's box (negative = beyond it).
 */
function stageWipe(direction: TransitionDirection, g: StageGeometry): Frames {
  const { left: L, top: T, width: w, height: h, stageWidth: W, stageHeight: H } = g;
  const o = OUT;
  switch (direction) {
    case "right": return [{ clipPath: `inset(${o} ${L + w}px ${o} ${o})` }, { clipPath: `inset(${o} ${L + w - W}px ${o} ${o})` }];
    case "left": return [{ clipPath: `inset(${o} ${o} ${o} ${W - L}px)` }, { clipPath: `inset(${o} ${o} ${o} ${-L}px)` }];
    case "down": return [{ clipPath: `inset(${o} ${o} ${T + h}px ${o})` }, { clipPath: `inset(${o} ${o} ${T + h - H}px ${o})` }];
    case "up": return [{ clipPath: `inset(${H - T}px ${o} ${o} ${o})` }, { clipPath: `inset(${-T}px ${o} ${o} ${o})` }];
  }
}

/** The corner an effect starts from, for each direction (clockwise from the top left): [0|1, 0|1] of width/height. */
function cornerOf(direction: TransitionDirection): [number, number] {
  return direction === "right" ? [0, 0] : direction === "down" ? [1, 0] : direction === "left" ? [1, 1] : [0, 1];
}

const BLINDS = 8;
const PERSPECTIVE = 1500;
const FLAT_MASK = "linear-gradient(#000, #000)";

/** Mask keyframe properties, with the -webkit- spelling Safari still needs. */
function maskFrame(size: string, position: string): Keyframe {
  return {
    maskImage: FLAT_MASK, maskRepeat: "repeat", maskSize: size, maskPosition: position,
    webkitMaskImage: FLAT_MASK, webkitMaskRepeat: "repeat", webkitMaskSize: size, webkitMaskPosition: position,
  };
}

/**
 * The keyframes of an effect. *geo* set: the effect is one across the whole stage (every container uses the same stage
 * coordinates); *size* is the container's own box, for the effects that need real distances.
 */
function planFor(type: ConcreteType, direction: TransitionDirection, geo?: StageGeometry, size?: BoxSize): Plan {
  const [ux, uy] = unit(direction);
  const sign = ux + uy; // -1 for left/up, +1 for right/down
  const move = (x: number, y: number) =>
    geo ? `translate(${x * geo.stageWidth}px, ${y * geo.stageHeight}px)` : `translate(${x * 100}%, ${y * 100}%)`;
  // Effects that turn or grow around a point use the middle of the screen when the effect spans it, else the container's.
  const origin = geo ? `${geo.stageWidth / 2 - geo.left}px ${geo.stageHeight / 2 - geo.top}px` : "50% 50%";
  const zoom = (scale: number, opacity: number): Keyframe => ({ transform: `scale(${scale})`, opacity, transformOrigin: origin });
  const centre = origin;
  const axis = horizontal(direction) ? "Y" : "X";
  const skewAxis = horizontal(direction) ? "X" : "Y";

  switch (type) {
    case "fade":
      return { out: [{ opacity: 1 }, { opacity: 0 }], in: [{ opacity: 0 }, { opacity: 1 }] };
    case "slide":
      return {
        out: [{ transform: move(0, 0) }, { transform: move(ux, uy) }],
        in: [{ transform: move(-ux, -uy) }, { transform: move(0, 0) }],
      };
    case "push-fade":
      return {
        out: [{ transform: move(0, 0), opacity: 1 }, { transform: move(ux, uy), opacity: 0 }],
        in: [{ transform: move(-ux, -uy), opacity: 0 }, { transform: move(0, 0), opacity: 1 }],
      };
    case "bounce":
      return {
        out: [{ transform: move(0, 0) }, { transform: move(ux, uy) }],
        in: [{ transform: move(-ux, -uy) }, { transform: move(0, 0) }],
        easing: "cubic-bezier(0.34, 1.56, 0.64, 1)", // overshoots the end point and settles back
      };
    case "cover":
      return { in: [{ transform: move(-ux, -uy) }, { transform: move(0, 0) }] };
    case "reveal":
      return { out: [{ transform: move(0, 0) }, { transform: move(ux, uy) }], oldOnTop: true };
    case "parallax":
      return {
        out: [{ transform: move(0, 0) }, { transform: move(ux * 0.3, uy * 0.3) }],
        in: [{ transform: move(-ux, -uy) }, { transform: move(0, 0) }],
      };
    case "stack":
      return {
        out: [{ transform: "scale(1)", opacity: 1, transformOrigin: origin }, { transform: "scale(0.9)", opacity: 0.4, transformOrigin: origin }],
        in: [{ transform: move(-ux, -uy) }, { transform: move(0, 0) }],
      };
    case "zoom-in":
      return { out: [zoom(1, 1), zoom(1.25, 0)], in: [zoom(0.8, 0), zoom(1, 1)] };
    case "zoom-out":
      return { out: [zoom(1, 1), zoom(0.8, 0)], in: [zoom(1.25, 0), zoom(1, 1)] };
    case "rotate":
      return {
        out: [
          { transform: "rotate(0deg) scale(1)", opacity: 1, transformOrigin: origin },
          { transform: `rotate(${sign * 12}deg) scale(1.3)`, opacity: 0, transformOrigin: origin },
        ],
        in: [
          { transform: `rotate(${-sign * 12}deg) scale(0.6)`, opacity: 0, transformOrigin: origin },
          { transform: "rotate(0deg) scale(1)", opacity: 1, transformOrigin: origin },
        ],
      };
    case "hinge": {
      // The old content falls away around a bottom corner (left/up: bottom left; right/down: bottom right).
      const left = sign < 0;
      const pivot = (fromLeft: boolean) =>
        geo ? `${fromLeft ? -geo.left : geo.stageWidth - geo.left}px ${geo.stageHeight - geo.top}px` : `${fromLeft ? 0 : 100}% 100%`;
      return {
        out: [
          { transform: "rotate(0deg)", opacity: 1, transformOrigin: pivot(left) },
          { transform: `rotate(${left ? -90 : 90}deg)`, opacity: 0, transformOrigin: pivot(left) },
        ],
        in: [
          { transform: `rotate(${left ? 20 : -20}deg)`, opacity: 0, transformOrigin: pivot(!left) },
          { transform: "rotate(0deg)", opacity: 1, transformOrigin: pivot(!left) },
        ],
      };
    }
    case "skew":
      return {
        out: [
          { transform: `${move(0, 0)} skew${skewAxis}(0deg)` },
          { transform: `${move(ux, uy)} skew${skewAxis}(${-sign * 20}deg)` },
        ],
        in: [
          { transform: `${move(-ux, -uy)} skew${skewAxis}(${sign * 20}deg)` },
          { transform: `${move(0, 0)} skew${skewAxis}(0deg)` },
        ],
      };

    case "wipe":
      return { in: geo ? stageWipe(direction, geo) : [{ clipPath: closedInset(direction) }, { clipPath: `inset(${OUT})` }] };
    case "diagonal": {
      // A triangle that grows from a corner until it covers everything.
      const [cx, cy] = cornerOf(direction);
      const sx = cx === 0 ? 1 : -1;
      const sy = cy === 0 ? 1 : -1;
      if (geo) {
        const x = cx * geo.stageWidth - geo.left;
        const y = cy * geo.stageHeight - geo.top;
        const dx = sx * geo.stageWidth * 2;
        const dy = sy * geo.stageHeight * 2;
        const c = `${x}px ${y}px`;
        return { in: [{ clipPath: `polygon(${c}, ${c}, ${c})` }, { clipPath: `polygon(${c}, ${x + dx}px ${y}px, ${x}px ${y + dy}px)` }] };
      }
      const c = `${cx * 100}% ${cy * 100}%`;
      return {
        in: [
          { clipPath: `polygon(${c}, ${c}, ${c})` },
          { clipPath: `polygon(${c}, ${cx * 100 + sx * 200}% ${cy * 100}%, ${cx * 100}% ${cy * 100 + sy * 200}%)` },
        ],
      };
    }
    case "split-open":
    case "split-close": {
      let open: Frames;
      if (geo) {
        const { left: L, top: T, width: w, height: h, stageWidth: W, stageHeight: H } = geo;
        open = horizontal(direction)
          ? [{ clipPath: `inset(${OUT} ${L + w - W / 2}px ${OUT} ${W / 2 - L}px)` }, { clipPath: `inset(${OUT} ${L + w - W}px ${OUT} ${-L}px)` }]
          : [{ clipPath: `inset(${H / 2 - T}px ${OUT} ${T + h - H / 2}px ${OUT})` }, { clipPath: `inset(${-T}px ${OUT} ${T + h - H}px ${OUT})` }];
      } else {
        open = horizontal(direction)
          ? [{ clipPath: `inset(${OUT} 50% ${OUT} 50%)` }, { clipPath: `inset(${OUT} 0% ${OUT} 0%)` }]
          : [{ clipPath: `inset(50% ${OUT} 50% ${OUT})` }, { clipPath: `inset(0% ${OUT} 0% ${OUT})` }];
      }
      // Opening: the new content opens from the middle line over the old. Closing: the old closes to it, uncovering the new.
      return type === "split-open" ? { in: open } : { out: [...open].reverse(), oldOnTop: true };
    }
    case "circle": {
      const full = geo ? `${Math.hypot(geo.stageWidth, geo.stageHeight) / 2 + 2}px` : "75%";
      return { in: [{ clipPath: `circle(${geo ? "0px" : "0%"} at ${centre})` }, { clipPath: `circle(${full} at ${centre})` }] };
    }
    case "corner-circle": {
      const [cx, cy] = cornerOf(direction);
      const at = geo ? `${cx * geo.stageWidth - geo.left}px ${cy * geo.stageHeight - geo.top}px` : `${cx * 100}% ${cy * 100}%`;
      const full = geo ? `${Math.hypot(geo.stageWidth, geo.stageHeight) + 2}px` : "145%";
      return { in: [{ clipPath: `circle(${geo ? "0px" : "0%"} at ${at})` }, { clipPath: `circle(${full} at ${at})` }] };
    }
    case "diamond": {
      if (geo) {
        const cx = geo.stageWidth / 2 - geo.left;
        const cy = geo.stageHeight / 2 - geo.top;
        const r = (geo.stageWidth + geo.stageHeight) / 2 + 2;
        const dot = `${cx}px ${cy}px`;
        return {
          in: [
            { clipPath: `polygon(${dot}, ${dot}, ${dot}, ${dot})` },
            { clipPath: `polygon(${cx}px ${cy - r}px, ${cx + r}px ${cy}px, ${cx}px ${cy + r}px, ${cx - r}px ${cy}px)` },
          ],
        };
      }
      return {
        in: [
          { clipPath: "polygon(50% 50%, 50% 50%, 50% 50%, 50% 50%)" },
          { clipPath: "polygon(50% -60%, 160% 50%, 50% 160%, -60% 50%)" },
        ],
      };
    }
    case "box": {
      if (geo) {
        const { left: L, top: T, width: w, height: h, stageWidth: W, stageHeight: H } = geo;
        return {
          in: [
            { clipPath: `inset(${H / 2 - T}px ${L + w - W / 2}px ${T + h - H / 2}px ${W / 2 - L}px)` },
            { clipPath: `inset(${-T}px ${L + w - W}px ${T + h - H}px ${-L}px)` },
          ],
        };
      }
      return { in: [{ clipPath: "inset(50%)" }, { clipPath: "inset(0%)" }] };
    }

    case "blinds": {
      // Eight slats, each opening from its own edge: a repeated mask tile that grows to the full pitch.
      const pitch = `${100 / BLINDS}%`;
      if (horizontal(direction)) {
        const from = direction === "right" ? "0% 0%" : "100% 0%";
        return { in: [maskFrame(`0% 100%`, from), maskFrame(`${pitch} 100%`, from)] };
      }
      const from = direction === "down" ? "0% 0%" : "0% 100%";
      return { in: [maskFrame(`100% 0%`, from), maskFrame(`100% ${pitch}`, from)] };
    }
    case "flash":
      return {
        out: [{ filter: "brightness(1)", opacity: 1 }, { filter: "brightness(4)", opacity: 0 }],
        in: [{ filter: "brightness(4)", opacity: 0 }, { filter: "brightness(1)", opacity: 1 }],
      };
    case "flip": {
      const turn = (degrees: number): Keyframe => ({
        transform: `perspective(${PERSPECTIVE}px) rotate${axis}(${degrees}deg)`, backfaceVisibility: "hidden", transformOrigin: centre,
      });
      return { out: [turn(0), turn(-sign * 180)], in: [turn(sign * 180), turn(0)] };
    }
    case "cube": {
      // Two faces of a cube: each is pushed out by half the cube's depth, so the turn happens around its centre.
      const depth = (geo ? (axis === "Y" ? geo.stageWidth : geo.stageHeight) : axis === "Y" ? size?.width ?? 0 : size?.height ?? 0) / 2;
      const face = (degrees: number): Keyframe => ({
        transform: `perspective(${PERSPECTIVE}px) translateZ(${-depth}px) rotate${axis}(${degrees}deg) translateZ(${depth}px)`,
        backfaceVisibility: "hidden", transformOrigin: centre,
      });
      return { out: [face(0), face(-sign * 90)], in: [face(sign * 90), face(0)] };
    }
    case "blur":
      return {
        out: [{ filter: "blur(0px)", opacity: 1 }, { filter: "blur(24px)", opacity: 0 }],
        in: [{ filter: "blur(24px)", opacity: 0 }, { filter: "blur(0px)", opacity: 1 }],
      };
    case "glitch": {
      const jitter = (x: number, y: number, skew: number, filter: string, opacity: number): Keyframe => ({
        transform: `translate(${x}%, ${y}%) skewX(${skew}deg)`, filter, opacity,
      });
      const steps = [
        jitter(-4, 0, 10, "hue-rotate(90deg) saturate(3)", 0.9),
        jitter(5, 1, -12, "hue-rotate(-70deg) contrast(2)", 0.7),
        jitter(-2, -1, 6, "hue-rotate(160deg)", 0.5),
      ];
      return {
        out: [jitter(0, 0, 0, "none", 1), ...steps, jitter(3, 0, 0, "saturate(4)", 0)],
        in: [jitter(-3, 0, 0, "saturate(4)", 0), ...[...steps].reverse(), jitter(0, 0, 0, "none", 1)],
      };
    }
  }
}

const supports = (property: string, value: string): boolean =>
  typeof CSS !== "undefined" && typeof CSS.supports === "function" && CSS.supports(property, value);

/** Can this browser do what the effect needs? (Else the effect falls back to a fade.) */
function browserCan(type: ConcreteType): boolean {
  switch (type) {
    case "wipe": case "diagonal": case "split-open": case "split-close": case "circle": case "corner-circle":
    case "diamond": case "box":
      return supports("clip-path", "inset(0)");
    case "blinds":
      return supports("mask-image", FLAT_MASK) || supports("-webkit-mask-image", FLAT_MASK);
    case "flash": case "blur": case "glitch":
      return supports("filter", "blur(1px)");
    case "flip": case "cube":
      return supports("transform", "perspective(1px)");
    default:
      return true;
  }
}

/** Does this browser animate elements at all? Without it content is simply swapped. */
export function transitionsAvailable(): boolean {
  return typeof Element !== "undefined" && typeof Element.prototype.animate === "function";
}

/** Is a transition configured and possible? (container-manager.ts asks before it sets up two elements.) */
export function transitionWanted(): boolean {
  return config.type !== "none" && config.durationMs > 0 && transitionsAvailable();
}

export interface Choice {
  type: ConcreteType;
  direction: TransitionDirection;
}

/** What a random type picks from and whether each container picks for itself. */
function randomSpec(type: TransitionType): { perContainer: boolean; pool: ConcreteType[] } | null {
  if (!(RANDOM_TYPES as readonly string[]).includes(type)) return null;
  const limit: Effort = type.endsWith("-light") ? "light" : type.endsWith("-medium") ? "medium" : "heavy";
  const allowed: Effort[] = limit === "light" ? ["light"] : limit === "medium" ? ["light", "medium"] : ["light", "medium", "heavy"];
  return { perContainer: type.startsWith("random-container"), pool: CONCRETE_TYPES.filter((t) => allowed.includes(EFFORT[t])) };
}

function randomChoice(pool: ConcreteType[]): Choice {
  return {
    type: pool[Math.floor(Math.random() * pool.length)],
    direction: DIRECTIONS[Math.floor(Math.random() * DIRECTIONS.length)],
  };
}

// The "random…" types: one pick for everything that changes in the same scene change (see beginSceneTransition).
let sceneChoice: Choice | null = null;

/**
 * Called once at the start of a scene change: with a "random…" type every container then uses the same transition.
 * *continuing*: the old content already left (the outro at the end of the old scene), so keep its pick.
 */
export function beginSceneTransition(continuing = false): void {
  if (continuing && sceneChoice) return;
  const spec = randomSpec(config.type);
  sceneChoice = spec && !spec.perContainer ? randomChoice(spec.pool) : null;
}

/** The transition for one container's change: the Design's, or a random pick (see the "random…" types). */
export function chooseTransition(): Choice {
  const spec = randomSpec(config.type);
  const choice: Choice = spec
    ? (spec.perContainer ? randomChoice(spec.pool) : (sceneChoice ??= randomChoice(spec.pool)))
    : { type: config.type as ConcreteType, direction: config.direction };
  const reduced = typeof matchMedia === "function" && matchMedia("(prefers-reduced-motion: reduce)").matches;
  return reduced || !browserCan(choice.type) ? { ...choice, type: "fade" } : choice;
}

/**
 * Where each container sits in the order they start, 0 (first) … 1 (last), for the Design's stagger. *entries* are the
 * containers that change in one scene change, with their boxes in percent of the screen.
 */
export function computeStagger(
  entries: Array<{ id: string; top: number; left: number; width: number; height: number }>,
): Record<string, number> {
  const ranks: Record<string, number> = {};
  if (config.stagger === "none" || entries.length < 2) return ranks;
  const metric = (e: (typeof entries)[number], index: number): number => {
    switch (config.stagger) {
      case "order": return index;
      case "top-bottom": return e.top + e.height / 2;
      case "left-right": return e.left + e.width / 2;
      case "centre-out": return Math.hypot(e.left + e.width / 2 - 50, e.top + e.height / 2 - 50);
      default: return Math.random();
    }
  };
  const values = entries.map(metric);
  const min = Math.min(...values);
  const span = Math.max(...values) - min;
  entries.forEach((e, i) => (ranks[e.id] = span > 0 ? (values[i] - min) / span : 0));
  return ranks;
}

/**
 * What to animate when only one side exists: content that appears (nothing leaves) or disappears (nothing enters).
 * The types that only move the new content (cover, wipe, circle…) or only the old one (reveal) run the other way round.
 */
function planOneSided(
  plan: Plan, type: ConcreteType, direction: TransitionDirection, appearing: boolean, geo?: StageGeometry, size?: BoxSize,
): Frames | undefined {
  if (appearing) {
    if (plan.in) return plan.in;
    return plan.out ? [...plan.out].reverse() : undefined; // reveal: the new content comes back from where the old would have gone
  }
  if (plan.out) return plan.out;
  if (type === "cover" || type === "parallax" || type === "stack") return planFor("slide", direction, geo, size).out; // leaves the way a slide would
  return plan.in ? [...plan.in].reverse() : undefined; // wipe / circle / …: closes again
}

export interface PlayOptions {
  /** The transition to play (default: chooseTransition()); the outro at the end of a scene fixes it for the intro. */
  choice?: Choice;
  /**
   * Sequential mode with the two halves played apart: "out" animates only the leaving element (first half) and keeps
   * it in its final state until the returned function is called; "in" animates only the entering one, at once.
   */
  phase?: "out" | "in";
  /** The container's box: clipped along the movement while the transition runs (see slotClip). */
  slot?: HTMLElement;
  /** Set when the effect spans the whole slide ("slide" scope): this container's box in the stage. */
  geometry?: StageGeometry;
  /** The container's own size in px. */
  size?: BoxSize;
  /** Place of this container in the start order, 0…1 (see computeStagger): it starts later and runs shorter. */
  stagger?: number;
}

/**
 * Animate *entering* over *leaving*; either may be missing (content appears or disappears). *finish* is called once
 * when it ends (or at once when it is cancelled); the returned function ends the transition early.
 */
export function playTransition(
  leaving: HTMLElement | null, entering: HTMLElement | null, finish: () => void, options: PlayOptions = {},
): () => void {
  const { type, direction } = options.choice ?? chooseTransition();
  const plan = planFor(type, direction, options.geometry, options.size);
  // An effect across the whole slide runs through the neighbours on purpose: nothing to clip then.
  const clip = options.slot && !options.geometry ? slotClip(type, direction) : "";
  if (options.slot && clip) options.slot.style.clipPath = clip;
  const easing = plan.easing ?? "ease-in-out";
  // A staggered container starts later and takes less time, so the last one is done when the transition's time is.
  const timing = (duration: number, delay = 0): KeyframeAnimationOptions => {
    const rank = options.stagger;
    const t = rank === undefined
      ? { duration, delay }
      : { duration: duration * 0.6, delay: delay + duration * 0.4 * rank };
    return t.delay > 0 ? { duration: t.duration, delay: t.delay, easing, fill: "both" } : { duration: t.duration, easing, fill: "both" };
  };
  const frames = (side: "leaving" | "entering", appearing: boolean) =>
    (side === "leaving" ? plan.out : plan.in) ?? planOneSided(plan, type, direction, appearing, options.geometry, options.size);

  const animations: Animation[] = [];
  const full = config.durationMs;
  if (options.phase) {
    const half = full / 2;
    if (options.phase === "out" && leaving) {
      const out = frames("leaving", false);
      if (out) animations.push(leaving.animate(out, timing(half)));
    } else if (options.phase === "in" && entering) {
      const into = frames("entering", true);
      if (into) animations.push(entering.animate(into, timing(half)));
    }
  } else if (config.sequential) {
    // The old content leaves in the first half, the new one comes in during the second. Until its turn the new
    // content waits in its first keyframe (hidden), through the animation's backward fill.
    const half = full / 2;
    const out = frames("leaving", false);
    const into = frames("entering", true);
    if (leaving && out) animations.push(leaving.animate(out, timing(half)));
    if (entering && into) animations.push(entering.animate(into, timing(half, half)));
  } else if (leaving && entering) {
    leaving.style.zIndex = plan.oldOnTop ? "1" : "";
    if (plan.out) animations.push(leaving.animate(plan.out, timing(full)));
    if (plan.in) animations.push(entering.animate(plan.in, timing(full)));
  } else {
    const element = leaving ?? entering;
    const one = element ? planOneSided(plan, type, direction, !leaving, options.geometry, options.size) : undefined;
    if (element && one) animations.push(element.animate(one, timing(full)));
  }

  let done = false;
  let fallback: ReturnType<typeof setTimeout> | undefined;
  const end = () => {
    if (done) return;
    done = true;
    if (fallback !== undefined) clearTimeout(fallback);
    animations.forEach((a) => a.cancel());
    if (leaving) leaving.style.zIndex = "";
    if (options.slot && clip) options.slot.style.clipPath = "";
    finish();
  };
  if (animations.length === 0) {
    end();
    return end;
  }
  // An outro stays in its final state (the old content gone) until the scene change ends it.
  if (options.phase !== "out") {
    Promise.all(animations.map((a) => a.finished)).then(end, end);
    // A browser that does not advance animations (a hidden page, a throttled kiosk) never settles `finished`; the old
    // content must not stay on screen for ever then.
    fallback = setTimeout(end, config.durationMs + 250);
  }
  return end;
}
