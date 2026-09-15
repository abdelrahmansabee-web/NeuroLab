import {
  overlayPortalStyle,
  overlaySlotAspect,
  overlaySlotReserveStyle,
  readSlotBox,
  OVERLAY_PORTAL_Z_COMPACT,
  OVERLAY_PORTAL_Z_EXPANDED,
} from "./overlayExpandLayout";

test("expanded portal covers the viewport without using the card slot", () => {
  const style = overlayPortalStyle({
    isExpanded: true,
    slot: { left: 40, top: 80, width: 320, height: 180 },
  });
  expect(style.position).toBe("fixed");
  expect(style.top).toBe(0);
  expect(style.left).toBe(0);
  expect(style.right).toBe(0);
  expect(style.bottom).toBe(0);
  expect(style.zIndex).toBe(OVERLAY_PORTAL_Z_EXPANDED);
});

test("compact portal pins to the measured slot so the video node never moves", () => {
  const slot = { left: 24, top: 120, width: 400, height: 225 };
  const style = overlayPortalStyle({ isExpanded: false, slot });
  expect(style).toMatchObject({
    position: "fixed",
    left: 24,
    top: 120,
    width: 400,
    height: 225,
    zIndex: OVERLAY_PORTAL_Z_COMPACT,
  });
  expect(style.opacity).toBeUndefined();
  expect(style.pointerEvents).toBeUndefined();
});

test("unmeasured or tiny slots stay inert until layout exists", () => {
  expect(overlayPortalStyle({ isExpanded: false, slot: null }).opacity).toBe(0);
  expect(overlayPortalStyle({ isExpanded: false, slot: { left: 0, top: 0, width: 1, height: 40 } }).pointerEvents).toBe(
    "none",
  );
});

test("readSlotBox rounds the card placeholder rect", () => {
  expect(readSlotBox(null)).toBe(null);
  expect(
    readSlotBox({
      getBoundingClientRect: () => ({ left: 10.6, top: 20.4, width: 300.2, height: 168.8 }),
    }),
  ).toEqual({ left: 11, top: 20, width: 300, height: 169 });
  expect(
    readSlotBox({
      getBoundingClientRect: () => ({ left: 0, top: 0, width: 0, height: 0 }),
    }),
  ).toBe(null);
});

test("slot reserve uses live video aspect then overlay frame size", () => {
  expect(overlaySlotAspect(null, 1.777)).toBeCloseTo(1.777);
  expect(overlaySlotAspect({ frame_width_px: 1280, frame_height_px: 720 }, null)).toBeCloseTo(16 / 9);
  expect(overlaySlotAspect(null, null)).toBeCloseTo(16 / 9);
  expect(overlaySlotReserveStyle(16 / 9).aspectRatio).toBe(String(16 / 9));
  expect(overlaySlotReserveStyle(16 / 9).maxHeight).toBe("80vh");
});
