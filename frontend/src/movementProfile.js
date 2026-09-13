/** Extended movement specs (task-agnostic profile from backend `movement_profile`). */

export const MOVEMENT_PROFILE_GROUP_LABELS = {
  quality: "Overall movement quality",
  joint: "Elbow & shoulder flexion",
  shoulder_abduction: "Shoulder abduction",
  forearm: "Forearm pronation / supination",
  fine_motor: "Fine motor (index & pinch)",
  hand: "Hand transport speed",
};

export const MOVEMENT_PROFILE_GROUP_ORDER = [
  "quality",
  "joint",
  "shoulder_abduction",
  "forearm",
  "fine_motor",
  "hand",
];

export const MOVEMENT_PROFILE_FIELDS = [
  { key: "movement_quality_index", label: "Movement quality index", unit: "0–100", group: "quality" },
  { key: "compensation_index", label: "Compensation index", unit: "0–1", group: "quality" },
  { key: "shoulder_abduction_trunk_compensation_index", label: "Abduction + trunk compensation", unit: "0–1", group: "quality" },
  { key: "sparc_shoulder_flexion", label: "SPARC — shoulder flexion", unit: "", group: "quality" },
  { key: "sparc_shoulder_abduction", label: "SPARC — shoulder abduction", unit: "", group: "quality" },
  { key: "sparc_forearm_rotation", label: "SPARC — forearm rotation", unit: "", group: "quality" },
  { key: "tremor_8_12hz_power", label: "Tremor 8–12 Hz (hand speed)", unit: "rel.", group: "quality" },
  { key: "tremor_index", label: "Tremor index (100=smooth)", unit: "0–100", group: "quality" },
  { key: "elbow_tremor_8_12hz_power", label: "Elbow tremor 8–12 Hz", unit: "rel.", group: "quality" },
  { key: "shoulder_flexion_tremor_8_12hz_power", label: "Shoulder tremor 8–12 Hz", unit: "rel.", group: "quality" },
  { key: "task_pattern", label: "Task pattern", unit: "", group: "quality" },
  { key: "movement_segments_detected", label: "Movement bouts detected", unit: "count", group: "quality" },
  { key: "elbow_angle_min_deg", label: "Elbow flexion (min)", unit: "°", group: "joint" },
  { key: "elbow_angle_max_deg", label: "Elbow extension (max)", unit: "°", group: "joint" },
  { key: "elbow_rom_deg", label: "Elbow ROM", unit: "°", group: "joint" },
  { key: "peak_elbow_ang_vel_deg_s", label: "Peak elbow opening speed", unit: "°/s", group: "joint" },
  { key: "mean_elbow_ang_vel_deg_s", label: "Mean elbow angular speed", unit: "°/s", group: "joint" },
  { key: "shoulder_flexion_mean_deg", label: "Shoulder flexion (mean)", unit: "°", group: "joint" },
  { key: "shoulder_flexion_rom_deg", label: "Shoulder flexion ROM", unit: "°", group: "joint" },
  { key: "peak_shoulder_flexion_vel_deg_s", label: "Peak shoulder flexion speed", unit: "°/s", group: "joint" },
  { key: "mean_shoulder_flexion_vel_deg_s", label: "Mean shoulder flexion speed", unit: "°/s", group: "joint" },
  { key: "shoulder_flexion_quality_index", label: "Shoulder flexion quality", unit: "0–100", group: "joint" },
  { key: "shoulder_abduction_mean_deg", label: "Shoulder abduction (mean)", unit: "°", group: "shoulder_abduction" },
  { key: "shoulder_abduction_rom_deg", label: "Shoulder abduction ROM", unit: "°", group: "shoulder_abduction" },
  { key: "peak_shoulder_abduction_vel_deg_s", label: "Peak shoulder abduction speed", unit: "°/s", group: "shoulder_abduction" },
  { key: "shoulder_abduction_quality_index", label: "Shoulder abduction quality", unit: "0–100", group: "shoulder_abduction" },
  { key: "forearm_rotation_mean_deg", label: "Forearm roll (mean vs rest)", unit: "°", group: "forearm" },
  { key: "forearm_pronation_supination_rom_deg", label: "Pronation/supination ROM", unit: "°", group: "forearm" },
  { key: "peak_forearm_rotation_vel_deg_s", label: "Peak forearm rotation speed", unit: "°/s", group: "forearm" },
  { key: "forearm_rotation_quality_index", label: "Forearm rotation quality", unit: "0–100", group: "forearm" },
  { key: "fine_motor_quality_index", label: "Fine motor quality", unit: "0–100", group: "fine_motor" },
  { key: "fine_motor_index_nvp", label: "Index-tip velocity peaks", unit: "count", group: "fine_motor" },
  { key: "fine_motor_index_speed_cv", label: "Index speed variability (CV)", unit: "", group: "fine_motor" },
  { key: "fine_motor_micro_stops", label: "Index micro-stops", unit: "count", group: "fine_motor" },
  { key: "pinch_aperture_rom_sw", label: "Pinch aperture ROM (shoulder widths)", unit: "", group: "fine_motor" },
  { key: "pinch_aperture_hl_rom_sw", label: "Pinch ROM — Hand Landmarker", unit: "", group: "fine_motor" },
  { key: "pinch_tremor_8_12hz_power", label: "Pinch tremor power (8–12 Hz)", unit: "rel.", group: "fine_motor" },
  { key: "pinch_grasp_quality_index", label: "Pinch/grasp quality (HL)", unit: "0–100", group: "fine_motor" },
  { key: "elbow_extension_at_peak_reach_deg", label: "Elbow at peak reach", unit: "°", group: "joint" },
  { key: "peak_hand_speed_px_s", label: "Peak hand speed", unit: "px/s", group: "hand" },
  { key: "mean_hand_speed_px_s", label: "Mean hand speed", unit: "px/s", group: "hand" },
];

export function getMovementProfile(phaseResult) {
  if (!phaseResult) return null;
  const nested = phaseResult.movement_profile;
  if (nested && typeof nested === "object") return nested;
  return null;
}

export function resolveProfileMetric(phaseResult, key, overlayData = null) {
  const profile = getMovementProfile(phaseResult);
  if (profile && profile[key] != null && profile[key] !== "") return profile[key];
  if (phaseResult && phaseResult[key] != null) return phaseResult[key];
  return null;
}

export function formatProfileValue(key, value) {
  if (value == null || value === "—") return "—";
  if (key === "task_pattern") return String(value).replace(/_/g, " ");
  if (typeof value === "string") return value;
  const n = Number(value);
  if (Number.isNaN(n)) return String(value);
  if (key === "movement_quality_index") return n.toFixed(0);
  if (key.endsWith("_quality_index") || key === "tremor_index") return n.toFixed(0);
  if (key.includes("tremor") && key.includes("power")) return `${(n * 100).toFixed(1)}% rel`;
  if (key === "compensation_index") return n.toFixed(2);
  if (key.includes("deg") && !key.includes("vel")) return n.toFixed(1);
  if (key.includes("vel") || key.includes("speed")) return n.toFixed(1);
  if (key === "movement_segments_detected") return String(Math.round(n));
  return n.toFixed(2);
}
