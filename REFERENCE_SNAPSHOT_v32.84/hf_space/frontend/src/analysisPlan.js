import { enrichKinematicCompletion, FULL_TASK_SMOOTHNESS_KEYS, REACH_WINDOW_SMOOTHNESS_KEYS, fullTaskSmoothnessComparable } from "./taskCompletion";
import { coreMetricKeysForTask, isLeClinicalTaskId } from "./clinicalTasks";

/**
 * PETTLEP AOMI RCT â€” Analysis plan, master dataset, SPSS syntax, preliminary stats.
 * Aligned with manuscript: 2Ã—2 mixed ANOVA (Group Ã— Time), n=28, primary = SPARC.
 */

export const STUDY_DESIGN = {
  title: "Immediate Effects of PETTLEP-Based AOMI on Upper Limb Kinematics",
  design: "Single-blind, pretest–posttest, parallel RCT; UE reach/ADL (+ optional LE tasks)",
  groups: { "1": "AOMI", "2": "Control" },
  targetN: 28,
  perGroup: 14,
  alpha: 0.05,
  primaryOutcome: "Task completion, then reach-window NVP / straightness / pause / stops",
};

/** Reach-to-grasp / drink protocol kinematic variables (+ LE when selected).
 *  UI table defaults to task core keys; full list remains for SPSS / "Show all".
 */
export const KINEMATIC_VARS = [
  // ── UE core movement quality (default UI) ──
  { key: "task_complete", label: "Task complete", unit: "0/1", dir: "higher", tier: "primary", core: true },
  { key: "nvp_reach", label: "NVP (reach)", unit: "count", dir: "lower", tier: "primary", core: true },
  { key: "nvp_drink", label: "NVP (drink lift)", unit: "count", dir: "lower", tier: "primary", core: true },
  { key: "nvp_return", label: "NVP (return)", unit: "count", dir: "lower", tier: "primary", core: true },
  { key: "nvp_total", label: "NVP (total)", unit: "count", dir: "lower", tier: "primary", core: true },
  { key: "drink_lift_height_cm", label: "Drink lift height", unit: "cm", dir: "higher", tier: "primary", core: true },
  { key: "straightness", label: "Path straightness", unit: "ratio", dir: "higher", tier: "primary", core: true },
  { key: "pause_time_sec", label: "Pause time", unit: "s", dir: "lower", tier: "primary", core: true },
  { key: "number_of_stops", label: "Number of stops", unit: "count", dir: "lower", tier: "primary", core: true },
  { key: "trunk_ratio", label: "Trunk ratio", unit: "ratio", dir: "lower", tier: "secondary", core: true },
  { key: "shoulder_elevation_cm", label: "Shoulder elevation", unit: "cm", dir: "lower", tier: "secondary", core: true },
  { key: "peak_velocity_cm_s", label: "Peak hand velocity", unit: "cm/s", dir: "higher", tier: "secondary", core: true },
  { key: "movement_time_sec", label: "Movement time", unit: "s", dir: "lower", tier: "secondary", core: true },
  { key: "tremor_8_12hz_power", label: "Tremor 8–12 Hz", unit: "rel.", dir: "lower", tier: "secondary", core: true },
  { key: "fine_motor_quality_index", label: "Hand / finger quality", unit: "0–100", dir: "higher", tier: "secondary", core: true },

  // ── UE isolated-task / ADL extras (shown when task selected or Show all) ──
  { key: "forearm_pronation_supination_rom_deg", label: "Pron/sup ROM", unit: "°", dir: "none", tier: "secondary", core: true },
  { key: "peak_forearm_rotation_vel_deg_s", label: "Peak forearm rotation", unit: "°/s", dir: "higher", tier: "secondary", core: true },
  { key: "sparc_forearm_rotation", label: "SPARC forearm rotation", unit: "", dir: "higher", tier: "exploratory" },
  { key: "shoulder_abduction_rom_deg", label: "Abd ROM", unit: "°", dir: "none", tier: "secondary", core: true },
  { key: "shoulder_abduction_mean_deg", label: "Shoulder abduction (mean)", unit: "°", dir: "none", tier: "secondary", core: true },
  { key: "peak_shoulder_abduction_vel_deg_s", label: "Peak abduction speed", unit: "°/s", dir: "higher", tier: "exploratory" },
  { key: "shoulder_abduction_trunk_compensation_index", label: "Abduction+trunk compensation", unit: "0–1", dir: "lower", tier: "secondary", core: true },
  { key: "pinch_grasp_quality_index", label: "Pinch/grasp quality", unit: "0–100", dir: "higher", tier: "secondary", core: true },
  { key: "pinch_tremor_8_12hz_power", label: "Pinch tremor 8–12 Hz", unit: "rel.", dir: "lower", tier: "exploratory" },
  { key: "finger_flex_ext_quality_index", label: "Finger flex/ext quality", unit: "0–100", dir: "higher", tier: "exploratory" },

  // ── Extended UE (backend / SPSS / Show all) ──
  { key: "task_completion_ratio", label: "Task completion ratio", unit: "0–1", dir: "higher", tier: "exploratory" },
  { key: "nvp_transport", label: "NVP (transport)", unit: "count", dir: "lower", tier: "exploratory" },
  { key: "lift_height_cm", label: "Lift height (transport)", unit: "cm", dir: "higher", tier: "exploratory" },
  { key: "drink_lift_height_sw", label: "Drink lift height (SW)", unit: "SW", dir: "higher", tier: "exploratory" },
  { key: "lift_height_sw", label: "Lift height (transport, SW)", unit: "SW", dir: "higher", tier: "exploratory" },
  { key: "straightness_reach", label: "Path straightness (reach window)", unit: "ratio", dir: "higher", tier: "exploratory" },
  { key: "pause_time_sec_reach", label: "Pause time (reach window)", unit: "s", dir: "lower", tier: "exploratory" },
  { key: "number_of_stops_reach", label: "Number of stops (reach window)", unit: "count", dir: "lower", tier: "exploratory" },
  { key: "nvp", label: "NVP (alias = reach)", unit: "count", dir: "lower", tier: "exploratory" },
  { key: "sip_bout_count", label: "Sip / mouth approaches", unit: "count", dir: "none", tier: "exploratory" },
  { key: "grasp_dwell_sec", label: "Grasp / hold dwell", unit: "s", dir: "none", tier: "exploratory" },
  { key: "functional_hold_sec", label: "Functional hold (grasp+mouth)", unit: "s", dir: "none", tier: "exploratory" },
  { key: "pause_time_sec_total", label: "Pause time (total incl. dwell)", unit: "s", dir: "lower", tier: "exploratory" },
  { key: "nvp_full_task", label: "NVP (full task, incl. sips)", unit: "count", dir: "lower", tier: "exploratory" },
  { key: "shoulder_elevation_palm_ratio", label: "Shoulder elevation (ratio)", unit: "ratio", dir: "lower", tier: "exploratory" },
  { key: "elbow_angle_mean_deg", label: "Elbow angle (mean)", unit: "deg", dir: "none", tier: "exploratory" },
  { key: "shoulder_flexion_mean_deg", label: "Shoulder flexion (mean)", unit: "deg", dir: "none", tier: "exploratory" },
  { key: "peak_elbow_ang_vel_deg_s", label: "Peak elbow angular velocity", unit: "deg/s", dir: "higher", tier: "exploratory" },
  { key: "peak_shoulder_flexion_vel_deg_s", label: "Peak shoulder flexion velocity", unit: "deg/s", dir: "higher", tier: "exploratory" },
  { key: "index_tremor_8_12hz_power", label: "Index tremor 8–12 Hz", unit: "rel.", dir: "lower", tier: "exploratory" },
  { key: "adl_tremor_8_12hz_power", label: "Tremor 8–12 Hz (ADL phase)", unit: "rel.", dir: "lower", tier: "exploratory" },
  { key: "tremor_peak_freq_hz", label: "Tremor peak frequency", unit: "Hz", dir: "none", tier: "exploratory" },
  { key: "movement_quality_index", label: "Movement quality index", unit: "0–100", dir: "higher", tier: "exploratory" },

  // ── LE / gait / STS / squat / balance (kept; shown for LE tasks) ──
  { key: "lr_symmetry_index", label: "L/R symmetry", unit: "0–1", dir: "higher", tier: "primary", core: true },
  { key: "gait_speed_m_s", label: "Gait speed", unit: "m/s", dir: "higher", tier: "primary", core: true },
  { key: "cadence_spm", label: "Cadence", unit: "steps/min", dir: "higher", tier: "primary", core: true },
  { key: "ankle_df_peak_L_deg", label: "Ankle DF peak L", unit: "deg", dir: "higher", tier: "primary", core: true },
  { key: "ankle_df_peak_R_deg", label: "Ankle DF peak R", unit: "deg", dir: "higher", tier: "primary", core: true },
  { key: "ankle_pf_peak_L_deg", label: "Ankle PF peak L", unit: "deg", dir: "higher", tier: "primary", core: true },
  { key: "ankle_pf_peak_R_deg", label: "Ankle PF peak R", unit: "deg", dir: "higher", tier: "primary", core: true },
  { key: "foot_drop_index", label: "Foot-drop index", unit: "0–1", dir: "lower", tier: "secondary", core: true },
  { key: "hip_hike_index", label: "Hip-hike index", unit: "0–1", dir: "lower", tier: "secondary", core: true },
  { key: "circumduction_index", label: "Circumduction index", unit: "0–1", dir: "lower", tier: "secondary", core: true },
  { key: "trunk_lean_max_deg", label: "Trunk lean max", unit: "deg", dir: "lower", tier: "secondary", core: true },
  { key: "sparc_com", label: "SPARC (COM)", unit: "", dir: "higher", tier: "exploratory" },
  { key: "stiff_knee_index", label: "Stiff-knee index", unit: "0–1", dir: "lower", tier: "exploratory" },
  { key: "push_off_deficit_index", label: "Push-off deficit", unit: "0–1", dir: "lower", tier: "exploratory" },
  { key: "vaulting_index", label: "Vaulting index", unit: "0–1", dir: "lower", tier: "exploratory" },
  { key: "sts_time_sec", label: "STS time", unit: "s", dir: "lower", tier: "secondary", core: true },
  { key: "com_rise_norm", label: "COM rise (HW)", unit: "", dir: "higher", tier: "secondary", core: true },
  { key: "weight_shift_asymmetry", label: "Weight-shift asymmetry", unit: "0–1", dir: "lower", tier: "secondary", core: true },
  { key: "trunk_compensation_index", label: "Trunk compensation", unit: "0–1", dir: "lower", tier: "secondary", core: true },
  { key: "squat_depth_norm", label: "Squat depth (HW)", unit: "", dir: "higher", tier: "secondary", core: true },
  { key: "min_knee_angle_deg", label: "Min knee (squat)", unit: "deg", dir: "none", tier: "secondary", core: true },
  { key: "knee_rom_L_deg", label: "Knee ROM L", unit: "deg", dir: "none", tier: "exploratory" },
  { key: "knee_rom_R_deg", label: "Knee ROM R", unit: "deg", dir: "none", tier: "exploratory" },
  { key: "com_sway_path_norm", label: "COM sway path", unit: "HW", dir: "lower", tier: "secondary", core: true },
  { key: "com_sway_area_norm", label: "COM sway area", unit: "HW²", dir: "lower", tier: "secondary", core: true },
  { key: "sway_velocity_mean", label: "Sway velocity", unit: "px/s", dir: "lower", tier: "secondary", core: true },
  { key: "lr_loading_symmetry", label: "Loading symmetry", unit: "0–1", dir: "higher", tier: "secondary", core: true },
];

/** Default UE results-table order — movement quality core. */
export const KINEMATIC_CORE_DISPLAY_ORDER = [
  "task_complete",
  "nvp_reach",
  "nvp_drink",
  "nvp_return",
  "nvp_total",
  "drink_lift_height_cm",
  "straightness",
  "pause_time_sec",
  "number_of_stops",
  "trunk_ratio",
  "shoulder_elevation_cm",
  "peak_velocity_cm_s",
  "movement_time_sec",
  "tremor_8_12hz_power",
  "fine_motor_quality_index",
];

/** Full order when user expands "Show all metrics". */
export const KINEMATIC_DISPLAY_ORDER = [
  ...KINEMATIC_CORE_DISPLAY_ORDER,
  "task_completion_ratio",
  "nvp_transport",
  "lift_height_cm",
  "drink_lift_height_sw",
  "lift_height_sw",
  "nvp",
  "straightness_reach",
  "pause_time_sec_reach",
  "number_of_stops_reach",
  "sip_bout_count",
  "grasp_dwell_sec",
  "functional_hold_sec",
  "nvp_full_task",
  "pause_time_sec_total",
  "shoulder_elevation_palm_ratio",
  "elbow_angle_mean_deg",
  "shoulder_flexion_mean_deg",
  "peak_elbow_ang_vel_deg_s",
  "peak_shoulder_flexion_vel_deg_s",
  "forearm_pronation_supination_rom_deg",
  "peak_forearm_rotation_vel_deg_s",
  "shoulder_abduction_rom_deg",
  "shoulder_abduction_mean_deg",
  "pinch_grasp_quality_index",
  "finger_flex_ext_quality_index",
  "index_tremor_8_12hz_power",
  "adl_tremor_8_12hz_power",
  "tremor_peak_freq_hz",
  "movement_quality_index",
  "lr_symmetry_index",
  "gait_speed_m_s",
  "cadence_spm",
  "ankle_df_peak_L_deg",
  "ankle_df_peak_R_deg",
  "ankle_pf_peak_L_deg",
  "ankle_pf_peak_R_deg",
  "foot_drop_index",
  "hip_hike_index",
  "circumduction_index",
  "trunk_lean_max_deg",
  "sts_time_sec",
  "com_sway_path_norm",
];
/** Manuscript / ethics-form reference pattern (Pre â†’ Post â†’ Healthy) */
export const MANUSCRIPT_KINEMATIC_TARGETS = {
  nvp_reach: { pre: 3.5, post: 2.5, healthy: 1.5 },
  nvp: { pre: 3.5, post: 2.5, healthy: 1.5 },
  straightness: { pre: 0.82, post: 0.88, healthy: 0.94 },
  pause_time_sec: { pre: 0.45, post: 0.25, healthy: 0.10 },
  number_of_stops: { pre: 2.5, post: 1.5, healthy: 0.5 },
  trunk_ratio: { pre: 0.32, post: 0.18, healthy: 0.03 },
  shoulder_elevation_cm: { pre: 4.0, post: 2.5, healthy: 1.2 },
  shoulder_elevation_palm_ratio: { pre: 0.25, post: 0.16, healthy: 0.09 },
  drink_lift_height_cm: { pre: 18, post: 24, healthy: 30 },
  movement_time_sec: { pre: 2.2, post: 1.7, healthy: 1.2 },
  peak_velocity_cm_s: { pre: 35, post: 48, healthy: 65 },
  peak_elbow_ang_vel_deg_s: { pre: 160.0, post: 200.0, healthy: 240.0 },
  peak_shoulder_flexion_vel_deg_s: { pre: 120.0, post: 150.0, healthy: 180.0 },
};

export function orderedKinematicVars(order = KINEMATIC_CORE_DISPLAY_ORDER) {
  const byKey = Object.fromEntries(KINEMATIC_VARS.map((v) => [v.key, v]));
  return order.map((k) => byKey[k]).filter(Boolean);
}

/** Extra rows only when "Show all metrics" is on (validation overlay extras). */
export const VALIDATION_PANEL_TABLE_EXTRAS = [
  { key: "tremor_8_12hz_power", label: "Tremor 8â€“12 Hz", unit: "rel.", dir: "lower" },
  { key: "index_tremor_8_12hz_power", label: "Index tremor 8â€“12 Hz", unit: "rel.", dir: "lower" },
  { key: "tremor_peak_freq_hz", label: "Tremor peak freq", unit: "Hz", dir: "none" },
  { key: "movement_quality_index", label: "Movement quality", unit: "0â€“100", dir: "higher" },
  { key: "shoulder_abduction_rom_deg", label: "Abd ROM (reach)", unit: "Â°", dir: "none" },
  { key: "forearm_pronation_supination_rom_deg", label: "Pron/sup ROM", unit: "Â°", dir: "none" },
  { key: "adl_shoulder_abduction_mean_deg", label: "Abduction (ADL drink)", unit: "Â°", dir: "lower" },
  { key: "adl_shoulder_abduction_rom_deg", label: "Abd ROM (ADL)", unit: "Â°", dir: "lower" },
  { key: "adl_finger_flex_ext_quality_index", label: "Finger flex/ext Q (ADL)", unit: "0â€“100", dir: "higher" },
  { key: "adl_head_forward_flexion_compensation_index", label: "Head compensation (ADL)", unit: "0â€“1", dir: "lower" },
  { key: "adl_tremor_8_12hz_power", label: "Tremor (ADL)", unit: "rel.", dir: "lower" },
  { key: "pause_stops_panel", label: "Pause / stops", unit: "s / count", dir: "lower", synthetic: true },
  {
    key: "peak_velocity_panel",
    label: "Peak velocity",
    unit: "cm/s",
    dir: "higher",
    panelAlias: true,
  },
];

function kinematicTierGroup(tier) {
  if (tier === "primary") return "Primary";
  if (tier === "secondary") return "Secondary";
  return "Exploratory";
}

function kinematicDirToDirection(dir) {
  if (dir === "lower") return "lower";
  if (dir === "higher") return "higher";
  return "none";
}

/**
 * Results table rows.
 * @param {{ includeExtended?: boolean, clinicalTask?: string|null, kinematicsResults?: object|null }} opts
 */
export function orderedKinematicResultsTableVars({
  includeExtended = false,
  clinicalTask = null,
  kinematicsResults = null,
} = {}) {
  const resultTask =
    clinicalTask
    || kinematicsResults?.pre?.clinical_task
    || kinematicsResults?.post?.clinical_task
    || kinematicsResults?.baseline?.clinical_task
    || null;
  const taskId = String(resultTask || "study_reach_grasp").toLowerCase();
  const taskCore = coreMetricKeysForTask(taskId);
  const order = includeExtended
    ? [...taskCore, ...KINEMATIC_DISPLAY_ORDER.filter((k) => !taskCore.includes(k))]
    : taskCore;
  const coreKeys = new Set(order);
  const core = orderedKinematicVars(order).map((v) => ({
    group: kinematicTierGroup(v.tier),
    name: v.label,
    key: v.key,
    unit: v.unit || "—",
    direction: kinematicDirToDirection(v.dir),
  }));
  if (!includeExtended) return core;
  // LE tasks: skip UE-only validation extras in the extended table.
  const extras = isLeClinicalTaskId(taskId)
    ? []
    : VALIDATION_PANEL_TABLE_EXTRAS.filter(
      (e) => (e.synthetic || e.panelAlias || !coreKeys.has(e.key)) && e.key !== "peak_velocity_panel" && e.key !== "pause_stops_panel",
    );
  const validation = extras.map((e) => ({
    group: "Validation video",
    name: e.label,
    key: e.key,
    unit: e.unit || "—",
    direction: kinematicDirToDirection(e.dir),
  }));
  return [...core, ...validation];
}

export const CLINICAL_VARS = [
  { pre: "BBT_Paretic_Pre", post: "BBT_Paretic_Post", label: "BBT paretic hand (blocks/60s)", dir: "higher", test: "mixed", tier: "secondary" },
  { pre: "VAMS_Happy_Pre", post: "VAMS_Happy_Post", label: "VAMS Happy", dir: "higher", test: "mixed", tier: "secondary" },
  { pre: "VAMS_Calm_Pre", post: "VAMS_Calm_Post", label: "VAMS Calm", dir: "higher", test: "mixed", tier: "secondary" },
  { pre: "VAMS_Sad_Pre", post: "VAMS_Sad_Post", label: "VAMS Sad", dir: "lower", test: "mixed", tier: "secondary" },
  { pre: "VAMS_Tense_Pre", post: "VAMS_Tense_Post", label: "VAMS Tense", dir: "lower", test: "mixed", tier: "secondary" },
  { pre: "VAS_Pre", post: "VAS_Post", label: "VAS pain (mean)", dir: "lower", test: "mixed", tier: "secondary" },
  { pre: "MDRS_Control_Pre", post: "MDRS_Difference_Post", label: "MDRS motor control change", dir: "higher", test: "post_only", tier: "secondary" },
  { pre: null, post: "IPAQ_MET", label: "IPAQ total MET-min/wk", dir: "none", test: "descriptive", tier: "moderator" },
];

const secondaryKinematicKeys = KINEMATIC_VARS.filter((k) => k.tier === "secondary").map((k) => k.key).join(", ");
const nKinematic = KINEMATIC_VARS.length;

export const SPSS_WORKFLOW = [
  { step: 1, title: "Data import", spss: "GET DATA â†’ master_study_data.csv â†’ SAVE master_study.sav" },
  { step: 2, title: "Variable labels & deltas", spss: `COMPUTE delta_* = *_Post âˆ’ *_Pre for ${nKinematic} kinematic + clinical vars` },
  { step: 3, title: "Healthy side equivalence", spss: "T-TEST / Mann-Whitney / Chi-square on Pre scores & demographics" },
  { step: 4, title: "Normality (Shapiroâ€“Wilk)", spss: "EXAMINE â€¦ BY Group on Pre, Post, and Î” for each DV" },
  { step: 5, title: "Primary analysis", spss: "Hierarchical: TaskComplete then GLM nvp_reach (and 3 reach-window smoothness) Pre Post BY Group; Holmâ€“Bonferroni k=4. Full-task NVP only if TaskComplete_Pre = TaskComplete_Post" },
  { step: 6, title: "Secondary kinematic", spss: `${secondaryKinematicKeys}; Holmâ€“Bonferroni k=${KINEMATIC_VARS.filter((k) => k.tier === "secondary").length}` },
  { step: 8, title: "Clinical scales", spss: "GLM VAMS-4, VAS; MWU/Wilcoxon if non-normal" },
  { step: 9, title: "MDRS post-only", spss: "Mann-Whitney MDRS_Difference_Post BY Group" },
  { step: 10, title: "Moderators", spss: "CORRELATIONS KVIQ-10 Pre with Î” kinematic; split by Group" },
  { step: 11, title: "Sensitivity", spss: "MIXED models + LOCF imputation (ITT)" },
  { step: 12, title: "Report", spss: "OMS tables â†’ APA; partial Î·Â² â‰¥ .14 = large (Cohen, 1988)" },
];

const LEGACY_KIN_MAP = {
  task_complete: ["task_complete"],
  task_completion_ratio: ["task_completion_ratio"],
  nvp_reach: ["nvp_reach"],
  nvp_drink: ["nvp_drink", "nvp_transport"],
  nvp_transport: ["nvp_transport", "nvp_drink"],
  nvp_return: ["nvp_return"],
  nvp_total: ["nvp_total"],
  drink_lift_height_cm: ["drink_lift_height_cm", "lift_height_cm"],
  lift_height_cm: ["lift_height_cm", "drink_lift_height_cm"],
  drink_lift_height_sw: ["drink_lift_height_sw", "lift_height_sw"],
  lift_height_sw: ["lift_height_sw", "drink_lift_height_sw"],
  straightness_reach: ["straightness_reach"],
  pause_time_sec_reach: ["pause_time_sec_reach"],
  number_of_stops_reach: ["number_of_stops_reach"],
  sip_bout_count: ["sip_bout_count"],
  grasp_dwell_sec: ["grasp_dwell_sec"],
  functional_hold_sec: ["functional_hold_sec"],
  pause_time_sec_total: ["pause_time_sec_total"],
  number_of_stops_total: ["number_of_stops_total"],
  nvp_full_task: ["nvp_full_task", "nvp_total"],
  nvp: ["nvp", "nvp_reach"],
  straightness: ["straightness", "straightness_reach"],
  pause_time_sec: ["pause_time_sec", "pause_time_sec_reach", "pause_time_sec_path", "pause_time"],
  number_of_stops: ["number_of_stops", "number_of_stops_reach", "number_of_stops_path", "n_stops", "stops"],
  trunk_ratio: ["trunk_ratio", "total_trunk_palm_ratio"],
  shoulder_elevation_cm: ["shoulder_elevation_cm"],
  shoulder_elevation_palm_ratio: ["shoulder_elevation_palm_ratio"],
  elbow_angle_mean_deg: ["elbow_angle_mean_deg", "elbow_angle_mean"],
  shoulder_flexion_mean_deg: ["shoulder_flexion_mean_deg", "shoulder_flexion_mean"],
  movement_time_sec: ["movement_time_sec", "total_duration_s", "duration"],
  peak_velocity_cm_s: ["peak_velocity_cm_s", "total_peak_velocity", "peak_velocity_px_s"],
  peak_elbow_ang_vel_deg_s: ["peak_elbow_ang_vel_deg_s", "peak_velocity_deg_s"],
  peak_shoulder_flexion_vel_deg_s: ["peak_shoulder_flexion_vel_deg_s"],
  tremor_8_12hz_power: ["tremor_8_12hz_power", "hand_speed_tremor_8_12hz_power"],
  index_tremor_8_12hz_power: ["index_tremor_8_12hz_power"],
  tremor_peak_freq_hz: ["tremor_peak_freq_hz"],
  tremor_index: ["tremor_index"],
  adl_tremor_8_12hz_power: ["adl_tremor_8_12hz_power"],
  movement_quality_index: ["movement_quality_index"],
  shoulder_abduction_rom_deg: ["shoulder_abduction_rom_deg"],
  forearm_pronation_supination_rom_deg: ["forearm_pronation_supination_rom_deg"],
  fine_motor_quality_index: ["fine_motor_quality_index"],
  adl_shoulder_abduction_mean_deg: ["adl_shoulder_abduction_mean_deg", "shoulder_abduction_mean_deg"],
  adl_shoulder_abduction_rom_deg: ["adl_shoulder_abduction_rom_deg"],
  adl_finger_flex_ext_rom_sw: ["adl_finger_flex_ext_rom_sw", "finger_flex_ext_rom_sw"],
  adl_finger_flex_ext_quality_index: ["adl_finger_flex_ext_quality_index", "finger_flex_ext_quality_index"],
  adl_head_forward_flexion_compensation_index: [
    "adl_head_forward_flexion_compensation_index",
    "head_forward_flexion_compensation_index",
  ],
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
  const enriched = enrichKinematicCompletion(result);
  KINEMATIC_VARS.forEach(({ key, fallback }) => {
    let v = pickKinField(result, key, fallback);
    if (v === null && enriched[key] != null && enriched[key] !== "") {
      v = Number(enriched[key]);
      if (Number.isNaN(v)) v = null;
    }
    if (v !== null) out[key] = v;
  });
  const profile = result?.movement_profile;
  if (profile && typeof profile === "object") {
    [
      "tremor_8_12hz_power",
      "tremor_index",
      "tremor_peak_freq_hz",
      "index_tremor_8_12hz_power",
      "hand_speed_tremor_8_12hz_power",
      "adl_tremor_8_12hz_power",
      "movement_quality_index",
    ].forEach((key) => {
      if (out[key] == null && profile[key] != null && profile[key] !== "") {
        out[key] = Number(profile[key]);
      }
    });
  }
  if (out.movement_quality_index == null && result?.movement_quality_index != null) {
    out.movement_quality_index = Number(result.movement_quality_index);
  }
  if (out.adl_tremor_8_12hz_power == null && result?.adl_tremor_8_12hz_power != null) {
    out.adl_tremor_8_12hz_power = Number(result.adl_tremor_8_12hz_power);
  }
  return Object.keys(out).length ? out : null;
}

/** Preâ†’Post relative % change. Returns null when relative % is undefined (e.g. Pre â‰ˆ 0). */
export function calcImprovement(pre, post, direction) {
  const preN = Number(pre);
  const postN = Number(post);
  if (Number.isNaN(preN) || Number.isNaN(postN)) return null;
  // Relative % needs a non-zero baseline â€” avoid Infinity%.
  if (Math.abs(preN) < 1e-12) {
    if (Math.abs(postN - preN) < 1e-12) return 0;
    return null;
  }
  let pct;
  if (direction === "higher") {
    pct = ((postN - preN) / Math.abs(preN)) * 100;
  } else if (direction === "lower") {
    pct = ((preN - postN) / Math.abs(preN)) * 100;
  } else {
    // Descriptive: unsigned magnitude of relative change
    pct = ((postN - preN) / Math.abs(preN)) * 100;
  }
  if (!Number.isFinite(pct)) return null;
  return pct;
}

/** Absolute Preâ†’Post delta label when relative % is not defined (Pre â‰ˆ 0). */
export function formatKinPrePostAbsDelta(pre, post) {
  const preN = Number(pre);
  const postN = Number(post);
  if (Number.isNaN(preN) || Number.isNaN(postN)) return null;
  const d = postN - preN;
  if (!Number.isFinite(d)) return null;
  const a = Math.abs(d);
  if (a < 1e-12) return "0%";
  if (a >= 100) return `Î” ${a.toFixed(0)}`;
  if (a >= 10) return `Î” ${a.toFixed(1)}`;
  if (a >= 1) return `Î” ${a.toFixed(2)}`;
  return `Î” ${a.toFixed(3)}`;
}

/** Postâ†’Healthy % or gap (calc_gap â€” exact Python port). */
export function calcGap(post, healthy, direction) {
  const postN = Number(post);
  const healthyN = Number(healthy);
  if (Number.isNaN(postN) || Number.isNaN(healthyN)) return null;
  if (Math.abs(healthyN) < 1e-12 && direction === "higher") return null;
  if (direction === "higher") {
    const pct = (Math.abs(healthyN - postN) / Math.abs(healthyN)) * 100;
    return Number.isFinite(pct) ? pct : null;
  }
  return postN - healthyN;
}

export function formatKinPrePostPct(pct) {
  if (pct == null || Number.isNaN(pct) || !Number.isFinite(pct)) return null;
  return `${Math.abs(pct).toFixed(0)}%`;
}

export function formatKinPostHealthyPct(pct) {
  if (pct == null || Number.isNaN(pct) || !Number.isFinite(pct)) return null;
  return `${Math.abs(pct).toFixed(1)}%`;
}

/** Format a raw kinematic value the same way everywhere (table, report, video overlay). */
export function formatKinValue(key, value) {
  if (value == null || value === "\u2014") return "\u2014";
  if (typeof value === "string") return value;
  const val = Number(value);
  if (Number.isNaN(val)) return String(value);
  if (key === "task_complete") return Number(val) === 1 ? "Complete" : "Incomplete";
  if (key === "task_completion_ratio") return val.toFixed(2);
  if (key === "nvp" || key === "nvp_reach" || key === "nvp_drink" || key === "nvp_transport" || key === "nvp_return" || key === "nvp_total" || key === "nvp_full_task" || key === "sip_bout_count") return val.toFixed(0);
  if (key === "drink_lift_height_cm" || key === "lift_height_cm" || key === "shoulder_elevation_cm") return val.toFixed(1);
  if (key === "peak_velocity_cm_s" || key === "hand_displacement_cm") return val.toFixed(1);
  if (key === "drink_lift_height_sw" || key === "lift_height_sw") return val.toFixed(3);
  if (key === "straightness" || key === "straightness_reach") return val.toFixed(3);
  if (key === "pause_time_sec" || key === "pause_time_sec_reach" || key === "pause_time_sec_total" || key === "grasp_dwell_sec" || key === "functional_hold_sec") return val.toFixed(2);
  if (key === "number_of_stops" || key === "number_of_stops_reach" || key === "number_of_stops_total" || key === "grasp_dwell_stops") return val.toFixed(0);
  if (key === "trunk_ratio") return `${(val * 100).toFixed(1)}%`;
  if (key === "shoulder_elevation_palm_ratio") return val.toFixed(3);
  if (key === "elbow_angle_mean_deg") return val.toFixed(1);
  if (key === "shoulder_flexion_mean_deg") return val.toFixed(1);
  if (key === "movement_time_sec") return val.toFixed(2);
  if (key === "peak_elbow_ang_vel_deg_s") return `${val.toFixed(1)}\u00b0/s`;
  if (key === "peak_shoulder_flexion_vel_deg_s") return `${val.toFixed(1)}\u00b0/s`;
  if (key.includes("tremor") && key.includes("power")) return `${(val * 100).toFixed(1)}% rel`;
  if (key === "tremor_peak_freq_hz" || key.endsWith("_peak_freq_hz")) return `${val.toFixed(1)} Hz`;
  if (key === "fine_motor_quality_index" || key.endsWith("_quality_index")) return val.toFixed(0);
  if (key.includes("_rom_deg") || (key.includes("deg") && !key.includes("vel"))) return val.toFixed(1);
  if (key.includes("ratio") || key.includes("trunk") || key.includes("_sw") || key.includes("path_eff")) return val.toFixed(3);
  return val.toFixed(2);
}

/**
 * Recovery toward healthy side (Fugl-Meyer style index).
 * higher-is-better: 100Ã—(postâˆ’pre)/(healthyâˆ’pre)
 * lower-is-better:    100Ã—(preâˆ’post)/(preâˆ’healthy) â€” only when pre is worse than healthy.
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
    if (Math.abs(denom) < 1e-9) return { valid: false, reason: "preâ‰ˆhealthy" };
    pct = ((postN - preN) / denom) * 100;
  } else if (direction === "lower") {
    if (preN <= helN) return { valid: false, reason: "pre_at_or_better_than_healthy" };
    const denom = preN - helN;
    if (Math.abs(denom) < 1e-9) return { valid: false, reason: "preâ‰ˆhealthy" };
    pct = ((preN - postN) / denom) * 100;
  } else {
    return null;
  }

  const improved = pct > 0;
  const text = `${pct >= 0 ? "" : ""}${pct.toFixed(0)}%`;
  return { valid: true, pct, improved, text };
}

/** Whether pre/post/healthy side values are comparable for cross-phase deltas (view/arm gates). */
export function kinCrossPhaseComparable(kinematicsResults, metricKey, armForPhase = null) {
  return kinCrossPhaseDeltaStatus(kinematicsResults, metricKey, armForPhase).comparable;
}

/**
 * Comparability + short reason for Preâ†’Post badge (n/c instead of a blank dash).
 * Reach-window smoothness stays comparable even when task completion differs.
 */
export function kinCrossPhaseDeltaStatus(kinematicsResults, metricKey, armForPhase = null) {
  void armForPhase;
  if (
    metricKey === "pause_stops_panel"
    || metricKey === "side_analyzed"
    || metricKey === "side"
  ) {
    return { comparable: false, reason: "n/c Â· not a single value" };
  }

  if (FULL_TASK_SMOOTHNESS_KEYS.includes(metricKey)) {
    if (!fullTaskSmoothnessComparable(kinematicsResults)) {
      return { comparable: false, reason: "n/c Â· task complete differs" };
    }
  }

  // Primary study window (reach): always allow Preâ†’Post %; banner still warns on low amp / completion.
  if (REACH_WINDOW_SMOOTHNESS_KEYS.includes(metricKey)) {
    return { comparable: true, reason: null };
  }

  const phases = ["pre", "post", "baseline"].filter((p) => kinematicsResults?.[p]);
  if (metricKey === "sparc" && phases.length >= 2) {
    const ok = phases.every((p) => kinematicsResults[p]?.sparc_comparable !== false);
    if (!ok) return { comparable: false, reason: "n/c Â· low reach amp" };
  }

  return { comparable: true, reason: null };
}

/** Key metrics for per-patient recovery summary. */
export const RECOVERY_SUMMARY_KEYS = [
  "task_complete",
  "nvp_reach",
  "nvp_drink",
  "nvp_return",
  "nvp_total",
  "drink_lift_height_cm",
  "straightness",
  "pause_time_sec",
  "number_of_stops",
  "trunk_ratio",
  "shoulder_elevation_cm",
  "peak_velocity_cm_s",
  "movement_time_sec",
  "tremor_8_12hz_power",
  "fine_motor_quality_index",
];

/** Read pre/post/healthy side kinematics from patient record. */
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
  // Legacy CSV columns (kept for backward compatibility; always present, empty if unavailable).
  const legacy = {
    total_trunk_palm_ratio: kinCell(m, "trunk_ratio"),
    total_duration_s: kinCell(m, "movement_time_sec"),
    total_peak_velocity: kinCell(m, "peak_velocity_cm_s"),
  };
  Object.entries(legacy).forEach(([k, v]) => {
    row[`${k}_${suffix}`] = v;
  });
}

/** SPSS-ready demographic columns (numeric codes aligned with app GSelect values). */
export const DEMO_SPSS_KEYS = [
  "ID",
  "Group",
  "Age",
  "Sex",
  "TimeSinceStroke",
  "StrokeType",
  "AffectedSide",
  "DominantHand",
  "Hemisphere",
  "DiseaseStage",
  "MAS",
  "MRC",
];

const MAS_UI_TO_SPSS = { "0": 0, "1": 1, "1+": 2, "2": 3, "3": 4, "4": 5 };
const DOMINANT_HAND_TO_SPSS = { right: 1, left: 2, both: 3 };
const HEMISPHERE_TO_SPSS = { left: 1, right: 2, bilateral: 3 };
const DISEASE_STAGE_TO_SPSS = { acute: 1, subacute: 2, chronic: 3 };

function spssNumericOrBlank(v) {
  if (v === "" || v === null || v === undefined) return "";
  const n = Number(v);
  return Number.isFinite(n) ? n : "";
}

function mapUiToSpss(map, raw) {
  if (raw === "" || raw === null || raw === undefined) return "";
  const key = String(raw).trim().toLowerCase();
  if (Object.prototype.hasOwnProperty.call(map, key)) return map[key];
  if (Object.prototype.hasOwnProperty.call(map, String(raw).trim())) return map[String(raw).trim()];
  return "";
}

/** Map demographics object â†’ SPSS numeric row fragment (UI unchanged). */
export function exportDemographicsForSpss(d = {}) {
  const masRaw = d.mas ?? "";
  let masSpss = "";
  if (masRaw !== "" && masRaw != null) {
    const k = String(masRaw).trim();
    if (Object.prototype.hasOwnProperty.call(MAS_UI_TO_SPSS, k)) masSpss = MAS_UI_TO_SPSS[k];
  }

  return {
    ID: d.participantId != null && d.participantId !== "" ? String(d.participantId) : "",
    Group: spssNumericOrBlank(d.group),
    Age: spssNumericOrBlank(d.age),
    Sex: spssNumericOrBlank(d.sex),
    TimeSinceStroke: spssNumericOrBlank(d.timeSinceStroke),
    StrokeType: spssNumericOrBlank(d.strokeType),
    AffectedSide: spssNumericOrBlank(d.side),
    DominantHand: mapUiToSpss(DOMINANT_HAND_TO_SPSS, d.dominantHand),
    Hemisphere: mapUiToSpss(HEMISPHERE_TO_SPSS, d.hemisphere),
    DiseaseStage: mapUiToSpss(DISEASE_STAGE_TO_SPSS, d.diseaseStage),
    MAS: masSpss,
    MRC: spssNumericOrBlank(d.mrc),
  };
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
    ...exportDemographicsForSpss(d),
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

  const bbt = patient.bbt || {};
  row.BBT_Paretic_Pre = bbt.pre?.pareticBlocks ?? "";
  row.BBT_Paretic_Post = bbt.post?.pareticBlocks ?? "";
  row.BBT_Unaffected_Pre = bbt.pre?.unaffectedBlocks ?? "";
  row.BBT_Unaffected_Post = bbt.post?.unaffectedBlocks ?? "";

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
  ["rest", "activity"].forEach((k) => {
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
  const rows = (patients || [])
    .filter((p) => p && !p._archived)
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
  l(`* --- ${label}${primary ? " [PRIMARY â€” Î±=.05 uncorrected]" : ""} ---`);
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

function spssFormatForColumn(name) {
  if (name === "ID") return "A30";
  if (
    [
      "Group",
      "Sex",
      "StrokeType",
      "AffectedSide",
      "DominantHand",
      "Hemisphere",
      "DiseaseStage",
      "MAS",
      "MRC",
    ].includes(name)
  ) {
    return "F8.0";
  }
  if (name === "Age" || name === "TimeSinceStroke") return "F8.2";
  return "F12.6";
}

function masterRowColumnOrder(sampleRow) {
  if (sampleRow && typeof sampleRow === "object") return Object.keys(sampleRow);
  const kinAll = KINEMATIC_VARS;
  return [
    ...DEMO_SPSS_KEYS,
    ...kinAll.flatMap(({ key }) => [`${key}_Pre`, `${key}_Post`]),
    ...kinAll.flatMap(({ key }) => [`${key}_Healthy`]),
    "total_trunk_palm_ratio_Pre",
    "total_duration_s_Pre",
    "total_peak_velocity_Pre",
    "total_trunk_palm_ratio_Post",
    "total_duration_s_Post",
    "total_peak_velocity_Post",
    "total_trunk_palm_ratio_Healthy",
    "total_duration_s_Healthy",
    "total_peak_velocity_Healthy",
    "WMFT_Time_Pre",
    "WMFT_Time_Post",
    "WMFT_Rating_Pre",
    "WMFT_Rating_Post",
    "VAMS_Happy_Pre",
    "VAMS_Happy_Post",
    "VAMS_Sad_Pre",
    "VAMS_Sad_Post",
    "VAMS_Calm_Pre",
    "VAMS_Calm_Post",
    "VAMS_Tense_Pre",
    "VAMS_Tense_Post",
    "KVIQ_Vis_Pre",
    "KVIQ_Vis_Post",
    "KVIQ_Kin_Pre",
    "KVIQ_Kin_Post",
    "IPAQ_MET",
    "VAS_Pre",
    "VAS_Post",
    "MDRS_Control_Pre",
    "MDRS_Difference_Post",
  ];
}

export function generateStudySPSSSyntax(csvFilename = "master_study_data.csv", sampleRow = null) {
  const lines = [];
  const l = (s = "") => lines.push(s);

  const kinPrimary = KINEMATIC_VARS.filter((k) => k.tier === "primary");
  const kinSecondary = KINEMATIC_VARS.filter((k) => k.tier === "secondary");
  const kinExploratory = KINEMATIC_VARS.filter((k) => k.tier === "exploratory");
  const kinAll = [...kinPrimary, ...kinSecondary, ...kinExploratory];

  const smoothnessPrimary = kinPrimary.find((k) => k.key === "nvp_reach") || kinPrimary[0] || kinAll[0];
  const primaryKey = smoothnessPrimary?.key || "nvp_reach";
  const primaryLabel = smoothnessPrimary?.label || primaryKey;

  l("* =================================================================");
  l("* PETTLEP AOMI RCT â€” SPSS Analysis Syntax (RA.ED AI auto-generated)");
  l("* Design: 2 (Group: AOMI vs Control) Ã— 2 (Time: Pre, Post) mixed ANOVA");
  l(`* Primary smoothness: ${primaryLabel}; interpret task_complete first. Secondary Holm k=${kinSecondary.length}`);
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
  const importCols = masterRowColumnOrder(sampleRow);
  importCols.forEach((col) => {
    l(`  ${col} ${spssFormatForColumn(col)}`);
  });
  l(".");
  l("CACHE.");
  l("EXECUTE.");
  l("");
  l("VALUE LABELS Group 1 'AOMI (Intervention)' 2 'Control'.");
  l("VALUE LABELS Sex 1 'Male' 2 'Female'.");
  l("VALUE LABELS StrokeType 1 'Ischemic' 2 'Hemorrhagic'.");
  l("VALUE LABELS AffectedSide 1 'Left' 2 'Right'.");
  l("VALUE LABELS DominantHand 1 'Right' 2 'Left' 3 'Both'.");
  l("VALUE LABELS Hemisphere 1 'Left' 2 'Right' 3 'Bilateral'.");
  l("VALUE LABELS DiseaseStage 1 'Acute' 2 'Subacute' 3 'Chronic'.");
  l("VALUE LABELS MAS 0 'No increase' 1 'Slight catch' 2 '1+ catch' 3 'More marked' 4 'Considerable' 5 'Rigid'.");
  l("VALUE LABELS MRC 2 'Grade 2' 3 'Grade 3' 4 'Grade 4' 5 'Grade 5'.");
  l("VALUE LABELS task_complete_Pre 0 'Incomplete' 1 'Complete'.");
  l("VALUE LABELS task_complete_Post 0 'Incomplete' 1 'Complete'.");
  l("EXECUTE.");
  l("");
  l("* --- Demographic variable labels ---");
  l("VARIABLE LABELS ID 'Study participant ID'.");
  l("VARIABLE LABELS Group 'Randomisation group'.");
  l("VARIABLE LABELS Age 'Age (years)'.");
  l("VARIABLE LABELS Sex 'Gender (1=Male, 2=Female)'.");
  l("VARIABLE LABELS TimeSinceStroke 'Months since stroke'.");
  l("VARIABLE LABELS StrokeType 'Stroke type (1=Ischemic, 2=Hemorrhagic)'.");
  l("VARIABLE LABELS AffectedSide 'Paretic side (1=Left, 2=Right)'.");
  l("VARIABLE LABELS DominantHand 'Dominant hand (1=Right, 2=Left, 3=Both)'.");
  l("VARIABLE LABELS Hemisphere 'Affected hemisphere'.");
  l("VARIABLE LABELS DiseaseStage 'Disease stage (acute/subacute/chronic)'.");
  l("VARIABLE LABELS MAS 'Modified Ashworth Scale (SPSS codes 0â€“5; UI 1+ â†’ 2)'.");
  l("VARIABLE LABELS MRC 'MRC muscle strength (2â€“5)'.");
  l("EXECUTE.");
  l("");

  l("* --- 2. VARIABLE LABELS (kinematic) ---");
  kinAll.forEach(({ key, label, unit }) => {
    l(`VARIABLE LABELS ${key}_Pre '${label} â€” Pre (${unit})'.`);
    l(`VARIABLE LABELS ${key}_Post '${label} â€” Post (${unit})'.`);
  });
  l("EXECUTE.");
  l("");

  l("* --- 3. DELTA SCORES (Post âˆ’ Pre) ---");
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

  l("* --- 4. HEALTHY SIDE EQUIVALENCE ---");
  l("T-TEST GROUPS=Group(1 2)");
  l(`  /VARIABLES=Age TimeSinceStroke MAS MRC ${primaryKey}_Pre trunk_ratio_Pre shoulder_elevation_palm_ratio_Pre.`);
  l("CROSSTABS Sex StrokeType AffectedSide BY Group /STATISTICS=CHISQ.");
  l("NPAR TESTS /MANN-WHITNEY MAS MRC BY Group(1 2).");
  l("");

  l("* --- 5. NORMALITY (Shapiroâ€“Wilk via EXAMINE) ---");
  l("* Run for each DV if needed; example for primary:");
  l(`EXAMINE VARIABLES=${primaryKey}_Pre ${primaryKey}_Post delta_${primaryKey} BY Group(1 2)`);
  l("  /PLOT BOXPLOT HISTOGRAM NPPLOT");
  l("  /STATISTICS DESCRIPTIVES");
  l("  /CINEMETRIC ALPHA(0.05).");
  l("* Decision: pâ‰¥.05 â†’ parametric GLM; p<.05 â†’ Wilcoxon (within) + Mann-Whitney (Î” between).");
  l("");

  l(`* --- 6. PRIMARY OUTCOMES (hierarchical: completion, then reach-window smoothness) ---`);
  l("* Interpret task_complete / task_completion_ratio before smoothness.");
  l("* Reach-window NVP family is comparable even when the cup was not lifted in Pre.");
  l("* Full-task NVP is exploratory: SELECT IF task_complete_Pre = task_complete_Post.");
  kinPrimary.forEach(({ key, label }) => {
    spssMixedGlm(l, key, label, { primary: true });
  });
  l("");

  if (kinSecondary.length) {
  l("* --- 7. SECONDARY KINEMATIC ---");
  l(`* Multiplicity: Holmâ€“Bonferroni across ${kinSecondary.length} secondary tests below.`);
  kinSecondary.forEach(({ key, label }) => {
    spssMixedGlm(l, key, label);
  });

  l(`* --- 7b. HOLMâ€“BONFERRONI (secondary kinematic family, k=${kinSecondary.length}) ---`);
  l(`* 1) Record GroupÃ—Time interaction p-values from step 7.`);
  l(`* 2) Sort p-values ascending: p(1) â‰¤ â€¦ â‰¤ p(${kinSecondary.length}).`);
  l(`* 3) Compare p(k) to Î±/(${kinSecondary.length}âˆ’k+1); report uncorrected + Holm-adjusted.`);
  l("");
  }

  if (kinExploratory.length) {
  l("* --- 8. EXPLORATORY KINEMATIC (no correction) ---");
  kinExploratory.forEach(({ key, label }) => {
    spssMixedGlm(l, key, label, { comment: "Exploratory â€” interpret cautiously" });
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

  const secondaryDeltaKeys = kinSecondary.map(({ key }) => `delta_${key}`).join(" ");

  l("* --- 11. MODERATORS & EXPLORATORY CORRELATIONS ---");
  l("SPLIT FILE LAYERED BY Group.");
  l("CORRELATIONS /VARIABLES=KVIQ_Vis_Pre KVIQ_Kin_Pre");
  l(`  delta_${primaryKey} ${secondaryDeltaKeys}`);
  l("  /PRINT=TWOTAIL NOSIG /MISSING=PAIRWISE.");
  l("SPLIT FILE OFF.");
  l(`CORRELATIONS /VARIABLES=delta_VAMS_Happy delta_VAMS_Calm delta_${primaryKey} delta_trunk_ratio /PRINT=TWOTAIL NOSIG.`);
  l("FREQUENCIES IPAQ_MET /STATISTICS=MEAN STDDEV MEDIAN.");
  l("");

  l("* --- 12. NON-PARAMETRIC BACKUP (if Shapiro p < .05) ---");
  l(`* Within AOMI: NPAR TESTS /WILCOXON ${primaryKey}_Pre WITH ${primaryKey}_Post (PAIRED).`);
  l("* Within Control: repeat Wilcoxon per group.");
  l(`* Between groups on Î”: NPAR TESTS /MANN-WHITNEY delta_${primaryKey} BY Group(1 2).`);
  l("");

  l("* --- 13. SENSITIVITY: LOCF + MIXED MODELS (ITT) ---");
  l("* LOCF: replace missing Post with Pre (document n imputed per variable).");
  l("* Example mixed model for primary:");
  l(`* MIXED ${primaryKey} BY Group time /FIXED=Group time Group*time /REPEATED=time | SUBJECT(ID) COVTYPE(AR1).`);
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

  const groupIsAomi = (r) => String(r.Group) === "1" || r.Group === 1;
  const groupIsCtrl = (r) => String(r.Group) === "2" || r.Group === 2;
  const aomi = rows.filter(groupIsAomi);
  const ctrl = rows.filter(groupIsCtrl);

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
  stats.isPrimary = pre.includes(KINEMATIC_VARS.find((k) => k.tier === "primary")?.key || "nvp");

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
  if (p == null || Number.isNaN(p)) return "â€”";
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
