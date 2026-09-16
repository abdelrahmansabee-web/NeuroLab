import {
  clampTableUserMark,
  clearTableUserMark,
  clientPointToOverlayNorm,
  hitTableMark,
  loadSharedTableSurfaceY,
  loadTableUserMark,
  saveSharedTableSurfaceY,
  saveTableUserMark,
  tableMarkHitGeom,
  tableUserMarkStorageKey,
} from "./overlayTableUserMark";

test("storage key prefers the overlay video filename", () => {
  expect(tableUserMarkStorageKey(
    { overlay_video_filename: "drink_pre.mp4" },
    "https://example/files/other.mp4",
  )).toBe("nl-table-user-mark:drink_pre.mp4");
});

test("clamp keeps a clinician table point inside the frame", () => {
  expect(clampTableUserMark({ x: -0.2, y: 1.4 })).toEqual({
    x: 0.01,
    y: 0.98,
    source: "user",
  });
  expect(clampTableUserMark({ x: 0.22, y: 0.81 }).x).toBeCloseTo(0.22, 8);
});

test("load / save round-trips through localStorage", () => {
  const overlay = { overlay_video_filename: "unit-table.mp4" };
  clearTableUserMark(overlay, "");
  expect(loadTableUserMark(overlay, "")).toBeNull();
  saveTableUserMark(overlay, "", { x: 0.31, y: 0.84 });
  const got = loadTableUserMark(overlay, "");
  expect(got.x).toBeCloseTo(0.31, 8);
  expect(got.y).toBeCloseTo(0.84, 8);
  expect(got.source).toBe("user");
  clearTableUserMark(overlay, "");
});

test("a clinician table Y is reused as the shared surface hint", () => {
  localStorage.removeItem("nl-table-surface-y-hint");
  saveTableUserMark({ overlay_video_filename: "hint-a.mp4" }, "", { x: 0.22, y: 0.67 });
  expect(loadSharedTableSurfaceY()).toBeCloseTo(0.67, 8);
  expect(saveSharedTableSurfaceY(0.48)).toBeNull();
  expect(loadSharedTableSurfaceY()).toBeCloseTo(0.67, 8);
  localStorage.removeItem("nl-table-surface-y-hint");
});

test("pointer on the canvas box maps to overlay 0–1", () => {
  const rect = { left: 100, top: 50, width: 200, height: 400 };
  expect(clientPointToOverlayNorm(100, 50, rect)).toEqual({ x: 0, y: 0 });
  expect(clientPointToOverlayNorm(200, 250, rect)).toEqual({ x: 0.5, y: 0.5 });
  expect(clientPointToOverlayNorm(90, 250, rect)).toBeNull();
  expect(clientPointToOverlayNorm(90, 250, rect, { clampToFrame: true }).x).toBe(0);
});

test("hit test covers the gold knob and the short table segment", () => {
  const g = tableMarkHitGeom({ x0: 80, x1: 120, xNorm: 0.5, yNorm: 0.8 }, 200);
  expect(hitTableMark({ x: 0.5, y: 0.8 }, g, { cssW: 200, cssH: 100 })).toBe(true);
  expect(hitTableMark({ x: 0.5, y: 0.82 }, g, { cssW: 200, cssH: 100 })).toBe(true);
  expect(hitTableMark({ x: 0.9, y: 0.8 }, g, { cssW: 200, cssH: 100 })).toBe(false);
});
