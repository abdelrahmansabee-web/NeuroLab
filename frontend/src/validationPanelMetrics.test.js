import {
  computeOverlayMetrics,
  computeValidationPanelLive,
  formatPanelAlignedKinValue,
} from "./validationPanelMetrics";
import { resolveKinMetricValue } from "./kinMetrics";

function frame({ t, palm, speed, elbow, shPalm = 0.1 }) {
  return {
    time: t,
    palm,
    trunk: [palm[0] * 0.2, palm[1]],
    speed,
    elbow_angle: elbow,
    shoulder_elevation_palm_ratio: shPalm,
    shoulder_elevation_table_ratio: shPalm,
    shoulder_elevation_norm: shPalm,
  };
}

function makeOverlay() {
  const fps = 60;
  const frames = [];
  for (let i = 0; i < 20; i += 1) {
    const moving = i >= 4 && i <= 14;
    frames.push(frame({
      t: i / fps,
      palm: [i * 10, 0],
      speed: i === 8 ? 0.2 : (moving ? 20 : 0.2),
      elbow: 90 + i * 2,
      shPalm: i === 14 ? 0.22 : 0.05,
    }));
  }
  return {
    fps,
    frames,
    movement_window: { start_idx: 4, end_idx: 14 },
    peak_frames: [2, 6, 10, 18],
    metrics: {
      peak_velocity_cm_s: 41.7,
      shoulder_elevation_cm: 3.4,
      elbow_angle_mean_deg: 111.1,
      movement_quality_index: 72.5,
      nvp: 99,
      straightness: 0.111,
      pause_time_sec: 9.99,
      number_of_stops: 99,
    },
  };
}

test("table snapshot uses panel formulas at movement-window end, not server metrics", () => {
  const overlay = makeOverlay();
  const panel = computeValidationPanelLive(overlay, 14);
  const table = computeOverlayMetrics(overlay);

  expect(panel).not.toBeNull();
  expect(table.nvp).toBe(panel.nvp);
  expect(table.nvp).toBe(2);
  expect(table.nvp_reach).toBeUndefined();
  expect(table.straightness).toBeCloseTo(panel.straightness, 8);
  expect(table.pause_time_sec).toBeCloseTo(panel.pauseTime, 8);
  expect(table.number_of_stops).toBe(panel.stops);
  expect(table.trunk_ratio).toBeCloseTo(panel.trunkRatio, 8);
  expect(table.movement_time_sec).toBeCloseTo(panel.movementTime, 8);
  expect(table.peak_velocity_cm_s).toBe(41.7);
  expect(table.shoulder_elevation_cm).toBe(3.4);
  expect(table.peak_elbow_ang_vel_deg_s).toBeCloseTo(panel.peakElbowAngVel, 8);
  expect(table.shoulder_elevation_palm_ratio).toBeCloseTo(0.22, 8);
});

test("panel pause counts every slow frame (no min-run / dwell split)", () => {
  const overlay = makeOverlay();
  const panel = computeValidationPanelLive(overlay, 14);
  const fps = 60;
  expect(panel.pauseTime).toBeCloseTo(1 / fps, 8);
  expect(panel.stops).toBe(1);
});

test("resolveKinMetricValue prefers panel NVP over backend nvp_reach", () => {
  const overlay = makeOverlay();
  const phaseResult = {
    nvp_reach: 7,
    nvp: 7,
    overlay_metrics: { nvp: 2, nvp_reach: 2 },
  };
  expect(resolveKinMetricValue(phaseResult, "nvp_reach", overlay)).toBe(2);
  expect(resolveKinMetricValue(phaseResult, "nvp", overlay)).toBe(2);
  expect(resolveKinMetricValue(phaseResult, "pause_time_sec", overlay)).toBeCloseTo(1 / 60, 8);
});

test("panel NVP ignores peaks before movement onset", () => {
  const overlay = makeOverlay();
  const panel = computeValidationPanelLive(overlay, 14);
  expect(panel.nvp).toBe(2);
  expect(overlay.peak_frames).toEqual([2, 6, 10, 18]);
});

test("panel-aligned format matches video panel decimals (ratio, not percent)", () => {
  expect(formatPanelAlignedKinValue("straightness", 0.87654)).toBe("0.88");
  expect(formatPanelAlignedKinValue("trunk_ratio", 0.321)).toBe("0.32");
  expect(formatPanelAlignedKinValue("movement_time_sec", 1.2)).toBe("1.20");
  expect(formatPanelAlignedKinValue("peak_velocity_cm_s", 41.73)).toBe("41.7");
  expect(formatPanelAlignedKinValue("pause_stops_panel", null, { pause_time_sec: 0.12, number_of_stops: 2 })).toBe("0.12 s / 2");
});
