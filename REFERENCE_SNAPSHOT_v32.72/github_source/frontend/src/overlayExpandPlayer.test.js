import React from "react";
import { render, fireEvent } from "@testing-library/react";
import { ValidationOverlayPlayer } from "./ValidationOverlayPlayer";

const overlayData = {
  frames: [
    {
      time: 0,
      palm: [0.52, 0.48],
      wrist: [0.5, 0.5],
      elbow: [0.42, 0.58],
      shoulder: [0.32, 0.36],
      lshoulder: [0.22, 0.36],
      rshoulder: [0.32, 0.36],
      trunk: [0.28, 0.34],
      speed: 0,
    },
  ],
  fps: 30,
  metrics: {},
  movement_window: { start_idx: 0, end_idx: 0 },
  frame_width_px: 1280,
  frame_height_px: 720,
};

test("expand keeps the same in-card video node", () => {
  window.matchMedia = (query) => ({
    matches: false,
    media: query,
    addEventListener() {},
    removeEventListener() {},
    addListener() {},
    removeListener() {},
  });
  window.ResizeObserver = class {
    observe() {}
    disconnect() {}
    unobserve() {}
  };

  HTMLCanvasElement.prototype.getContext = () => ({
    clearRect() {},
    fillRect() {},
    strokeRect() {},
    beginPath() {},
    moveTo() {},
    lineTo() {},
    quadraticCurveTo() {},
    bezierCurveTo() {},
    arc() {},
    closePath() {},
    stroke() {},
    fill() {},
    save() {},
    restore() {},
    translate() {},
    scale() {},
    setLineDash() {},
    drawImage() {},
    measureText: () => ({ width: 10 }),
    createLinearGradient: () => ({ addColorStop() {} }),
    createRadialGradient: () => ({ addColorStop() {} }),
  });

  const { container, getByTitle } = render(
    <ValidationOverlayPlayer videoUrl="blob:test-overlay" overlayData={overlayData} phaseLabel="Post" />,
  );

  const home = container.querySelector(".validation-player-home");
  expect(home).toBeTruthy();
  const video = home.querySelector("video");
  expect(video).toBeTruthy();
  expect(video.getAttribute("src")).toBe("blob:test-overlay");
  expect(document.body.querySelector("video")).toBe(video);
  expect(home.contains(video)).toBe(true);

  fireEvent.scroll(window);
  expect(home.querySelector("video")).toBe(video);
  expect(home.contains(video)).toBe(true);

  fireEvent.pointerDown(getByTitle("Fullscreen"));

  expect(home.querySelector(".validation-player-fullscreen")).toBeTruthy();
  expect(getByTitle("Exit fullscreen")).toBeTruthy();
  expect(home.querySelector("video")).toBe(video);
  expect(document.documentElement.classList.contains("nl-overlay-expanded")).toBe(true);

  fireEvent.pointerDown(getByTitle("Exit fullscreen"));
  expect(home.querySelector(".validation-player-fullscreen")).toBeNull();
  expect(home.querySelector("video")).toBe(video);
  expect(document.documentElement.classList.contains("nl-overlay-expanded")).toBe(false);
});
