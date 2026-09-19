/** Swallow the leftover click after an overlay unmounts on pointerdown. */

const LISTENERS = ["pointerup", "mouseup", "click"];

let until = 0;
let armed = false;

function onCapture(event) {
  if (Date.now() >= until) {
    disarmGhostClick();
    return;
  }
  event.preventDefault();
  event.stopPropagation();
}

function disarmGhostClick() {
  if (!armed || typeof document === "undefined") {
    armed = false;
    until = 0;
    return;
  }
  armed = false;
  until = 0;
  LISTENERS.forEach((type) => {
    document.removeEventListener(type, onCapture, true);
  });
}

/** Eat the same-gesture click that would hit whatever is now under the cursor. */
export function swallowGhostClick(ms = 450) {
  const hold = Number(ms);
  until = Date.now() + (Number.isFinite(hold) && hold > 0 ? hold : 450);
  if (armed || typeof document === "undefined") return;
  armed = true;
  LISTENERS.forEach((type) => {
    document.addEventListener(type, onCapture, true);
  });
}

export function isGhostClick() {
  if (Date.now() >= until) {
    if (armed) disarmGhostClick();
    return false;
  }
  return true;
}

export function resetGhostClick() {
  disarmGhostClick();
}
