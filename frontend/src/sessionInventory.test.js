import { summarizeInventory, summarizePhase, summarizeSession } from "./sessionInventory";

function patient({ id, name, pre, post, baseline, archived } = {}) {
  return {
    _id: id || "x",
    _archived: !!archived,
    demographics: { participantId: id || "101", name: name || "" },
    kinematics: {
      analysisResults: {
        ...(pre ? { pre } : {}),
        ...(post ? { post } : {}),
        ...(baseline ? { baseline } : {}),
      },
    },
  };
}

describe("sessionInventory", () => {
  test("counts ready, incomplete, and missing sessions", () => {
    const inv = summarizeInventory([
      patient({
        id: "101",
        pre: { csv_filename: "a.csv", video_filename: "a.mp4", movement_time_sec: 1.2, peak_velocity_cm_s: 40 },
        post: { csv_filename: "b.csv", video_filename: "b.mp4", movement_time_sec: 1.0, peak_velocity_cm_s: 48 },
      }),
      patient({
        id: "102",
        pre: { csv_filename: "c.csv", movement_time_sec: 2.0 },
      }),
      patient({ id: "103" }),
      patient({ id: "104", archived: true, pre: { csv_filename: "z.csv" } }),
    ]);
    expect(inv.total).toBe(3);
    expect(inv.ready).toBe(1);
    expect(inv.partial).toBe(1);
    expect(inv.empty).toBe(1);
  });

  test("marks a phase ready only when analysis and video are both present", () => {
    const p = patient({
      id: "110",
      pre: { csv_filename: "x.csv", video_filename: "x.mp4", movement_time_sec: 1.5 },
      post: { csv_filename: "y.csv", movement_time_sec: 1.4 },
    });
    expect(summarizePhase(p, "pre").tone).toBe("ready");
    expect(summarizePhase(p, "post").tone).toBe("partial");
    expect(summarizeSession(p).bucket).toBe("partial");
  });
});
