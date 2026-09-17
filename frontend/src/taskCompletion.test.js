import {
  deriveTaskCompletion,
  inferPalmTaskShape,
  inferPalmPhaseWindows,
  motionConfirmsAdlComplete,
  enrichKinematicCompletion,
  countTaskNvpFromPeaks,
} from "./taskCompletion";

function drinkFrames() {
  const frames = [];
  for (let i = 0; i < 40; i += 1) {
    let x = 0.42;
    let y = 0.74;
    if (i < 10) {
      x = 0.42 + i * 0.012;
      y = 0.74;
    } else if (i < 22) {
      x = 0.54;
      y = 0.74 - (i - 10) * 0.018;
    } else {
      x = 0.54 - (i - 22) * 0.008;
      y = 0.524 + (i - 22) * 0.012;
    }
    frames.push({ time: i / 30, palm: [x, y], wrist: [x, y + 0.02], speed: 12 });
  }
  return frames;
}

test("drink palm path is reach, lift, and return", () => {
  const shape = inferPalmTaskShape({ frames: drinkFrames() });
  expect(shape.liftOk).toBe(true);
  expect(shape.returnOk).toBe(true);
  expect(shape.reach).toBe(true);
});

test("backend Incomplete drink is Complete when overlay shows the full sip", () => {
  const result = {
    clinical_task: "reach_grasp_drink_return",
    task_complete: 0,
    task_completion_ratio: 0.333,
    completed_phase_ids: ["reach_grasp"],
    task_phases: [{ id: "reach_grasp" }],
  };
  expect(deriveTaskCompletion(result).taskComplete).toBe(false);
  expect(deriveTaskCompletion(result, { frames: drinkFrames() }).taskComplete).toBe(true);
  expect(enrichKinematicCompletion(result, { frames: drinkFrames() }).task_complete).toBe(1);
});

test("Complete is never downgraded by a still overlay", () => {
  const result = {
    clinical_task: "reach_grasp_drink_return",
    task_complete: 1,
    completed_phase_ids: ["reach_grasp", "transport_drink", "return"],
  };
  const still = { frames: Array.from({ length: 12 }, () => ({ palm: [0.5, 0.7] })) };
  expect(deriveTaskCompletion(result, still).taskComplete).toBe(true);
});

test("reach plus return plus lift height counts as a completed drink", () => {
  const result = {
    clinical_task: "reach_grasp_drink_return",
    task_complete: 0,
    completed_phase_ids: ["reach_grasp", "return"],
    task_phases: [{ id: "reach_grasp" }, { id: "return" }],
    drink_lift_height_cm: 8.2,
    nvp_reach: 2,
    nvp_return: 1,
  };
  expect(motionConfirmsAdlComplete(result, null)).toBe(true);
  expect(deriveTaskCompletion(result).taskComplete).toBe(true);
});

test("idle hands do not become Complete", () => {
  const result = {
    clinical_task: "reach_grasp_drink_return",
    task_complete: 0,
    completed_phase_ids: [],
  };
  const still = { frames: Array.from({ length: 16 }, () => ({ palm: [0.5, 0.72] })) };
  expect(deriveTaskCompletion(result, still).taskComplete).toBe(false);
});

test("stored nvp_total cannot stay below nvp_reach", () => {
  const enriched = enrichKinematicCompletion({
    nvp_reach: 13,
    nvp_drink: 4,
    nvp_return: 1,
    nvp_total: 7,
  });
  expect(enriched.nvp_reach).toBe(13);
  expect(enriched.nvp_drink).toBe(4);
  expect(enriched.nvp_return).toBe(1);
  expect(enriched.nvp_total).toBeGreaterThanOrEqual(enriched.nvp_reach);
  expect(enriched.nvp_total).toBe(13);
});

test("NVP rows recount from the same peak_frames as the overlay", () => {
  const overlay = {
    fps: 60,
    frames: Array.from({ length: 40 }, (_, i) => ({ time: i / 60, palm: [0.4, 0.7], speed: 12 })),
    movement_window: { start_idx: 4, end_idx: 30 },
    peak_frames: [2, 6, 10, 16, 22, 28],
  };
  const result = {
    nvp_reach: 99,
    nvp_drink: 99,
    nvp_return: 99,
    nvp_total: 1,
    task_phases: [
      { id: "reach_grasp", start_frame: 4, end_frame: 12 },
      { id: "transport_drink", start_frame: 13, end_frame: 22 },
      { id: "return", start_frame: 23, end_frame: 30 },
    ],
  };
  const fromPeaks = countTaskNvpFromPeaks(result, overlay);
  expect(fromPeaks.nvp_reach).toBe(2);
  expect(fromPeaks.nvp_drink).toBe(2);
  expect(fromPeaks.nvp_return).toBe(1);
  expect(fromPeaks.nvp_total).toBe(5);
  const enriched = enrichKinematicCompletion(result, overlay);
  expect(enriched.nvp_reach).toBe(2);
  expect(enriched.nvp_drink).toBe(2);
  expect(enriched.nvp_return).toBe(1);
  expect(enriched.nvp_total).toBe(5);
  expect(enriched.nvp_total).toBe(enriched.nvp_reach + enriched.nvp_drink + enriched.nvp_return);
});

test("nested reach window does not swallow drink and return NVP", () => {
  const overlay = {
    fps: 60,
    frames: Array.from({ length: 40 }, (_, i) => ({ time: i / 60, palm: [0.4, 0.7], speed: 12 })),
    movement_window: { start_idx: 4, end_idx: 30 },
    peak_frames: [2, 6, 10, 16, 22, 28],
  };
  const result = {
    nvp_reach: 99,
    nvp_drink: 99,
    nvp_return: 99,
    nvp_total: 1,
    task_phases: [
      { id: "reach_grasp", start_frame: 4, end_frame: 30 },
      { id: "transport_drink", start_frame: 13, end_frame: 22 },
      { id: "return", start_frame: 23, end_frame: 30 },
    ],
  };
  const fromPeaks = countTaskNvpFromPeaks(result, overlay);
  expect(fromPeaks.nvp_reach).toBe(2);
  expect(fromPeaks.nvp_drink).toBe(2);
  expect(fromPeaks.nvp_return).toBe(1);
  expect(fromPeaks.nvp_total).toBe(5);
  const enriched = enrichKinematicCompletion(result, overlay);
  expect(enriched.nvp_reach).toBe(2);
  expect(enriched.nvp_drink).toBe(2);
  expect(enriched.nvp_return).toBe(1);
  expect(enriched.nvp_total).toBe(5);
  expect(enriched.nvp_total).toBe(enriched.nvp_reach + enriched.nvp_drink + enriched.nvp_return);
});

test("missing reach window still partitions leftover peaks after drink/return", () => {
  const overlay = {
    fps: 60,
    frames: Array.from({ length: 40 }, (_, i) => ({ time: i / 60, palm: [0.4, 0.7], speed: 12 })),
    movement_window: { start_idx: 4, end_idx: 30 },
    peak_frames: [2, 6, 10, 16, 22, 28],
  };
  const result = {
    nvp_reach: 99,
    nvp_drink: 99,
    nvp_return: 99,
    nvp_total: 1,
    task_phases: [
      { id: "transport_drink", start_frame: 13, end_frame: 22 },
      { id: "return", start_frame: 23, end_frame: 30 },
    ],
  };
  const fromPeaks = countTaskNvpFromPeaks(result, overlay);
  expect(fromPeaks.nvp_reach).toBe(2);
  expect(fromPeaks.nvp_drink).toBe(2);
  expect(fromPeaks.nvp_return).toBe(1);
  expect(fromPeaks.nvp_total).toBe(5);
});

test("without phase frames, overlay palm split still partitions drink/return into total", () => {
  const frames = drinkFrames();
  const overlay = {
    fps: 30,
    frames,
    movement_window: { start_idx: 0, end_idx: frames.length - 1 },
    peak_frames: [3, 8, 14, 18, 25, 32],
  };
  const wins = inferPalmPhaseWindows(overlay);
  expect(wins).not.toBeNull();
  expect(wins.drink.startIdx).toBeGreaterThan(wins.reach.startIdx);
  expect(wins.return.startIdx).toBeGreaterThan(wins.drink.startIdx);
  const result = {
    clinical_task: "reach_grasp_drink_return",
    nvp_reach: 12,
    nvp_drink: 4,
    nvp_return: 1,
    nvp_total: 7,
  };
  const fromPeaks = countTaskNvpFromPeaks(result, overlay);
  expect(fromPeaks.nvp_drink).toBeGreaterThan(0);
  expect(fromPeaks.nvp_return).toBeGreaterThan(0);
  expect(fromPeaks.nvp_total).toBe(
    (fromPeaks.nvp_reach || 0) + (fromPeaks.nvp_drink || 0) + (fromPeaks.nvp_return || 0),
  );
  expect(fromPeaks.nvp_total).toBe(6);
  const enriched = enrichKinematicCompletion(result, overlay);
  expect(enriched.nvp_reach).toBe(fromPeaks.nvp_reach);
  expect(enriched.nvp_drink).toBe(fromPeaks.nvp_drink);
  expect(enriched.nvp_return).toBe(fromPeaks.nvp_return);
  expect(enriched.nvp_total).toBe(fromPeaks.nvp_total);
  expect(enriched.nvp_drink).not.toBe(4);
  expect(enriched.nvp_total).not.toBe(12);
});
