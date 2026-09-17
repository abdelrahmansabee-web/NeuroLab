/** Clinical / ADL movement tasks (UE + LE). Backend maps each id to its analysis window. */

export const UE_CLINICAL_TASK_IDS = [
  "study_reach_grasp",
  "forearm_pronation_supination",
  "shoulder_abduction_active",
  "fine_motor_pincer",
  "reach_grasp_drink_return",
  "reach_grasp_brush_return",
];

export const LE_CLINICAL_TASK_IDS = [
  "sts_stand",
  "bodyweight_squat",
  "overground_gait",
  "quiet_stance_balance",
];

export const CLINICAL_MOVEMENT_TASKS = [
  {
    id: "study_reach_grasp",
    label: "Reach to grasp — study (cube)",
    hint: "Fastest on Hugging Face — ethics primary reach only. Use this unless you need multi-phase ADL.",
    phaseIds: ["reach_grasp"],
    domain: "ue",
  },
  {
    id: "forearm_pronation_supination",
    label: "Forearm pronation / supination",
    hint: "Window = max ROM on forearm roll (world 3D when available). Expected ROM ≈ 40–180°.",
    expectedRomDeg: [40, 180],
    phaseIds: ["forearm_rotation"],
    domain: "ue",
  },
  {
    id: "shoulder_abduction_active",
    label: "Active shoulder abduction (isolated)",
    hint: "Optional isolated abduction drill. For functional abduction during ADL, use brush teeth — read abduction on the transport-to-face phase.",
    expectedRomDeg: [30, 120],
    phaseIds: ["shoulder_abduction"],
    domain: "ue",
  },
  {
    id: "fine_motor_pincer",
    label: "Fine motor — pincer / pinch",
    hint: "Window = max pinch aperture (Hand Landmarker tips when model present). Expected aperture ROM ≈ 0.02–0.35 shoulder widths.",
    expectedRomSw: [0.02, 0.35],
    phaseIds: ["pincer_pinch"],
    domain: "ue",
  },
  {
    id: "reach_grasp_drink_return",
    label: "Reach → grasp → drink → return",
    hint: "Slower on HF CPU: 3 movement bouts + drink lift / transport metrics. Prefer study reach for speed.",
    adlAbductionPhaseId: "transport_drink",
    phaseIds: ["reach_grasp", "transport_drink", "return"],
    domain: "ue",
  },
  {
    id: "reach_grasp_brush_return",
    label: "Reach → grasp → brush teeth → return",
    hint: "Per-phase metrics; transport-to-face is best for abduction, forearm rotation, and fine motor / pinch.",
    adlAbductionPhaseId: "transport_brush",
    phaseIds: ["reach_grasp", "transport_brush", "return"],
    domain: "ue",
  },
  {
    id: "sts_stand",
    label: "Sit-to-Stand",
    hint: "Rise from chair to stand. Frontal or 45° camera; full body visible.",
    phaseIds: ["sts"],
    domain: "le",
  },
  {
    id: "bodyweight_squat",
    label: "Bodyweight squat",
    hint: "Controlled squat depth. Capture both knees and trunk lean.",
    phaseIds: ["squat"],
    domain: "le",
  },
  {
    id: "overground_gait",
    label: "Overground gait",
    hint: "Walk 5–8 m; sagittal-oblique view. Prefer known walkway length for m/s.",
    phaseIds: ["gait"],
    domain: "le",
  },
  {
    id: "quiet_stance_balance",
    label: "Quiet stance balance",
    hint: "Feet still, arms relaxed; 20–30 s. Frontal view for sway/symmetry.",
    phaseIds: ["balance"],
    domain: "le",
  },
];

/** Per-phase UI notes (multi-bout ADL + LE). */
export const TASK_PHASE_NOTES = {
  reach_grasp: "Reach & grasp — shoulder abduction, fine motor / pinch, finger open/close, tremor, and head compensation on the reach window.",
  transport_drink: "Cup at mouth — shoulder abduction, finger open/close quality, and head forward/flexion compensation.",
  transport_brush: "Brush at face — best phase for shoulder abduction, forearm rotation, and fine motor / pinch.",
  return: "Return to rest — compensation and trunk ratio still apply.",
  forearm_rotation: "Forearm pronation/supination — ROM and peak rotation speed on the max-ROM window.",
  shoulder_abduction: "Active shoulder abduction — ROM, peak speed, and abduction+trunk compensation.",
  pincer_pinch: "Pincer / pinch — aperture ROM and pinch/fine-motor quality (Hand Landmarker when available).",
  sts: "Sit-to-stand — COM rise, knee extension, weight-shift symmetry, trunk compensation.",
  squat: "Squat — depth, eccentric/concentric timing, knee symmetry, forward lean.",
  gait: "Gait — speed, cadence, DF/PF vs norm, FPA/rotation proxy, compensations (hike/circumduction/foot-drop).",
  balance: "Quiet stance — COM sway path/area, sway velocity, loading symmetry.",
};

/** Default core result keys per task (results table). */
export const TASK_CORE_METRIC_KEYS = {
  study_reach_grasp: [
    "task_complete",
    "nvp_reach",
    "straightness",
    "pause_time_sec",
    "number_of_stops",
    "trunk_ratio",
    "shoulder_elevation_cm",
    "peak_velocity_cm_s",
    "movement_time_sec",
    "tremor_8_12hz_power",
    "fine_motor_quality_index",
  ],
  forearm_pronation_supination: [
    "task_complete",
    "forearm_pronation_supination_rom_deg",
    "peak_forearm_rotation_vel_deg_s",
    "sparc_forearm_rotation",
    "tremor_8_12hz_power",
    "movement_time_sec",
    "movement_quality_index",
  ],
  shoulder_abduction_active: [
    "task_complete",
    "shoulder_abduction_rom_deg",
    "shoulder_abduction_mean_deg",
    "peak_shoulder_abduction_vel_deg_s",
    "shoulder_abduction_trunk_compensation_index",
    "trunk_ratio",
    "movement_time_sec",
    "movement_quality_index",
  ],
  fine_motor_pincer: [
    "task_complete",
    "fine_motor_quality_index",
    "pinch_grasp_quality_index",
    "pinch_tremor_8_12hz_power",
    "finger_flex_ext_quality_index",
    "tremor_8_12hz_power",
    "movement_time_sec",
    "movement_quality_index",
  ],
  reach_grasp_drink_return: [
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
  ],
  reach_grasp_brush_return: [
    "task_complete",
    "nvp_reach",
    "nvp_return",
    "nvp_total",
    "straightness",
    "pause_time_sec",
    "number_of_stops",
    "trunk_ratio",
    "shoulder_elevation_cm",
    "shoulder_abduction_rom_deg",
    "forearm_pronation_supination_rom_deg",
    "peak_velocity_cm_s",
    "movement_time_sec",
    "tremor_8_12hz_power",
    "fine_motor_quality_index",
  ],
  sts_stand: [
    "movement_quality_index",
    "sts_time_sec",
    "com_rise_norm",
    "lr_symmetry_index",
    "weight_shift_asymmetry",
    "trunk_lean_max_deg",
    "trunk_compensation_index",
    "movement_time_sec",
  ],
  bodyweight_squat: [
    "movement_quality_index",
    "squat_depth_norm",
    "min_knee_angle_deg",
    "lr_symmetry_index",
    "trunk_lean_max_deg",
    "knee_rom_L_deg",
    "knee_rom_R_deg",
    "movement_time_sec",
  ],
  overground_gait: [
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
    "movement_time_sec",
  ],
  quiet_stance_balance: [
    "movement_quality_index",
    "com_sway_path_norm",
    "com_sway_area_norm",
    "sway_velocity_mean",
    "lr_loading_symmetry",
    "lr_symmetry_index",
    "trunk_lean_max_deg",
    "movement_time_sec",
  ],
};

/** Per-phase metric chips under Task phases panel. */
export const TASK_PHASE_METRIC_KEYS = [
  { key: "movement_time_sec", label: "Movement time", unit: "s" },
  { key: "nvp", label: "NVP", unit: "" },
  { key: "straightness", label: "Straightness", unit: "" },
  { key: "pause_time_sec", label: "Pause time", unit: "s" },
  { key: "number_of_stops", label: "Stops", unit: "" },
  { key: "peak_hand_speed_px_s", label: "Peak hand speed", unit: "px/s" },
  { key: "elbow_rom_deg", label: "Elbow ROM", unit: "°" },
  { key: "peak_elbow_ang_vel_deg_s", label: "Peak elbow speed", unit: "°/s" },
  { key: "shoulder_flexion_mean_deg", label: "Shoulder flexion (mean)", unit: "°" },
  { key: "peak_shoulder_flexion_vel_deg_s", label: "Peak shoulder flex speed", unit: "°/s" },
  { key: "shoulder_abduction_mean_deg", label: "Shoulder abduction", unit: "°" },
  { key: "peak_shoulder_abduction_vel_deg_s", label: "Peak abduction speed", unit: "°/s" },
  { key: "shoulder_abduction_trunk_compensation_index", label: "Abduction+trunk compensation", unit: "0–1" },
  { key: "forearm_pronation_supination_rom_deg", label: "Pron/sup ROM", unit: "°" },
  { key: "peak_forearm_rotation_vel_deg_s", label: "Peak forearm rotation", unit: "°/s" },
  { key: "sparc_shoulder_flexion", label: "SPARC shoulder flexion", unit: "" },
  { key: "sparc_shoulder_abduction", label: "SPARC shoulder abduction", unit: "" },
  { key: "sparc_forearm_rotation", label: "SPARC forearm rotation", unit: "" },
  { key: "tremor_8_12hz_power", label: "Tremor 8–12 Hz (hand)", unit: "rel." },
  { key: "tremor_index", label: "Tremor index", unit: "0–100" },
  { key: "fine_motor_quality_index", label: "Fine motor quality", unit: "0–100" },
  { key: "pinch_grasp_quality_index", label: "Pinch/grasp quality (HL)", unit: "0–100" },
  { key: "pinch_tremor_8_12hz_power", label: "Pinch tremor 8–12 Hz", unit: "rel." },
  { key: "finger_flex_ext_rom_sw", label: "Finger flex/ext ROM", unit: "SW" },
  { key: "finger_flex_ext_quality_index", label: "Finger flex/ext quality", unit: "0–100" },
  { key: "head_forward_flexion_compensation_index", label: "Head forward flexion", unit: "0–1" },
  { key: "trunk_ratio", label: "Trunk ratio", unit: "" },
  { key: "compensation_index", label: "Compensation", unit: "0–1" },
  { key: "movement_quality_index", label: "Quality index", unit: "0–100" },
  { key: "gait_speed_m_s", label: "Gait speed", unit: "m/s" },
  { key: "cadence_spm", label: "Cadence", unit: "steps/min" },
  { key: "lr_symmetry_index", label: "L/R symmetry", unit: "0–1" },
  { key: "ankle_df_peak_L_deg", label: "Ankle DF peak L", unit: "°" },
  { key: "ankle_df_peak_R_deg", label: "Ankle DF peak R", unit: "°" },
  { key: "ankle_pf_peak_L_deg", label: "Ankle PF peak L", unit: "°" },
  { key: "ankle_pf_peak_R_deg", label: "Ankle PF peak R", unit: "°" },
  { key: "foot_drop_index", label: "Foot-drop index", unit: "0–1" },
  { key: "hip_hike_index", label: "Hip-hike index", unit: "0–1" },
  { key: "circumduction_index", label: "Circumduction index", unit: "0–1" },
  { key: "sts_time_sec", label: "STS time", unit: "s" },
  { key: "squat_depth_norm", label: "Squat depth (HW)", unit: "" },
  { key: "com_sway_path_norm", label: "COM sway path", unit: "HW" },
];

export function clinicalTaskById(id) {
  return CLINICAL_MOVEMENT_TASKS.find((t) => t.id === id) || CLINICAL_MOVEMENT_TASKS[0];
}

export function isLeClinicalTaskId(id) {
  return LE_CLINICAL_TASK_IDS.includes(String(id || "").toLowerCase());
}

export function isUeClinicalTaskId(id) {
  return UE_CLINICAL_TASK_IDS.includes(String(id || "").toLowerCase());
}

export function clinicalTaskDomain(id) {
  if (isLeClinicalTaskId(id)) return "le";
  return "ue";
}

export function clinicalTasksForDomain(domain) {
  const d = String(domain || "ue").toLowerCase() === "le" ? "le" : "ue";
  return CLINICAL_MOVEMENT_TASKS.filter((t) => (t.domain || "ue") === d);
}

export const CLINICAL_DOMAIN_LABELS = {
  ue: { en: "Upper Extremity", tr: "Üst Ekstremite", short: "UE" },
  le: { en: "Lower Extremity", tr: "Alt Ekstremite", short: "LE" },
};

export function coreMetricKeysForTask(taskId) {
  const id = String(taskId || "study_reach_grasp").toLowerCase();
  return TASK_CORE_METRIC_KEYS[id] || TASK_CORE_METRIC_KEYS.study_reach_grasp;
}
