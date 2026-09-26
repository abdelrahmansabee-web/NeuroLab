const fs = require("fs");
const path = require("path");

const css = fs.readFileSync(path.join(__dirname, "index.css"), "utf8");
const app = fs.readFileSync(path.join(__dirname, "App.js"), "utf8");
const overlay = fs.readFileSync(path.join(__dirname, "..", "public", "liquid_glass.css"), "utf8");

test("lab glass does not paint an invented black fill over iPad clinic cards", () => {
  expect(css).not.toMatch(/html\.nl-touch \[data-nl-app-scroll\][^{]*\{[^}]*background-color:\s*rgba\(10,\s*14,\s*22/);
  expect(css).not.toMatch(/html\.nl-touch \[data-nl-app-scroll\][^{]*\{[^}]*background-color:\s*rgba\(16,\s*22,\s*32/);
  expect(app).not.toMatch(/html\.nl-touch \[data-nl-app-scroll\][^{]*\{[^}]*background-color:\s*rgba\(10,\s*14,\s*22/);
  expect(app).not.toMatch(/html\.nl-touch \[data-nl-app-scroll\][^{]*\{[^}]*background-color:\s*rgba\(16,\s*22,\s*32/);
});

test("iPad and touch keep the same liquid glass degree as desktop, not a diluted blur", () => {
  expect(app).toMatch(
    /html\.nl-touch \.content-shell \.content-panel-glass[\s\S]*?backdrop-filter:\s*blur\(24px\) saturate\(2\.85\)/,
  );
  expect(app).not.toMatch(/html\.nl-touch \.content-shell \.content-panel-glass[\s\S]*?backdrop-filter:\s*blur\(6px\)/);
  expect(app).not.toMatch(/html\.nl-touch \.glass-float \{[\s\S]*?blur\(8px\)/);
  expect(css).toMatch(/@supports not \(\(backdrop-filter: blur\(1px\)\) or \(-webkit-backdrop-filter: blur\(1px\)\)\)/);
});

test("clinic chrome uses shared liquid section motion instead of a missing bounce", () => {
  expect(css).toMatch(/@keyframes nl-bounce-in/);
  expect(css).toMatch(/@keyframes nl-bounce-out/);
  expect(app).toMatch(/const BOUNCE_OUT_MS = 420/);
  expect(app).toMatch(/const BOUNCE_IN_MS = 520/);
});

test("analysis film strip and progress use muted glass instead of dark plastic", () => {
  expect(css).toMatch(/\.kin-analyze-track/);
  expect(css).toMatch(/\.kin-analyze-track-fill/);
  expect(css).not.toMatch(/rgba\(8,\s*10,\s*18,\s*0\.82\)/);
  expect(css).toMatch(/\.kin-film-strip__body[\s\S]*?rgba\(255,\s*255,\s*255,\s*0\.028\)/);
});

test("validation video chrome uses muted glass bars and panels", () => {
  expect(css).toMatch(/\.validation-metrics-gutter[\s\S]*?rgba\(255,\s*255,\s*255,\s*0\.028\)/);
  expect(css).toMatch(/\.validation-seek-bar[\s\S]*?border-radius:\s*999px/);
  expect(css).toMatch(/\.validation-seek-fill[\s\S]*?transition:\s*none/);
  expect(css).toMatch(/\.validation-player-controls[\s\S]*?border-radius:\s*24px/);
});

test("three-dot menu is a desktop popover from the button, not only a bottom sheet", () => {
  expect(app).toMatch(/moreMenuBtnRef/);
  expect(app).toMatch(/desktop-more-menu/);
  expect(app).toMatch(/transformOrigin: "top right"/);
  expect(app).toMatch(/desktop-more-menu[\s\S]*?position: "absolute"/);
  expect(app).not.toMatch(/className=\{`rounded-\[28px\] sidebar-shell \$\{SIDEBAR_CLS\}`\}/);
});

test("analysis phase cards use muted glass instead of neon sky/emerald/amber plates", () => {
  expect(app).not.toMatch(/border-t-\[3px\] bg-gradient-to-b \$\{a\.top\}/);
  expect(app).not.toMatch(/from-sky-500\/14/);
  expect(app).toMatch(/KIN_PHASE_PIP/);
  expect(app).toMatch(/rounded-\[28px\] border border-white\/\[0\.06\] bg-white\/\[0\.028\]/);
});

test("clinic buttons use muted glass pills instead of neon sky/emerald plates", () => {
  expect(app).toMatch(/default: "bg-white\/\[0\.06\] border-white\/\[0\.08\] text-white\/85/);
  expect(app).toMatch(/rounded-full border font-semibold text-sm/);
  expect(app).not.toMatch(/sky: "bg-sky-500\/20 border-sky-400\/30/);
});

test("live overlay stylesheet restyles chrome without touching analysis bundles", () => {
  expect(overlay).toMatch(/background-color: rgba\(255, 255, 255, 0\.008\)/);
  expect(overlay).toMatch(/html\.nl-touch \.content-shell \.content-panel-glass/);
  expect(overlay).toMatch(/\.validation-seek-fill[\s\S]*transition:\s*none/);
  expect(overlay).not.toMatch(/analyze_reach|calculate_sparc|nvp_count/);
});

test("clinic chrome keeps original GitHub glass degree, not milky lens brightening", () => {
  expect(app).toMatch(
    /const GLASS_CLS = "bg-white\/\[0\.008\] backdrop-blur-md backdrop-saturate-\[2\.25\] border border-white\/\[0\.03\]"/,
  );
  expect(app).toMatch(/background-color: rgba\(255,255,255,0\.008\)/);
  expect(app).toMatch(/background-color: rgba\(255,255,255,0\.028\)/);
  expect(app).toMatch(/@keyframes nl-liquid-orbit/);
  expect(app).toMatch(/animation: nl-liquid-orbit 28s linear infinite/);
  expect(app).not.toMatch(/nl-liquid-sheen/);
  expect(app).not.toMatch(/linear-gradient\(118deg/);
  expect(app).not.toMatch(/brightness\(1\.08\)/);
  expect(app).not.toMatch(/bg-white\/70/);
  expect(app).toMatch(/\.sidebar-shell \{\s*border-radius: 36px !important;/);
  expect(app).toMatch(/\.app-topbar-glass,\s*\.section-header \{\s*border-radius: 999px !important;/);
});
