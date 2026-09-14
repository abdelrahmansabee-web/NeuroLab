import {
  overlayDist,
  pickForearmEnd,
  pickMovingHandRoot,
  pointNear,
  shouldSnapSmooth,
  splitMovedFromRest,
  elbowOnArm,
  centroid,
} from "./overlayFollow";

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
  const pose = [360, 220];
  const hl = [620, 640];
  const end = pickForearmEnd(elbow, pose, hl, MIN_SIDE);
  expect(end).toEqual(pose);
});

test("lagged pose wrist yields to HL wrist further along the same forearm", () => {
  const elbow = [400, 500];
  const pose = [390, 420];
  const hl = [370, 250];
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

test("after the reach, table joints stay at rest and the cup cluster is the one that moved", () => {
  const rest = [700, 700];
  const table = [[680, 690], [700, 705], [720, 695]];
  const cup = [[560, 260], [575, 250], [590, 270]];
  const { moved, stuck } = splitMovedFromRest([...table, ...cup], rest, MIN_SIDE);
  expect(stuck).toHaveLength(3);
  expect(moved).toHaveLength(3);
  expect(overlayDist(centroid(moved), [575, 260])).toBeLessThan(20);
});

test("mid-clip: do not point the forearm at the table rest hand", () => {
  const rest = [700, 700];
  const shoulder = [380, 360];
  const bellyElbow = [430, 520];
  const poseChest = [450, 500];
  const tableHl = [690, 690];
  const cupPalm = [560, 250];
  const movedCentroid = [575, 255];
  const root = pickMovingHandRoot({
    shoulder,
    elbow: bellyElbow,
    poseWrist: poseChest,
    hlWrist: tableHl,
    palm: cupPalm,
    movedCentroid,
    restPt: rest,
    minSide: MIN_SIDE,
  });
  expect(overlayDist(root, cupPalm)).toBeLessThan(30);
  expect(overlayDist(root, tableHl)).toBeGreaterThan(200);
  expect(elbowOnArm(shoulder, bellyElbow, root, MIN_SIDE)).toBe(false);
});

test("at rest, moving-root picker keeps the table hand", () => {
  const rest = [420, 620];
  const root = pickMovingHandRoot({
    shoulder: [400, 380],
    elbow: [410, 500],
    poseWrist: [420, 620],
    hlWrist: [425, 618],
    palm: [430, 610],
    restPt: rest,
    minSide: MIN_SIDE,
  });
  expect(overlayDist(root, rest)).toBeLessThan(30);
});
