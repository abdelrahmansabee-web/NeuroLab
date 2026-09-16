import {
  overlayPortalStyle,
  overlayPlayerChromeStyle,
  overlayCompactIsInCard,
  overlaySlotAspect,
  overlaySlotReserveStyle,
  readSlotBox,
  captureContainingBlockStyles,
  restoreContainingBlockStyles,
  lockOverlayAppScroller,
  unlockOverlayAppScroller,
  OVERLAY_PORTAL_Z_COMPACT,
  OVERLAY_PORTAL_Z_EXPANDED,
  OVERLAY_APP_SCROLL_EXPANDED_Z,
} from "./overlayExpandLayout";

test("expanded chrome covers the viewport without using the card slot", () => {
  const style = overlayPlayerChromeStyle({ isExpanded: true });
  expect(style.position).toBe("fixed");
  expect(style.top).toBe(0);
  expect(style.left).toBe(0);
  expect(style.right).toBe(0);
  expect(style.bottom).toBe(0);
  expect(style.zIndex).toBe(OVERLAY_PORTAL_Z_EXPANDED);
});

test("compact chrome stays in-flow so iPad scroll keeps the video in its card", () => {
  const style = overlayPlayerChromeStyle({ isExpanded: false });
  expect(style.position).toBe("absolute");
  expect(style.inset).toBe(0);
  expect(style.width).toBe("100%");
  expect(style.height).toBe("100%");
  expect(style.zIndex).toBe(OVERLAY_PORTAL_Z_COMPACT);
  expect(style.left).toBeUndefined();
  expect(style.top).toBeUndefined();
  expect(overlayCompactIsInCard(style)).toBe(true);
  expect(
    overlayCompactIsInCard({
      position: "fixed",
      left: 24,
      top: 120,
      width: 400,
      height: 225,
      zIndex: 35,
    }),
  ).toBe(false);
});

test("expanded iPad scroller stacks above the clinic sidebar", () => {
  expect(OVERLAY_APP_SCROLL_EXPANDED_Z).toBeGreaterThan(100);
});

test("expand locks the clinic app scroller the same way the actions sheet does", () => {
  const scroller = document.createElement("div");
  scroller.setAttribute("data-nl-app-scroll", "1");
  scroller.style.overflow = "auto";
  document.body.appendChild(scroller);
  const saved = lockOverlayAppScroller();
  expect(scroller.style.overflow).toBe("hidden");
  expect(scroller.style.touchAction).toBe("none");
  unlockOverlayAppScroller(saved);
  expect(scroller.style.overflow).toBe("auto");
  expect(scroller.style.touchAction).toBe("");
  document.body.removeChild(scroller);
});

test("expand CSS raises the scroller and main above the sticky top bar without hiding it", () => {
  const fs = require("fs");
  const path = require("path");
  const css = fs.readFileSync(path.join(__dirname, "index.css"), "utf8");
  expect(css).toMatch(/html\.nl-overlay-expanded \[data-nl-app-scroll\]/);
  expect(css).toMatch(/html\.nl-overlay-expanded main\s*\{[\s\S]*?z-index:\s*80/);
  expect(css).not.toMatch(/html\.nl-overlay-expanded \.nl-clinic-shell-topbar/);
  expect(css).not.toMatch(/html\.nl-overlay-expanded \.nl-clinic-main/);
});

test("legacy overlayPortalStyle compact no longer pins a fixed slot", () => {
  const style = overlayPortalStyle({
    isExpanded: false,
    slot: { left: 24, top: 120, width: 400, height: 225 },
  });
  expect(style.position).toBe("absolute");
  expect(style.width).toBe("100%");
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

test("containing-block unlock beats stylesheet !important without touching overflow", () => {
  const styleEl = document.createElement("style");
  styleEl.textContent = ".glass-float { backdrop-filter: blur(12px) saturate(2.25) !important; overflow: auto; }";
  document.head.appendChild(styleEl);
  const scroller = document.createElement("div");
  scroller.style.overflow = "auto";
  scroller.style.overflowY = "auto";
  const parent = document.createElement("div");
  parent.className = "glass-float";
  parent.style.overflow = "hidden";
  const child = document.createElement("div");
  parent.appendChild(child);
  scroller.appendChild(parent);
  document.body.appendChild(scroller);

  const saved = captureContainingBlockStyles(child);
  expect(parent.style.overflow).toBe("hidden");
  expect(scroller.style.overflow).toBe("auto");
  expect(scroller.style.overflowY).toBe("auto");
  expect(parent.style.getPropertyPriority("transform")).toBe("important");
  expect(parent.style.getPropertyValue("transform")).toBe("none");
  expect(parent.style.getPropertyValue("filter")).toBe("none");
  expect(parent.classList.contains("nl-overlay-escape")).toBe(true);

  restoreContainingBlockStyles(saved);
  expect(parent.style.overflow).toBe("hidden");
  expect(parent.classList.contains("nl-overlay-escape")).toBe(false);
  expect(parent.style.getPropertyValue("backdrop-filter")).toBe("");
  document.body.removeChild(scroller);
  document.head.removeChild(styleEl);
});

test("compact overlay tools wrap instead of painting labels over icons", () => {
  const fs = require("fs");
  const path = require("path");
  const css = fs.readFileSync(path.join(__dirname, "index.css"), "utf8");
  expect(css).toMatch(/\.validation-controls-tools\s*\{[^}]*flex-wrap:\s*wrap/s);
  expect(css).not.toMatch(/\.validation-controls-tools\s*\{[^}]*flex-wrap:\s*nowrap/s);
  expect(css).toMatch(/container-name:\s*overlay-controls/);
  expect(css).toMatch(/@container overlay-controls/);
  expect(css).toMatch(/\.validation-control-icon\.is-active/);
  expect(css).toMatch(/\.validation-control-icon\.is-table-place/);
});
