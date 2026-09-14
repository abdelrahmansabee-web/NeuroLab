import { overlayDist, pickForearmEnd, pointNear, shouldSnapSmooth } from "./overlayFollow";

const MIN_SIDE = 1000;

test("start of clip: pose and HL wrists together stay on the table hand", () => {
  const elbow = [400, 400];
  const pose = [420, 620];
  const hl = [425, 618];
  const end = pickForearmEnd(elbow, pose, hl, MIN_SIDE);
  expect(overlayDist(end, hl)).toBeLessThan(10);
});

test("HL on the table while pose wrist is at the raised hand keeps the pose wrist", () => {
  const elbow = [400, 380];
  const pose = [360, 220]; // up toward the mouth
  const hl = [620, 640]; // table to the side
  const end = pickForearmEnd(elbow, pose, hl, MIN_SIDE);
  expect(end).toEqual(pose);
});

test("lagged pose wrist yields to HL wrist further along the same forearm", () => {
  const elbow = [400, 500];
  const pose = [390, 420]; // short, on the chest
  const hl = [370, 250]; // same direction, at the real wrist
  const end = pickForearmEnd(elbow, pose, hl, MIN_SIDE);
  expect(end).toEqual(hl);
});

test("finger dots far from the hand root are not near", () => {
  const root = [370, 250];
  const tableTip = [620, 640];
  expect(pointNear(tableTip, root, 0.22 * MIN_SIDE)).toBe(false);
  expect(pointNear([375, 240], root, 0.22 * MIN_SIDE)).toBe(true);
});

test("large landmark jumps snap instead of smearing across the chest", () => {
  expect(shouldSnapSmooth([620, 640], [370, 250], MIN_SIDE)).toBe(true);
  expect(shouldSnapSmooth([370, 250], [372, 248], MIN_SIDE)).toBe(false);
});
