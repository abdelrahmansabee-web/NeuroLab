import { tremorScribbleSpatialGain } from "./overlayMetricEvidence";

test("scribble stays 1:1 and off below the 2 px floor", () => {
  expect(tremorScribbleSpatialGain(0.8)).toBe(0);
  expect(tremorScribbleSpatialGain(1.9)).toBe(0);
  expect(tremorScribbleSpatialGain(2)).toBe(1);
  expect(tremorScribbleSpatialGain(12)).toBe(1);
});
