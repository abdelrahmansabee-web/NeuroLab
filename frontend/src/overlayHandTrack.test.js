import {
  buildPoseRestHand,
  buildSmoothedTracks,
  hlTipsOffPoseHand,
  interpPair,
  isHlOverlayKey,
  overlayPalmIsTrusted,
  resolveHandDrawSource,
  shouldDrawHlFingers,
} from "./overlayHandTrack";

describe("overlayHandTrack onset handoff", () => {
  test("pose rest index MCP sits on 2*palm - wrist (the real knuckle)", () => {
    const wrist = [400, 390];
    const palm = [413, 393];
    const elbow = [320, 380];
    const trunk = [330, 300];
    const hand = buildPoseRestHand(wrist, palm, elbow, trunk);
    const poseIndex = [2 * palm[0] - wrist[0], 2 * palm[1] - wrist[1]];
    const d = Math.hypot(
      hand.joints.index.mcp[0] - poseIndex[0],
      hand.joints.index.mcp[1] - poseIndex[1],
    );
    expect(d).toBeLessThan(0.05);
  });

  test("resting tips stay short of an open-hand (do not overshoot nails at onset)", () => {
    const wrist = [400, 390];
    const palm = [413, 393];
    const hand = buildPoseRestHand(wrist, palm, [320, 380], [330, 300]);
    const mcpLen = hand.mcpLen;
    const tipSpan = Math.hypot(
      hand.joints.index.tip[0] - wrist[0],
      hand.joints.index.tip[1] - wrist[1],
    ) / mcpLen;
    expect(tipSpan).toBeGreaterThan(1.35);
    expect(tipSpan).toBeLessThan(1.65);
    const openHand = 2.17;
    expect(tipSpan).toBeLessThan(openHand * 0.8);
  });

  test("thumb lies on the trunk side of the hand axis", () => {
    const wrist = [400, 390];
    const palm = [413, 393];
    const hand = buildPoseRestHand(wrist, palm, [320, 380], [330, 300]);
    const ux = (2 * palm[0] - wrist[0] - wrist[0]);
    const uy = (2 * palm[1] - wrist[1] - wrist[1]);
    const nx = -uy;
    const ny = ux;
    const thumb = hand.joints.thumb.tip;
    const trunk = [330, 300];
    const lat = (p) => (p[0] - wrist[0]) * nx + (p[1] - wrist[1]) * ny;
    expect(Math.sign(lat(thumb))).toBe(Math.sign(lat(trunk)));
  });

  test("HL finger keys are never smoothed (cup samples must not blend into the reach)", () => {
    const frames = [];
    for (let i = 0; i < 30; i += 1) {
      const cup = i < 10;
      frames.push({
        time: i / 60,
        wrist: [0.40, 0.50],
        palm: [0.43, 0.51],
        index: cup ? [0.80, 0.40] : [0.48, 0.52],
        finger_joints: {
          index: { tip: cup ? [0.80, 0.40] : [0.48, 0.52], vis: { tip: true } },
        },
      });
    }
    const tracks = buildSmoothedTracks(frames, 60);
    expect(isHlOverlayKey("index")).toBe(true);
    expect(isHlOverlayKey("fj:index:tip")).toBe(true);
    expect(tracks.at("index", 10)).toBeNull();
    const wrist = tracks.at("wrist", 10);
    expect(wrist[0]).toBeCloseTo(0.40, 5);
    expect(wrist[1]).toBeCloseTo(0.50, 5);
  });

  test("pose skeleton smoothing is zero-lag on a linear reach", () => {
    const frames = [];
    for (let i = 0; i < 40; i += 1) {
      frames.push({ wrist: [0.2 + i * 0.01, 0.5] });
    }
    const tracks = buildSmoothedTracks(frames, 60);
    const mid = tracks.at("wrist", 20);
    expect(Math.abs(mid[0] - frames[20].wrist[0])).toBeLessThan(1e-6);
  });

  test("cup-latched tips are off the pose hand; resting digits are not", () => {
    const poseWrist = [100, 200];
    const palm = [120, 204];
    const palmReach = Math.hypot(20, 4);
    const onHand = [
      [128, 201],
      [130, 205],
      [126, 208],
      [122, 210],
      [118, 206],
    ];
    const onCup = [
      [210, 188],
      [218, 180],
      [205, 175],
      [198, 190],
      [225, 170],
    ];
    expect(hlTipsOffPoseHand({
      poseWrist,
      hlWrist: poseWrist,
      tips: onHand,
      forearmPx: 90,
      palmReachPx: palmReach,
      handSpan: 640,
    })).toBe(false);
    expect(hlTipsOffPoseHand({
      poseWrist,
      hlWrist: [210, 185],
      tips: onCup,
      forearmPx: 90,
      palmReachPx: palmReach,
      handSpan: 640,
    })).toBe(true);
  });

  test("off-hand never draws HL joints even if the source flag still says hl", () => {
    expect(shouldDrawHlFingers(true, "hl")).toBe(false);
    expect(shouldDrawHlFingers(true, "pose")).toBe(false);
    expect(shouldDrawHlFingers(false, "pose")).toBe(false);
    expect(shouldDrawHlFingers(false, "hl")).toBe(true);
  });

  test("handoff waits for consecutive on-hand frames then snaps (no blend flag)", () => {
    let st = { src: "hl", offStreak: 0, onStreak: 0 };
    st = resolveHandDrawSource(st, true);
    expect(st.src).toBe("pose");
    expect(st.switched).toBe(true);
    st = resolveHandDrawSource(st, false);
    expect(st.src).toBe("pose");
    st = resolveHandDrawSource(st, false);
    st = resolveHandDrawSource(st, false);
    expect(st.src).toBe("pose");
    st = resolveHandDrawSource(st, false);
    expect(st.src).toBe("hl");
    expect(st.switched).toBe(true);
  });

  test("interpPair blends overlay samples", () => {
    expect(interpPair([0, 0], [10, 10], 0.5)).toEqual([5, 5]);
    expect(interpPair([3, 4], null, 0.9)).toEqual([3, 4]);
  });

  test("overlay palm is trusted only at pose-knuckle distance, not cup distance", () => {
    expect(overlayPalmIsTrusted(16, 80, 640)).toBe(true);
    expect(overlayPalmIsTrusted(30, 80, 640)).toBe(true);
    expect(overlayPalmIsTrusted(90, 80, 640)).toBe(false);
    expect(overlayPalmIsTrusted(2, 80, 640)).toBe(false);
  });

  test("POST: cup-distance overlay palm must not hide an off-hand latch", () => {
    const poseWrist = [100, 200];
    const forearmPx = Math.hypot(80, 10);
    const cup = [220, 185];
    const cupTips = [
      [218, 180],
      [225, 176],
      [212, 178],
      [208, 186],
      [230, 172],
    ];
    const cupMcps = cupTips.map(([x, y]) => [x - 4, y + 3]);
    const palmReachPx = Math.hypot(cup[0] - poseWrist[0], cup[1] - poseWrist[1]);
    expect(overlayPalmIsTrusted(palmReachPx, forearmPx, 640)).toBe(false);
    // Server often stores kinematic palm as hl_wrist when HL WRIST is missing,
    // while INDEX / finger_joints stay on the cup.
    expect(hlTipsOffPoseHand({
      poseWrist,
      hlWrist: [113, 204],
      tips: cupTips,
      mcps: cupMcps,
      forearmPx,
      palmReachPx,
      handSpan: 640,
    })).toBe(true);
  });

  test("PRE: on-finger overlay palm and MCPs stay on-hand", () => {
    const poseWrist = [100, 200];
    const forearmPx = 90;
    const onHandTips = [
      [128, 201],
      [130, 205],
      [126, 208],
      [122, 210],
      [118, 206],
    ];
    const onHandMcps = [
      [118, 201],
      [119, 204],
      [117, 206],
      [115, 207],
      [113, 204],
    ];
    const palmReachPx = Math.hypot(20, 4);
    expect(hlTipsOffPoseHand({
      poseWrist,
      hlWrist: [102, 201],
      tips: onHandTips,
      mcps: onHandMcps,
      forearmPx,
      palmReachPx,
      handSpan: 640,
    })).toBe(false);
  });

  test("PRE reach: extended tips stay on-hand when MCPs remain at the wrist", () => {
    const poseWrist = [100, 200];
    const forearmPx = 90;
    const reachTips = [
      [100 + forearmPx * 0.88, 200],
      [100 + forearmPx * 0.90, 204],
      [100 + forearmPx * 0.86, 208],
      [100 + forearmPx * 0.80, 210],
      [100 + forearmPx * 0.72, 206],
    ];
    const reachMcps = [
      [128, 201],
      [129, 204],
      [127, 206],
      [125, 207],
      [123, 204],
    ];
    expect(hlTipsOffPoseHand({
      poseWrist,
      hlWrist: [104, 201],
      tips: reachTips,
      mcps: reachMcps,
      forearmPx,
      palmReachPx: forearmPx * 0.88,
      handSpan: 640,
    })).toBe(false);
  });

  test("cup overlay palm does not aim the rest hand at the cup", () => {
    const wrist = [400, 390];
    const elbow = [320, 380];
    const trunk = [330, 300];
    const posePalm = [413, 393];
    const cup = [520, 370];
    const fromPose = buildPoseRestHand(wrist, posePalm, elbow, trunk);
    const fromCup = buildPoseRestHand(wrist, cup, elbow, trunk);
    expect(fromCup).toBeTruthy();
    const forearm = [wrist[0] - elbow[0], wrist[1] - elbow[1]];
    const toCup = [cup[0] - wrist[0], cup[1] - wrist[1]];
    const toTip = [
      fromCup.joints.index.tip[0] - wrist[0],
      fromCup.joints.index.tip[1] - wrist[1],
    ];
    const dot = (a, b) => a[0] * b[0] + a[1] * b[1];
    const align = (a, b) => dot(a, b) / (Math.hypot(a[0], a[1]) * Math.hypot(b[0], b[1]));
    expect(align(toTip, forearm)).toBeGreaterThan(0.95);
    expect(align(toTip, toCup)).toBeLessThan(align(toTip, forearm));
    const poseMcp = [2 * posePalm[0] - wrist[0], 2 * posePalm[1] - wrist[1]];
    expect(Math.hypot(
      fromPose.joints.index.mcp[0] - poseMcp[0],
      fromPose.joints.index.mcp[1] - poseMcp[1],
    )).toBeLessThan(0.05);
  });
});
