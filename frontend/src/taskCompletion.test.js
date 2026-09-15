import {
  deriveTaskCompletion,
  inferPalmTaskShape,
  motionConfirmsAdlComplete,
  enrichKinematicCompletion,
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
