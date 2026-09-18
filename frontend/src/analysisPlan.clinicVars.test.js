import {
  KINEMATIC_VARS,
  deriveRequestedClinicKinematics,
  formatKinValue,
  normalizeKinematicResult,
  pickKinField,
} from "./analysisPlan";
import { kinematicKeysForTask } from "./clinicExcelExport";
import { coreMetricKeysForTask } from "./clinicalTasks";

const byKey = Object.fromEntries(KINEMATIC_VARS.map((v) => [v.key, v]));

test("requested clinic variables exist with abduction lower-is-better", () => {
  expect(byKey.nvp_total.dir).toBe("lower");
  expect(byKey.shoulder_elevation_cm.label).toBe("Shoulder elevation");
  expect(byKey.trunk_forward_displacement_cm.dir).toBe("lower");
  expect(byKey.movement_time_sec.dir).toBe("lower");
  expect(byKey.average_hand_velocity_cm_s.unit).toBe("cm/s");
  expect(byKey.elbow_angle_mean_deg.label).toMatch(/Elbow extension/i);
  expect(byKey.shoulder_flexion_mean_deg.label).toMatch(/Shoulder flexion/i);
  expect(byKey.shoulder_abduction_mean_deg.dir).toBe("lower");
});

test("nvp_total falls back to nvp for reach-only results", () => {
  expect(pickKinField({ nvp: 5 }, "nvp_total")).toBe(5);
  expect(pickKinField({ nvp_total: 11, nvp: 5 }, "nvp_total")).toBe(11);
});

test("derives trunk forward cm and average hand velocity from stored px fields", () => {
  const out = deriveRequestedClinicKinematics({
    cm_per_px: 0.2,
    trunk_displacement_px: 40,
    movement_profile: { mean_hand_speed_px_s: 80 },
  });
  expect(out.trunk_forward_displacement_cm).toBeCloseTo(8, 8);
  expect(out.average_hand_velocity_cm_s).toBeCloseTo(16, 8);
});

test("normalizeKinematicResult keeps existing nvp_total and fills missing cm keys", () => {
  const n = normalizeKinematicResult({
    nvp_total: 9,
    nvp: 4,
    movement_time_sec: 1.5,
    cm_per_px: 0.1,
    trunk_displacement_px: 30,
    movement_profile: {
      mean_hand_speed_px_s: 50,
      shoulder_flexion_mean_deg: 62.5,
      shoulder_abduction_mean_deg: 28.1,
      elbow_angle_mean_deg: 140.2,
    },
    shoulder_elevation_cm: 3.4,
  });
  expect(n.nvp_total).toBe(9);
  expect(n.movement_time_sec).toBe(1.5);
  expect(n.shoulder_elevation_cm).toBe(3.4);
  expect(n.trunk_forward_displacement_cm).toBeCloseTo(3, 8);
  expect(n.average_hand_velocity_cm_s).toBeCloseTo(5, 8);
  expect(n.shoulder_flexion_mean_deg).toBe(62.5);
  expect(n.shoulder_abduction_mean_deg).toBe(28.1);
  expect(n.elbow_angle_mean_deg).toBe(140.2);
});

test("reach / drink / brush SPSS cores include the requested variables", () => {
  const needed = [
    "nvp_total",
    "shoulder_elevation_cm",
    "trunk_forward_displacement_cm",
    "movement_time_sec",
    "average_hand_velocity_cm_s",
    "elbow_angle_mean_deg",
    "shoulder_flexion_mean_deg",
    "shoulder_abduction_mean_deg",
  ];
  ["study_reach_grasp", "reach_grasp_drink_return", "reach_grasp_brush_return"].forEach((taskId) => {
    const excel = kinematicKeysForTask(taskId);
    const core = coreMetricKeysForTask(taskId);
    needed.forEach((key) => {
      expect(core).toContain(key);
      expect(excel).toContain(key);
    });
  });
});

test("formatKinValue keeps existing NVP / elevation formatting", () => {
  expect(formatKinValue("nvp_total", 12)).toBe("12");
  expect(formatKinValue("shoulder_elevation_cm", 3.41)).toBe("3.4");
  expect(formatKinValue("average_hand_velocity_cm_s", 41.73)).toBe("41.7");
  expect(formatKinValue("trunk_forward_displacement_cm", 2.26)).toBe("2.3");
});
