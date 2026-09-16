const fs = require("fs");
const path = require("path");

const css = fs.readFileSync(path.join(__dirname, "index.css"), "utf8");
const app = fs.readFileSync(path.join(__dirname, "App.js"), "utf8");

test("iPad clinic scroller lab cards drop backdrop-filter so they cannot stick over a scrolled copy", () => {
  expect(css).toMatch(
    /html\.nl-touch \[data-nl-app-scroll\] \.content-shell[\s\S]*?backdrop-filter:\s*none\s*!important/,
  );
  expect(css).toMatch(
    /html\.nl-touch \[data-nl-app-scroll\] \.content-shell \.content-panel-glass[\s\S]*?backdrop-filter:\s*none\s*!important/,
  );
  expect(app).toMatch(
    /html\.nl-touch \[data-nl-app-scroll\] \.content-shell \.content-panel-glass[\s\S]*?backdrop-filter:\s*none\s*!important/,
  );
  expect(css).not.toMatch(
    /html\.nl-touch \[data-nl-app-scroll\][^{]*\{[^}]*position:\s*fixed/,
  );
});

test("iPad section pane does not keep a translateZ containing block on lab cards", () => {
  expect(css).toMatch(/html\.nl-touch \.section-pane\s*\{[\s\S]*?transform:\s*none/);
});

test("compact overlay chrome stays in-card after the lab-glass scroll fix", () => {
  const { overlayPlayerChromeStyle, overlayCompactIsInCard } = require("./overlayExpandLayout");
  expect(overlayCompactIsInCard(overlayPlayerChromeStyle({ isExpanded: false }))).toBe(true);
});
