/**
 * High-performance motion tokens: opacity + transform only (avoid filter/height/width).
 * Springs tuned for snappy, low-latency feel on high-refresh displays.
 */

export const NL_SPRING_SNAPPY = {
  type: "spring",
  stiffness: 520,
  damping: 42,
  mass: 0.55,
  restDelta: 0.001,
  restSpeed: 0.001,
};

export const NL_SPRING_SHEET = {
  type: "spring",
  stiffness: 400,
  damping: 38,
  mass: 0.68,
  restDelta: 0.001,
  restSpeed: 0.001,
};

export const NL_SPRING_TOAST = {
  type: "spring",
  stiffness: 460,
  damping: 34,
  mass: 0.58,
};

export const NL_TWEEN_OVERLAY = {
  type: "tween",
  duration: 0.18,
  ease: [0.33, 1, 0.68, 1],
};

export const NL_TWEEN_MENU = {
  type: "tween",
  duration: 0.28,
  ease: [0.33, 1, 0.68, 1],
};

/** Section pane enter/exit — ease-out, no spring overshoot */
export const NL_TWEEN_SECTION = {
  type: "tween",
  duration: 0.34,
  ease: [0.22, 1, 0.36, 1],
};

export const NL_TWEEN_SECTION_EXIT = {
  type: "tween",
  duration: 0.22,
  ease: [0.4, 0, 0.6, 1],
};

export const NL_TRANSFORM_TRANSITION =
  "transform 0.26s cubic-bezier(0.33, 1, 0.68, 1)";

export const NL_LAYOUT_TRANSITION = "none";

export const NL_GPU_LAYER = {
  willChange: "transform, opacity",
  backfaceVisibility: "hidden",
  WebkitBackfaceVisibility: "hidden",
  transform: "translateZ(0)",
};

/** Full horizontal slide — transform only, smooth ease-out */
export const NL_TWEEN_SECTION_SLIDE = {
  type: "tween",
  duration: 0.42,
  ease: [0.22, 1, 0.36, 1],
};

const SLIDE_PANE_ABSOLUTE = {
  position: "absolute",
  top: 0,
  left: 0,
  right: 0,
  width: "100%",
};

/**
 * Forward: current pane → slides off to the right; next pane → from the left.
 * Back: opposite directions.
 * @param {boolean | null} reduceMotion
 */
export function sectionSlideVariants(reduceMotion) {
  const t = NL_TWEEN_SECTION_SLIDE;
  if (reduceMotion) {
    return {
      enter: { opacity: 0 },
      center: { opacity: 1, position: "relative" },
      exit: { opacity: 0, transition: { duration: 0.08 } },
    };
  }
  return {
    enter: (dir) => {
      const d = dir === 0 ? 1 : dir;
      return {
        ...SLIDE_PANE_ABSOLUTE,
        x: d >= 0 ? "-100%" : "100%",
        zIndex: 1,
      };
    },
    center: {
      x: 0,
      position: "relative",
      zIndex: 1,
      transition: t,
    },
    exit: (dir) => {
      const d = dir === 0 ? 1 : dir;
      return {
        ...SLIDE_PANE_ABSOLUTE,
        x: d >= 0 ? "100%" : "-100%",
        zIndex: 2,
        transition: t,
      };
    },
  };
}

/** @deprecated */
export function sectionStackVariants(reduceMotion) {
  return sectionSlideVariants(reduceMotion);
}

/** @deprecated */
export function sectionTransitionProps(reduceMotion, direction = 0) {
  if (reduceMotion) {
    return {
      initial: { opacity: 0 },
      animate: { opacity: 1 },
      exit: { opacity: 0 },
      transition: { duration: 0.01 },
    };
  }
  const slide = direction === 0 ? 0 : direction > 0 ? 18 : -18;
  const exitSlide = direction === 0 ? 0 : direction > 0 ? -14 : 14;
  return {
    initial: { opacity: 0, x: slide, y: 4 },
    animate: {
      opacity: 1,
      x: 0,
      y: 0,
      transition: NL_TWEEN_SECTION,
    },
    exit: {
      opacity: 0,
      x: exitSlide,
      y: -3,
      transition: NL_TWEEN_SECTION_EXIT,
    },
  };
}
