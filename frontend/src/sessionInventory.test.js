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

  test("Drive recall snapshot counts bytes, not filenames, and names missing pieces", () => {
    const analyzed = patient({
      id: "115",
      name: "Ada",
      pre: { csv_filename: "a.csv", video_filename: "a.mp4", movement_time_sec: 1.2 },
    });
    const filenameOnly = summarizeInventory([analyzed]);
    expect(filenameOnly.ready).toBe(1);
    expect(filenameOnly.fromDrive).toBeFalsy();

    const recall = {
      attempted: true,
      rows: [
        {
          key: "115_Ada",
          id: "115",
          expected: true,
          complete: false,
          missing: ["Clinic PDF", "Pre overlay"],
          pdfOk: false,
          phases: [
            {
              phase: "pre",
              expected: true,
              complete: false,
              hasKin: true,
              hasOriginal: true,
              hasOverlay: false,
              hasUnified: false,
            },
          ],
        },
      ],
    };
    const fromDrive = summarizeInventory([analyzed], recall);
    expect(fromDrive.fromDrive).toBe(true);
    expect(fromDrive.complete).toBe(0);
    expect(fromDrive.incomplete).toBe(1);
    expect(fromDrive.rows[0].bucket).toBe("partial");
    expect(fromDrive.rows[0].missing).toEqual(["Clinic PDF", "Pre overlay"]);
    expect(fromDrive.rows[0].phases[0].hasOriginal).toBe(true);
    expect(fromDrive.rows[0].phases[0].hasOverlay).toBe(false);
    expect(fromDrive.rows[0].phases[0].tone).toBe("partial");
  });

  test("fully recalled Drive session is ready even if JSON video name is missing", () => {
    const p = patient({
      id: "101",
      name: "Ada",
      pre: { csv_filename: "a.csv", movement_time_sec: 1.1 },
    });
    const recall = {
      attempted: true,
      rows: [
        {
          key: "101_Ada",
          id: "101",
          expected: true,
          complete: true,
          missing: [],
          pdfOk: true,
          phases: [
            {
              phase: "pre",
              expected: true,
              complete: true,
              hasKin: true,
              hasOriginal: true,
              hasOverlay: true,
              hasUnified: true,
              wantUnified: true,
            },
          ],
        },
      ],
    };
    const inv = summarizeInventory([p], recall);
    expect(inv.complete).toBe(1);
    expect(inv.rows[0].bucket).toBe("ready");
    expect(inv.rows[0].phases[0].tone).toBe("ready");
    expect(inv.rows[0].phases[0].hasVideo).toBe(true);
  });
});
