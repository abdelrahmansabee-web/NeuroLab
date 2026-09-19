import { isGhostClick, resetGhostClick, swallowGhostClick } from "./uiGhostClick";

afterEach(() => {
  resetGhostClick();
});

test("swallowGhostClick eats the leftover click after an overlay closes", () => {
  const seen = [];
  const onClick = (e) => {
    if (!e.defaultPrevented) seen.push("click");
  };
  document.addEventListener("click", onClick);
  swallowGhostClick(400);
  expect(isGhostClick()).toBe(true);
  document.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true }));
  expect(seen).toEqual([]);
  document.removeEventListener("click", onClick);
});

test("ghost window expires so the next real tap works", () => {
  jest.useFakeTimers();
  swallowGhostClick(50);
  expect(isGhostClick()).toBe(true);
  jest.advanceTimersByTime(60);
  expect(isGhostClick()).toBe(false);
  jest.useRealTimers();
});
