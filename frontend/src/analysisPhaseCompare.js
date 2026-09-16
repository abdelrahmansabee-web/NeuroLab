/**
 * Clinic video analysis is one pipeline keyed by the slot (pre / post / baseline).
 * PRE is not a separate analyzer. POST uses the same arm and overlay builder.
 * Healthy side is the same builder on the contralateral arm.
 */

export const CLINIC_PHASES = ["pre", "post", "baseline"];

function parseArmSide(val) {
  const v = String(val || "").trim().toLowerCase();
  if (v === "left" || v === "1" || v === "l" || v === "sol") return "left";
  if (v === "right" || v === "2" || v === "r" || v === "sag") return "right";
  return null;
}

/** Clinic slot → kinematic trial_role. baseline is the healthy-side card. */
export function clinicTrialRoleFromPhase(phase) {
  const ph = String(phase || "pre").trim().toLowerCase();
  if (ph === "baseline" || ph === "healthy") return "healthy";
  if (ph === "pre" || ph === "post") return ph;
  return ph || "pre";
}

/**
 * Mirror of resolve_analysis_arm:
 * pre/post → paretic (stroke_side / affected_side)
 * baseline/healthy → contralateral
 */
export function resolveAnalysisArm(phase, strokeSide = "auto", affectedSide = "auto") {
  const ph = String(phase || "pre").trim().toLowerCase();
  const stroke = parseArmSide(strokeSide);
  if (ph === "baseline" || ph === "healthy") {
    if (stroke) return stroke === "left" ? "right" : "left";
    const explicit = parseArmSide(affectedSide);
    if (explicit) return explicit === "left" ? "right" : "left";
    return "auto";
  }
  const explicit = parseArmSide(affectedSide);
  if (explicit) return explicit;
  if (stroke) return stroke;
  return "auto";
}

/** Same FormData for every video except phase / filename / trial_role. */
export function videoAnalyzeFormFields(phase, { strokeSide = "auto", clinicalTask = "reach" } = {}) {
  const role = clinicTrialRoleFromPhase(phase);
  return {
    phase: String(phase || "pre"),
    trial_role: role,
    stroke_side: strokeSide,
    affected_side: strokeSide,
    // Server ignores this and uses resolve_analysis_arm(phase, …). Sent for all videos.
    arm_type: "paretic",
    clinical_task: clinicalTask,
    overlay_endpoint: "/overlay-data/{csv}",
  };
}

export function analysisProfileForRole(trialRole) {
  return String(trialRole || "").toLowerCase() === "healthy" ? "reference" : "affected";
}

/**
 * Filename substring inference used when the server does not receive trial_role.
 * "post" matches inside "posture"; "control" / "healthy" override a pre_ prefix.
 */
export function inferTrialRoleFromFilename(csvPath) {
  const stem = String(csvPath || "").split(/[/\\]/).pop().replace(/\.csv$/i, "").toLowerCase();
  if (["baseline", "healthy", "healthyside", "unaffected", "control"].some((k) => stem.includes(k))) {
    return "healthy";
  }
  if (stem.includes("post")) return "post";
  if (stem.includes("pre")) return "pre";
  return "unknown";
}

export function summarizeOverlayClock(overlay) {
  const frames = overlay?.frames || [];
  const t0 = frames[0]?.time;
  const tN = frames.length ? frames[frames.length - 1]?.time : null;
  return {
    overlay_version: overlay?.overlay_version ?? overlay?.version ?? null,
    affected_side: overlay?.affected_side ?? null,
    fps: overlay?.fps ?? null,
    duration_sec: overlay?.duration_sec ?? null,
    nframes: frames.length,
    t0: t0 ?? null,
    tN: tN ?? null,
  };
}

function num(v) {
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
}

/**
 * Compare overlay JSON clocks. Paint/mapping is phase-agnostic; this only
 * reports whether PRE's stored timebase differs from POST / healthy side.
 */
export function diffPhaseOverlayClocks(overlays = {}) {
  const keys = CLINIC_PHASES.filter((k) => overlays[k]?.frames?.length);
  const clocks = Object.fromEntries(keys.map((k) => [k, summarizeOverlayClock(overlays[k])]));
  const diffs = [];
  if (clocks.pre && clocks.post) {
    if (clocks.pre.affected_side && clocks.post.affected_side
      && clocks.pre.affected_side !== clocks.post.affected_side) {
      diffs.push("pre_post_affected_side");
    }
    if (clocks.pre.overlay_version != null && clocks.post.overlay_version != null
      && String(clocks.pre.overlay_version) !== String(clocks.post.overlay_version)) {
      diffs.push("pre_post_overlay_version");
    }
    const preFps = num(clocks.pre.fps);
    const postFps = num(clocks.post.fps);
    if (preFps && postFps && Math.abs(preFps - postFps) > 0.51) diffs.push("pre_post_fps");
  }
  if (clocks.pre && clocks.baseline) {
    if (clocks.pre.affected_side && clocks.baseline.affected_side
      && clocks.pre.affected_side === clocks.baseline.affected_side) {
      diffs.push("pre_baseline_same_arm");
    }
  }
  return { clocks, diffs };
}

/** What actually differs between the three clinic cards. */
export function compareClinicPhasePipelines({ strokeSide = "right" } = {}) {
  const pre = videoAnalyzeFormFields("pre", { strokeSide });
  const post = videoAnalyzeFormFields("post", { strokeSide });
  const baseline = videoAnalyzeFormFields("baseline", { strokeSide });
  const sharedKeys = ["stroke_side", "affected_side", "arm_type", "clinical_task", "overlay_endpoint"];
  const prePostSameRequest = sharedKeys.every((k) => pre[k] === post[k]);
  return {
    pre,
    post,
    baseline,
    preArm: resolveAnalysisArm("pre", strokeSide, strokeSide),
    postArm: resolveAnalysisArm("post", strokeSide, strokeSide),
    baselineArm: resolveAnalysisArm("baseline", strokeSide, strokeSide),
    preProfile: analysisProfileForRole(pre.trial_role),
    postProfile: analysisProfileForRole(post.trial_role),
    baselineProfile: analysisProfileForRole(baseline.trial_role),
    prePostSameRequest,
    prePostSameArm: true,
    healthyOppositeArm: true,
    overlayBuilderShared: true,
    // Same overlay builder. PRE lead is a long-clip analysis clock:
    // int(1000/fps) CSV time runs slow vs Safari, so 1:1 paint finishes first.
    preLeadIsShortOverlaySpan: true,
  };
}
