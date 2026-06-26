/**
 * PETTLEP AOMI RCT — Analysis plan, master dataset, SPSS syntax, preliminary stats.
 * Aligned with manuscript: 2×2 mixed ANOVA (Group × Time), n=28, primary = SPARC.
 */

export const STUDY_DESIGN = {
  title: "Immediate Effects of PETTLEP-Based AOMI on Upper Limb Kinematics",
  design: "Single-blind, pretest–posttest, parallel RCT",
  groups: { "1": "AOMI", "2": "Control" },
  targetN: 28,
  perGroup: 14,
  alpha: 0.05,
  primaryOutcome: "sparc",
};

/** Manuscript-aligned kinematic variables (side-view pipeline) */
export const KINEMATIC_VARS = [
  { key: "sparc", label: "SPARC (smoothness)", unit: "index", dir: "higher", tier: "primary" },
  { key: "trunk_ratio", label: "Trunk ratio", unit: "ratio", dir: "lower", tier: "secondary" },
  { key: "shoulder_vert_norm", label: "Shoulder elevation (norm)", unit: "norm", dir: "lower", tier: "secondary" },
  { key: "hand_displacement_norm", label: "Hand reach (peak cm)", unit: "cm", dir: "higher", tier: "secondary" },
  { key: "movement_time_sec", label: "Movement time", unit: "s", dir: "lower", tier: "secondary" },
  { key: "peak_velocity_cm_s", label: "Peak velocity", unit: "cm/s", dir: "higher", tier: "secondary", fallback: "peak_velocity_px_s" },
];

export const KINEMATIC_DISPLAY_ORDER = [
  "sparc",
  "trunk_ratio",
  "shoulder_vert_norm",
  "hand_displacement_norm",
  "peak_velocity_cm_s",
  "movement_time_sec",
];

/** Manuscript / ethics-form reference pattern (Pre → Post → Healthy) */
export const MANUSCRIPT_KINEMATIC_TARGETS = {
  sparc: { pre: -1.85, post: -1.65, healthy: -1.45 },
  trunk_ratio: { pre: 32.0, post: 18.0, healthy: 3.0 },
  shoulder_vert_norm: { pre: 18.0, post: 12.0, healthy: 6.5 },
  hand_displacement_norm: { pre: 22, post: 28, healthy: 38 },
  peak_velocity_cm_s: { pre: 22.0, post: 28.0, healthy: 19.0 },
};

export function orderedKinematicVars() {
  const byKey = Object.fromEntries(KINEMATIC_VARS.map((v) => [v.key, v]));
  return KINEMATIC_DISPLAY_ORDER.map((k) => byKey[k]).filter(Boolean);
}

export const CLINICAL_VARS = [
  { pre: "WMFT_Rating_Pre", post: "WMFT_Rating_Post", label: "WMFT-4 rating sum", dir: "higher", test: "mixed", tier: "secondary" },
  { pre: "WMFT_Time_Pre", post: "WMFT_Time_Post", label: "WMFT-4 time sum (s)", dir: "lower", test: "mixed", tier: "secondary" },
  { pre: "VAMS_Happy_Pre", post: "VAMS_Happy_Post", label: "VAMS Happy", dir: "higher", test: "mixed", tier: "secondary" },
  { pre: "VAMS_Calm_Pre", post: "VAMS_Calm_Post", label: "VAMS Calm", dir: "higher", test: "mixed", tier: "secondary" },
  { pre: "VAMS_Sad_Pre", post: "VAMS_Sad_Post", label: "VAMS Sad", dir: "lower", test: "mixed", tier: "secondary" },
  { pre: "VAMS_Tense_Pre", post: "VAMS_Tense_Post", label: "VAMS Tense", dir: "lower", test: "mixed", tier: "secondary" },
  { pre: "KVIQ_Vis_Pre", post: "KVIQ_Vis_Post", label: "KVIQ-10 visual total", dir: "higher", test: "mixed", tier: "moderator" },
  { pre: "KVIQ_Kin_Pre", post: "KVIQ_Kin_Post", label: "KVIQ-10 kinesthetic total", dir: "higher", test: "mixed", tier: "moderator" },
  { pre: "VAS_Pre", post: "VAS_Post", label: "VAS pain (mean)", dir: "lower", test: "mixed", tier: "secondary" },
  { pre: "MDRS_Control_Pre", post: "MDRS_Difference_Post", label: "MDRS motor control change", dir: "higher", test: "post_only", tier: "secondary" },
  { pre: null, post: "IPAQ_MET", label: "IPAQ total MET-min/wk", dir: "none", test: "descriptive", tier: "moderator" },
];

export const SPSS_WORKFLOW = [
  { step: 1, title: "Data import", spss: "GET DATA → master_study_data.csv → SAVE master_study.sav" },
  { step: 2, title: "Variable labels & deltas", spss: "COMPUTE delta_* = *_Post − *_Pre for 6 kinematic + clinical vars" },
  { step: 3, title: "Baseline equivalence", spss: "T-TEST / Mann-Whitney / Chi-square on Pre scores & demographics" },
  { step: 4, title: "Normality (Shapiro–Wilk)", spss: "EXAMINE … BY Group on Pre, Post, and Δ for each DV" },
  { step: 5, title: "Primary analysis", spss: "GLM sparc Pre Post BY Group /WSFACTOR=time 2 — α=.05 uncorrected" },
  { step: 6, title: "Secondary kinematic (5 GLMs)", spss: "trunk_ratio, shoulder_vert_norm, hand_displacement_norm, movement_time_sec, peak_velocity_px_s; Holm–Bonferroni k=5" },
  { step: 8, title: "Clinical scales", spss: "GLM WMFT-4, VAMS-4, VAS, KVIQ; MWU/Wilcoxon if non-normal" },
  { step: 9, title: "MDRS post-only", spss: "Mann-Whitney MDRS_Difference_Post BY Group" },
  { step: 10, title: "Moderators", spss: "CORRELATIONS KVIQ-10 Pre with Δ kinematic; split by Group" },
  { step: 11, title: "Sensitivity", spss: "MIXED models + LOCF imputation (ITT)" },
  { step: 12, title: "Report", spss: "OMS tables → APA; partial η² ≥ .14 = large (Cohen, 1988)" },
];

const LEGACY_KIN_MAP = {
  sparc: ["sparc"],
  trunk_ratio: ["trunk_ratio", "total_trunk_palm_ratio"],
  shoulder_vert_norm: ["shoulder_vert_norm", "shoulder_elevation_norm"],
  hand_displacement_norm: ["hand_displacement_norm", "hand_disp_sw", "reach_amplitude_sw", "lat_range_sw"],
  movement_time_sec: ["movement_time_sec", "total_duration_s", "duration"],
  peak_velocity_cm_s: ["peak_velocity_cm_s", "peak_velocity_px_s", "peak_velocity_m_s", "total_peak_velocity"],
};

export function pickKinField(result, canonicalKey, fallbackKey = null) {
  if (!result || typeof result !== "object") return null;
  const keys = [canonicalKey];
  if (fallbackKey) keys.push(fallbackKey);
  const aliases = (LEGACY_KIN_MAP[canonicalKey] || []).concat(keys);
  for (const k of aliases) {
    const v = result[k];
    if (v !== undefined && v !== null && v !== "" && !Number.isNaN(Number(v))) return Number(v);
  }
  return null;
}

export function normalizeKinematicResult(result) {
  if (!result) return null;
  const out = {};
  KINEMATIC_VARS.forEach(({ key, fallback }) => {
    const v = pickKinField(result, key, fallback);
    if (v !== null) out[key] = v;
  });
  return Object.keys(out).length ? out : null;
}

/** Pre→Post % (calc_improvement — exact Python port). */
export function calcImprovement(pre, post, direction) {
  const preN = Number(pre);
  const postN = Number(post);
  if (Number.isNaN(preN) || Number.isNaN(postN)) return null;
  if (direction === "higher") {
    return (postN - preN) / Math.abs(preN) * 100;
  }
  return (preN - postN) / preN * 100;
}

/** Post→Healthy % or gap (calc_gap — exact Python port). */
export function calcGap(post, healthy, direction) {
  const postN = Number(post);
  const healthyN = Number(healthy);
  if (Number.isNaN(postN) || Number.isNaN(healthyN)) return null;
  if (direction === "higher") {
    return Math.abs(healthyN - postN) / Math.abs(healthyN) * 100;
  }
  return postN - healthyN;
}

export function formatKinPrePostPct(pct) {
  if (pct == null || Number.isNaN(pct)) return null;
  return `تحسن ${Math.abs(pct).toFixed(0)}%`;
}

export function formatKinPostHealthyPct(pct) {
  if (pct == null || Number.isNaN(pct)) return null;
  return `فرق ${Math.abs(pct).toFixed(1)}%`;
}

/**
 * Recovery toward healthy-side baseline (Fugl-Meyer style index).
 * higher-is-better: 100×(post−pre)/(healthy−pre)
 * lower-is-better:    100×(pre−post)/(pre−healthy) — only when pre is worse than healthy.
 */
export function computeRecoveryPct(pre, post, healthy, direction) {
  if (pre == null || post == null || healthy == null || direction === "none") return null;
  const preN = Number(pre);
  const postN = Number(post);
  const helN = Number(healthy);
  if ([preN, postN, helN].some((x) => Number.isNaN(x))) return null;

  let pct;
  if (direction === "higher") {
    if (helN <= preN) return { valid: false, reason: "healthy_not_beyond_pre" };
    const denom = helN - preN;
    if (Math.abs(denom) < 1e-9) return { valid: false, reason: "pre≈healthy" };
    pct = ((postN - preN) / denom) * 100;
  } else if (direction === "lower") {
    if (preN <= helN) return { valid: false, reason: "pre_at_or_better_than_healthy" };
    const denom = preN - helN;
    if (Math.abs(denom) < 1e-9) return { valid: false, reason: "pre≈healthy" };
    pct = ((preN - postN) / denom) * 100;
  } else {
    return null;
  }

  const improved = pct > 0;
  const text = `${pct >= 0 ? "" : ""}${pct.toFixed(0)}%`;
  return { valid: true, pct, improved, text };
}

/** Whether pre/post/baseline values are comparable for cross-phase deltas (view/arm gates). */
export function kinCrossPhaseComparable(kinematicsResults, metricKey, armForPhase = null) {
  const phases = ["pre", "post", "baseline"].filter((p) => kinematicsResults?.[p]);
  if (phases.length < 2) return true;

  if (metricKey === "sparc") {
    return phases.every((p) => kinematicsResults[p]?.sparc_comparable !== false);
  }

  return true;
}

/** Key metrics for per-patient recovery summary (when re-recording is not possible). */
export const RECOVERY_SUMMARY_KEYS = [
  "sparc",
  "trunk_ratio",
  "shoulder_vert_norm",
  "hand_displacement_norm",
];

/** Read pre/post/baseline kinematics from patient record. */
export function getPatientKinPhase(patient, phase) {
  const kin = patient?.kinematics || {};
  const key = phase === "healthy" ? "baseline" : phase;
  const raw =
    kin[`result_${key}`] ||
    patient?.[`result_${key}`] ||
    kin.analysisResults?.[key] ||
    kin[key];
  return normalizeKinematicResult(raw);
}

function kinCell(m, key) {
  if (!m) return "";
  const v = pickKinField(m, key);
  return v !== null && v !== undefined ? v : "";
}

function appendManuscriptAliases(row, suffix, m) {
  // Legacy CSV columns (optional backward compatibility)
  const legacy = {
    total_trunk_palm_ratio: kinCell(m, "trunk_ratio"),
    total_duration_s: kinCell(m, "movement_time_sec"),
    total_peak_velocity: kinCell(m, "peak_velocity_cm_s"),
  };
  Object.entries(legacy).forEach(([k, v]) => {
    if (v !== "") row[`${k}_${suffix}`] = v;
  });
}

export function applyLOCF(rows) {
  return rows.map((row) => {
    const out = { ...row, LOCF_imputed: 0 };
    Object.keys(row).forEach((col) => {
      if (!col.endsWith("_Post")) return;
      const v = row[col];
      if (v !== "" && v !== null && v !== undefined) return;
      const preCol = col.replace(/_Post$/, "_Pre");
      const pre = row[preCol];
      if (pre !== "" && pre !== null && pre !== undefined) {
        out[col] = pre;
        out.LOCF_imputed = 1;
      }
    });
    return out;
  });
}

export function buildMasterRow(patient, wmftItems, kgiaMovements, ipaqActs) {
  const d = patient?.demographics || {};
  if (!d.participantId && !d.name) return null;

  const row = {
    ID: d.participantId || "",
    Group: d.group || "",
    Age: d.age ?? "",
    Sex: d.sex ?? "",
    TimeSinceStroke: d.timeSinceStroke ?? "",
    StrokeType: d.strokeType ?? "",
    AffectedSide: d.side ?? "",
    MAS: d.mas ?? "",
    MRC: d.mrc ?? "",
  };

  ["pre", "post"].forEach((tp) => {
    const m = getPatientKinPhase(patient, tp);
    const suffix = tp === "pre" ? "Pre" : "Post";
    KINEMATIC_VARS.forEach(({ key }) => {
      row[`${key}_${suffix}`] = kinCell(m, key);
    });
    appendManuscriptAliases(row, suffix, m);
  });

  const mHealthy = getPatientKinPhase(patient, "baseline");
  KINEMATIC_VARS.forEach(({ key }) => {
    row[`${key}_Healthy`] = kinCell(mHealthy, key);
  });
  appendManuscriptAliases(row, "Healthy", mHealthy);

  const wmft = patient.wmft || {};
  let rtPre = 0, rtPost = 0, rrPre = 0, rrPost = 0, rc = 0;
  wmftItems.forEach((t) => {
    const preT = parseFloat(wmft[t.id]?.pre?.time);
    const postT = parseFloat(wmft[t.id]?.post?.time);
    const preR = parseFloat(wmft[t.id]?.pre?.rating);
    const postR = parseFloat(wmft[t.id]?.post?.rating);
    if (!isNaN(preT)) rtPre += preT;
    if (!isNaN(postT)) rtPost += postT;
    if (!isNaN(preR)) { rrPre += preR; rc++; }
    if (!isNaN(postR)) rrPost += postR;
  });
  row.WMFT_Time_Pre = rtPre || "";
  row.WMFT_Time_Post = rtPost || "";
  row.WMFT_Rating_Pre = rc > 0 ? rrPre : "";
  row.WMFT_Rating_Post = rc > 0 ? rrPost : "";

  const vams = patient.vams || {};
  ["happy", "sad", "calm", "tense"].forEach((k) => {
    const cap = k.charAt(0).toUpperCase() + k.slice(1);
    row[`VAMS_${cap}_Pre`] = vams[k]?.pre ?? "";
    row[`VAMS_${cap}_Post`] = vams[k]?.post ?? "";
  });

  const kgia = patient.kgia || {};
  let visPre = 0, visPost = 0, kinPre = 0, kinPost = 0, vc = 0, kc = 0;
  kgiaMovements.forEach((_, mi) => {
    const v = kgia[`${mi}_gorsel`];
    if (v) {
      const p = parseFloat(v.once), q = parseFloat(v.sonra);
      if (!isNaN(p)) { visPre += p; vc++; }
      if (!isNaN(q)) visPost += q;
    }
    const k = kgia[`${mi}_kinestetik`];
    if (k) {
      const p = parseFloat(k.once), q = parseFloat(k.sonra);
      if (!isNaN(p)) { kinPre += p; kc++; }
      if (!isNaN(q)) kinPost += q;
    }
  });
  row.KVIQ_Vis_Pre = vc > 0 ? visPre : "";
  row.KVIQ_Vis_Post = vc > 0 ? visPost : "";
  row.KVIQ_Kin_Pre = kc > 0 ? kinPre : "";
  row.KVIQ_Kin_Post = kc > 0 ? kinPost : "";

  const ipaq = patient.ipaq || {};
  let met = 0;
  ipaqActs.forEach((a) => {
    met += (parseFloat(ipaq[a.id]?.sure) || 0) * (parseFloat(ipaq[a.id]?.gun) || 0) * a.met;
  });
  row.IPAQ_MET = met > 0 ? Math.round(met) : "";

  const vas = patient.vas || {};
  let vp = 0, vq = 0, pc = 0, qc = 0;
  ["rest", "activity", "night"].forEach((k) => {
    const p = parseFloat(vas[k]?.pre), q = parseFloat(vas[k]?.post);
    if (!isNaN(p)) { vp += p; pc++; }
    if (!isNaN(q)) { vq += q; qc++; }
  });
  row.VAS_Pre = pc > 0 ? +(vp / pc).toFixed(1) : "";
  row.VAS_Post = qc > 0 ? +(vq / qc).toFixed(1) : "";

  const mc = patient.motorchange || {};
  row.MDRS_Control_Pre = mc.control ?? "";
  row.MDRS_Difference_Post = mc.difference ?? "";

  return row;
}

export function buildMasterDataset(patients, wmftItems, kgiaMovements, ipaqActs, { locf = false } = {}) {
  const rows = patients
    .map((p) => buildMasterRow(p, wmftItems, kgiaMovements, ipaqActs))
    .filter(Boolean);
  return locf ? applyLOCF(rows) : rows;
}

function cap(s) {
  return s.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function spssMixedGlm(l, key, label, opts = {}) {
  const { primary = false, comment = "" } = opts;
  if (comment) l(`* ${comment}`);
  l(`* --- ${label}${primary ? " [PRIMARY — α=.05 uncorrected]" : ""} ---`);
  l(`GLM ${key}_Pre ${key}_Post BY Group`);
  l("  /WSFACTOR=time 2 Polynomial");
  l("  /METHOD=SSTYPE(3)");
  if (primary) {
    l("  /EMMEANS=TABLES(time) COMPARE ADJ(BONFERRONI)");
    l("  /EMMEANS=TABLES(Group*time) COMPARE(time) ADJ(BONFERRONI)");
  }
  l("  /PRINT=DESCRIPTIVE ETASQ HOMOGENEITY");
  l("  /CRITERIA=ALPHA(.05)");
  l("  /WSDESIGN=time.");
  l("");
}

function spssClinicalGlm(l, pre, post, label) {
  l(`* --- ${label} ---`);
  l(`GLM ${pre} ${post} BY Group /WSFACTOR=time 2 /METHOD=SSTYPE(3) /PRINT=DESCRIPTIVE ETASQ /WSDESIGN=time.`);
  l("");
}

export function generateStudySPSSSyntax(csvFilename = "master_study_data.csv") {
  const lines = [];
  const l = (s = "") => lines.push(s);

  const kinPrimary = KINEMATIC_VARS.filter((k) => k.tier === "primary");
  const kinSecondary = KINEMATIC_VARS.filter((k) => k.tier === "secondary");
  const kinExploratory = KINEMATIC_VARS.filter((k) => k.tier === "exploratory");
  const kinAll = [...kinPrimary, ...kinSecondary, ...kinExploratory];

  l("* =================================================================");
  l("* PETTLEP AOMI RCT — SPSS Analysis Syntax (NeuroLab v6 auto-generated)");
  l("* Design: 2 (Group: AOMI vs Control) × 2 (Time: Pre, Post) mixed ANOVA");
  l("* Primary outcome: SPARC (α=.05 uncorrected); secondary kinematics Holm k=5");
  l("* References: Field (2018); Cohen (1988); Schulz et al. CONSORT 2010");
  l("* =================================================================");
  l("");

  l("* --- 1. IMPORT (adjust FILE path to your machine) ---");
  l(`GET DATA /TYPE=TXT`);
  l(`  /FILE='${csvFilename}'`);
  l("  /DELCASE=LINE");
  l("  /DELIMITERS=\",\"");
  l("  /QUALIFIER='\"'");
  l("  /ARRANGEMENT=DELIMITED");
  l("  /FIRSTCASE=2");
  l("  /IMPORTCASE=ALL");
  l("  /VARIABLES=");
  l("  ID A10 Group F2.0 Age F8.2 Sex F2.0 TimeSinceStroke F8.2 StrokeType F2.0");
  l("  AffectedSide F2.0 MAS F8.2 MRC F8.2.");
  l("CACHE.");
  l("EXECUTE.");
  l("");
  l("VALUE LABELS Group 1 'AOMI' 2 'Control'.");
  l("VALUE LABELS Sex 1 'Male' 2 'Female'.");
  l("EXECUTE.");
  l("");

  l("* --- 2. VARIABLE LABELS (kinematic) ---");
  kinAll.forEach(({ key, label, unit }) => {
    l(`VARIABLE LABELS ${key}_Pre '${label} — Pre (${unit})'.`);
    l(`VARIABLE LABELS ${key}_Post '${label} — Post (${unit})'.`);
  });
  l("EXECUTE.");
  l("");

  l("* --- 3. DELTA SCORES (Post − Pre) ---");
  kinAll.forEach(({ key, label }) => {
    l(`COMPUTE delta_${key} = ${key}_Post - ${key}_Pre.`);
    l(`VARIABLE LABELS delta_${key} '${label} change (Post-Pre)'.`);
  });
  CLINICAL_VARS.filter((c) => c.pre && c.post && c.test === "mixed").forEach((c) => {
    const base = c.pre.replace("_Pre", "");
    l(`COMPUTE delta_${base} = ${c.post} - ${c.pre}.`);
    l(`VARIABLE LABELS delta_${base} '${c.label} change (Post-Pre)'.`);
  });
  l("EXECUTE.");
  l("");

  l("* --- 4. BASELINE EQUIVALENCE ---");
  l("T-TEST GROUPS=Group(1 2)");
  l("  /VARIABLES=Age TimeSinceStroke MAS MRC sparc_Pre trunk_ratio_Pre shoulder_vert_norm_Pre.");
  l("CROSSTABS Sex StrokeType AffectedSide BY Group /STATISTICS=CHISQ.");
  l("NPAR TESTS /MANN-WHITNEY MAS MRC BY Group(1 2).");
  l("");

  l("* --- 5. NORMALITY (Shapiro–Wilk via EXAMINE) ---");
  l("* Run for each DV if needed; example for primary:");
  l("EXAMINE VARIABLES=sparc_Pre sparc_Post delta_sparc BY Group(1 2)");
  l("  /PLOT BOXPLOT HISTOGRAM NPPLOT");
  l("  /STATISTICS DESCRIPTIVES");
  l("  /CINEMETRIC ALPHA(0.05).");
  l("* Decision: p≥.05 → parametric GLM; p<.05 → Wilcoxon (within) + Mann-Whitney (Δ between).");
  l("");

  l("* --- 6. PRIMARY OUTCOME (SPARC, α=.05 uncorrected) ---");
  kinPrimary.forEach(({ key, label }) => {
    spssMixedGlm(l, key, label, { primary: true });
  });
  l("");

  if (kinSecondary.length) {
  l("* --- 7. SECONDARY KINEMATIC ---");
  l(`* Multiplicity: Holm–Bonferroni across ${kinSecondary.length} secondary tests below.`);
  kinSecondary.forEach(({ key, label }) => {
    spssMixedGlm(l, key, label);
  });

  l(`* --- 7b. HOLM–BONFERRONI (secondary kinematic family, k=${kinSecondary.length}) ---`);
  l(`* 1) Record Group×Time interaction p-values from step 7.`);
  l(`* 2) Sort p-values ascending: p(1) ≤ … ≤ p(${kinSecondary.length}).`);
  l(`* 3) Compare p(k) to α/(${kinSecondary.length}−k+1); report uncorrected + Holm-adjusted.`);
  l("");
  }

  if (kinExploratory.length) {
  l("* --- 8. EXPLORATORY KINEMATIC (no correction) ---");
  kinExploratory.forEach(({ key, label }) => {
    spssMixedGlm(l, key, label, { comment: "Exploratory — interpret cautiously" });
  });
  l("");
  }

  l("* --- 9. CLINICAL OUTCOMES ---");
  spssClinicalGlm(l, "WMFT_Rating_Pre", "WMFT_Rating_Post", "WMFT-4 rating sum");
  spssClinicalGlm(l, "WMFT_Time_Pre", "WMFT_Time_Post", "WMFT-4 time sum");
  ["Happy", "Calm", "Sad", "Tense"].forEach((d) => {
    spssClinicalGlm(l, `VAMS_${d}_Pre`, `VAMS_${d}_Post`, `VAMS ${d}`);
  });
  spssClinicalGlm(l, "VAS_Pre", "VAS_Post", "VAS pain (mean)");
  spssClinicalGlm(l, "KVIQ_Vis_Pre", "KVIQ_Vis_Post", "KVIQ-10 visual total");
  spssClinicalGlm(l, "KVIQ_Kin_Pre", "KVIQ_Kin_Post", "KVIQ-10 kinesthetic total");
  l("");

  l("* --- 10. MDRS (post-only perceived motor control change) ---");
  l("NPAR TESTS /MANN-WHITNEY MDRS_Difference_Post BY Group(1 2).");
  l("T-TEST GROUPS=Group(1 2) /VARIABLES=MDRS_Difference_Post MDRS_Control_Pre.");
  l("");

  l("* --- 11. MODERATORS & EXPLORATORY CORRELATIONS ---");
  l("SPLIT FILE LAYERED BY Group.");
  l("CORRELATIONS /VARIABLES=KVIQ_Vis_Pre KVIQ_Kin_Pre");
  l("  delta_sparc delta_trunk_ratio delta_shoulder_vert_norm delta_hand_displacement_norm delta_movement_time_sec delta_peak_velocity_px_s");
  l("  /PRINT=TWOTAIL NOSIG /MISSING=PAIRWISE.");
  l("SPLIT FILE OFF.");
  l("CORRELATIONS /VARIABLES=delta_VAMS_Happy delta_VAMS_Calm delta_sparc delta_trunk_ratio /PRINT=TWOTAIL NOSIG.");
  l("FREQUENCIES IPAQ_MET /STATISTICS=MEAN STDDEV MEDIAN.");
  l("");

  l("* --- 12. NON-PARAMETRIC BACKUP (if Shapiro p < .05) ---");
  l("* Within AOMI: NPAR TESTS /WILCOXON sparc_Pre WITH sparc_Post (PAIRED).");
  l("* Within Control: repeat Wilcoxon per group.");
  l("* Between groups on Δ: NPAR TESTS /MANN-WHITNEY delta_sparc BY Group(1 2).");
  l("");

  l("* --- 13. SENSITIVITY: LOCF + MIXED MODELS (ITT) ---");
  l("* LOCF: replace missing Post with Pre (document n imputed per variable).");
  l("* Example mixed model for primary:");
  l("* MIXED sparc BY Group time /FIXED=Group time Group*time /REPEATED=time | SUBJECT(ID) COVTYPE(AR1).");
  l("");

  l("* --- 14. SAVE ---");
  l("SAVE OUTFILE='master_study_analyzed.sav' /COMPRESSED.");
  l("EXECUTE.");

  return lines.join("\n");
}

/** Client-side outcome analysis (preliminary; confirm in SPSS). */
export function analyzeOutcome(rows, spec) {
  const { pre, post, label, dir } = spec;
  if (!pre || !post) return null;

  const aomi = rows.filter((r) => r.Group === "1");
  const ctrl = rows.filter((r) => r.Group === "2");

  const pull = (list, col) => list.map((r) => parseFloat(r[col])).filter((v) => !isNaN(v));

  const aPre = pull(aomi, pre), aPost = pull(aomi, post);
  const cPre = pull(ctrl, pre), cPost = pull(ctrl, post);

  const stats = { label, pre, post, nAomi: aomi.length, nCtrl: ctrl.length };

  if (aPre.length >= 2) stats.aomiPre = { mean: +mean(aPre).toFixed(3), sd: +sd(aPre).toFixed(3), n: aPre.length };
  if (aPost.length >= 2) stats.aomiPost = { mean: +mean(aPost).toFixed(3), sd: +sd(aPost).toFixed(3), n: aPost.length };
  if (cPre.length >= 2) stats.ctrlPre = { mean: +mean(cPre).toFixed(3), sd: +sd(cPre).toFixed(3), n: cPre.length };
  if (cPost.length >= 2) stats.ctrlPost = { mean: +mean(cPost).toFixed(3), sd: +sd(cPost).toFixed(3), n: cPost.length };

  const pairRows = (list) => {
    const preArr = [], postArr = [];
    list.forEach((r) => {
      const p = parseFloat(r[pre]), q = parseFloat(r[post]);
      if (!isNaN(p) && !isNaN(q)) { preArr.push(p); postArr.push(q); }
    });
    return { preArr, postArr };
  };
  const aPair = pairRows(aomi);
  const cPair = pairRows(ctrl);
  const dA = aPair.preArr.map((p, i) => aPair.postArr[i] - p);
  const dC = cPair.preArr.map((p, i) => cPair.postArr[i] - p);

  stats.withinAomi = aPair.preArr.length >= 2 ? pairedTest(aPair.preArr, aPair.postArr) : null;
  stats.withinCtrl = cPair.preArr.length >= 2 ? pairedTest(cPair.preArr, cPair.postArr) : null;
  stats.betweenDelta = dA.length >= 2 && dC.length >= 2 ? welchTest(dA, dC) : null;
  stats.baseline = aPre.length >= 2 && cPre.length >= 2 ? welchTest(aPre, cPre) : null;
  stats.dir = dir;
  stats.isPrimary = pre.includes("sparc");

  return stats;
}

export function analyzeAllOutcomes(rows) {
  const specs = [];

  KINEMATIC_VARS.forEach(({ key, label, dir, tier }) => {
    specs.push({ pre: `${key}_Pre`, post: `${key}_Post`, label, dir, tier: `kinematic-${tier}` });
  });

  CLINICAL_VARS.filter((c) => c.test === "mixed").forEach((c) => {
    specs.push({ ...c, tier: "clinical" });
  });

  return specs.map((s) => analyzeOutcome(rows, s)).filter(Boolean);
}

function mean(a) {
  return a.reduce((s, x) => s + x, 0) / a.length;
}
function sd(a) {
  if (a.length < 2) return 0;
  const m = mean(a);
  return Math.sqrt(a.reduce((s, x) => s + (x - m) ** 2, 0) / (a.length - 1));
}
function pairedTest(a, b) {
  const d = a.map((x, i) => b[i] - x);
  const m = mean(d), s = sd(d), n = d.length;
  if (n < 2 || s === 0) return { test: "paired-t", t: 0, p: 1, es: 0, n };
  const t = m / (s / Math.sqrt(n));
  const p = 2 * (1 - tDistCdf(Math.abs(t), n - 1));
  return { test: "paired-t", t, p, es: m / s, n };
}
function welchTest(a, b) {
  const m1 = mean(a), m2 = mean(b), s1 = sd(a), s2 = sd(b), n1 = a.length, n2 = b.length;
  if (n1 < 2 || n2 < 2) return null;
  const se = Math.sqrt(s1 * s1 / n1 + s2 * s2 / n2);
  const t = (m1 - m2) / (se || 1e-9);
  const num = (s1 * s1 / n1 + s2 * s2 / n2) ** 2;
  const den = (s1 * s1 / n1) ** 2 / (n1 - 1) + (s2 * s2 / n2) ** 2 / (n2 - 1);
  const df = den > 0 ? num / den : n1 + n2 - 2;
  const p = 2 * (1 - tDistCdf(Math.abs(t), df));
  const pooled = Math.sqrt(((n1 - 1) * s1 * s1 + (n2 - 1) * s2 * s2) / (n1 + n2 - 2));
  return { test: "Welch", t, p, es: pooled > 0 ? (m1 - m2) / pooled : 0, df, n1, n2 };
}
function tDistCdf(t, df) {
  const x = df / (df + t * t);
  return 1 - 0.5 * incompleteBeta(df / 2, 0.5, x);
}
function incompleteBeta(a, b, x) {
  if (x <= 0) return 0;
  if (x >= 1) return 1;
  const lnBeta = lnGamma(a) + lnGamma(b) - lnGamma(a + b);
  const front = Math.exp(Math.log(x) * a + Math.log(1 - x) * b - lnBeta) / a;
  let f = 1, c = 1, d = 0;
  for (let i = 0; i <= 200; i++) {
    const m = i / 2;
    let num;
    if (i === 0) num = 1;
    else if (i % 2 === 0) num = (m * (b - m) * x) / ((a + 2 * m - 1) * (a + 2 * m));
    else num = -((a + m) * (a + b + m) * x) / ((a + 2 * m) * (a + 2 * m + 1));
    d = 1 + num * d; if (Math.abs(d) < 1e-30) d = 1e-30; d = 1 / d;
    c = 1 + num / c; if (Math.abs(c) < 1e-30) c = 1e-30;
    f *= c * d;
    if (Math.abs(c * d - 1) < 1e-10) break;
  }
  return front * (f - 1);
}
function lnGamma(z) {
  const g = 7;
  const c = [0.99999999999980993, 676.5203681218851, -1259.1392167224028, 771.32342877765313, -176.61502916214059, 12.507343278686905, -0.13857109526572012, 9.9843695780195716e-6, 1.5056327351493116e-7];
  if (z < 0.5) return Math.log(Math.PI / Math.sin(Math.PI * z)) - lnGamma(1 - z);
  z -= 1;
  let x = c[0];
  for (let i = 1; i < g + 2; i++) x += c[i] / (z + i);
  const t = z + g + 0.5;
  return 0.5 * Math.log(2 * Math.PI) + (z + 0.5) * Math.log(t) - t + Math.log(x);
}

export function fmtP(p) {
  if (p == null || Number.isNaN(p)) return "—";
  if (p < 0.001) return "<.001";
  return p.toFixed(3);
}

export function sigStars(p) {
  if (p == null) return "";
  if (p < 0.001) return "***";
  if (p < 0.01) return "**";
  if (p < 0.05) return "*";
  return "ns";
}
