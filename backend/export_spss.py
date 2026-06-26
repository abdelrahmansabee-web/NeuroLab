"""
export_spss.py — Stroke Rehab Kinematic Analysis → SPSS-Ready CSV

Scans backend/outputs/ for all CSV landmark files, runs the phase-based
kinematic analysis on each, and produces a wide-format master CSV with
per-phase metrics for each patient, ready for Repeated Measures ANOVA.

Usage:
  # 1. Scan outputs and show detected patients:
  .\venv\Scripts\python.exe export_spss.py --scan

  # 2. After reviewing, generate the SPSS CSV:
  .\venv\Scripts\python.exe export_spss.py --patients patient_mapping.csv --out spss_kinematics.csv

  Where patient_mapping.csv has columns:
    patient_id, group, pre_file, post_file, baseline_file
  (pre_file etc. are the CSV filenames relative to outputs/ dir)
"""

import os, sys, json, csv, re, traceback
import numpy as np
import pandas as pd

OUTPUTS_DIR = os.path.join(os.path.dirname(__file__), "outputs")
sys.path.insert(0, os.path.dirname(__file__))
from kinematics_analyzer import analyze_reach_and_wipe

# ─── All variables to extract ──────────────────────────────

GLOBAL_VARS = [
    "sparc",
    "trunk_ratio",
    "shoulder_vert_norm",
    "elbow_angle_mean",
    "elbow_angle_min",
    "elbow_angle_max",
    "movement_time_sec",
    "peak_velocity_px_s",
    "peak_velocity_m_s",
    "time_to_peak_velocity_sec",
    "relative_time_to_peak_pct",
    "shoulder_width_px",
    "shoulder_width_cm",
    "metric_scale_m",
    "shoulder_elevation_cm",
    "side_analyzed",
    "fs_hz",
    "active_onset_s",
    "active_offset_s",
    "trunk_displacement_px",
    "palm_displacement_px",
]


def analyze_file(filepath, affected_side="right", metric_scale=0.0):
    """Run analysis and extract all metrics into a flat dict."""
    result = analyze_reach_and_wipe(filepath, affected_side=affected_side, metric_scale=metric_scale)
    if "error" in result:
        raise ValueError(f"Analysis error: {result['error']}")
    return result


def flatten_result(result, phase_prefix):
    row = {}
    for v in GLOBAL_VARS:
        val = result.get(v)
        row[f"{phase_prefix}_{v}"] = val if val is not None else ""
    return row


def scan_outputs():
    """List all CSVs in the outputs directory and detect patient/timepoint."""
    if not os.path.isdir(OUTPUTS_DIR):
        print(f"Outputs directory not found: {OUTPUTS_DIR}")
        return

    # Pattern: {timepoint}_{timestamp}_{patient_id}.csv
    # e.g. pre_20260603_165439_pre.csv, baseline_20260603_165330_baseline.csv
    pattern = re.compile(r"^(pre|post|baseline|during)_(\d{8}_\d{6})_(.+)\.csv$")

    files = sorted(os.listdir(OUTPUTS_DIR))
    patients = {}  # patient_id -> {timepoint: filename}

    print(f"Scanning: {OUTPUTS_DIR}\n")
    print(f"{'Patient ID':<25} {'Pre':<30} {'Post':<30} {'Baseline':<30}")
    print("-" * 115)

    for fname in files:
        if not fname.endswith(".csv"):
            continue
        m = pattern.match(fname)
        if not m:
            # Try without timestamp (older format)
            m2 = re.match(r"^(pre|post|baseline|during)_(.+)\.csv$", fname)
            if m2:
                tp, pid = m2.groups()
            else:
                continue
        else:
            tp, ts, pid = m.groups()

        if pid not in patients:
            patients[pid] = {}
        patients[pid][tp] = fname

    for pid, tps in sorted(patients.items()):
        pre = tps.get("pre", "—")
        post = tps.get("post", "—")
        bl = tps.get("baseline", "—")
        if len(pre) > 28: pre = "…" + pre[-27:]
        if len(post) > 28: post = "…" + post[-27:]
        if len(bl) > 28: bl = "…" + bl[-27:]
        print(f"{pid:<25} {pre:<30} {post:<30} {bl:<30}")

    if not patients:
        print("No matching CSV files found.")
        return

    print(f"\nTotal patients detected: {len(patients)}")
    print("\nTo generate SPSS CSV, create a patient_mapping.csv:")
    print("  patient_id,group,pre_file,post_file,baseline_file")
    print("  (leave column blank if no file for that timepoint)")
    print(f"\nThen run: {sys.argv[0]} --patients patient_mapping.csv --out spss_kinematics.csv")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Export kinematic data for SPSS")
    parser.add_argument("--scan", action="store_true", help="Scan outputs directory")
    parser.add_argument("--patients", type=str, help="Patient mapping CSV file")
    parser.add_argument("--out", type=str, default="spss_kinematics.csv", help="Output CSV path")
    parser.add_argument("--side", type=str, default="right", help="Affected side (right/left/auto)")
    parser.add_argument("--metric-scale", type=float, default=0.0, help="Shoulder width in meters (0=normalized only)")

    args = parser.parse_args()

    if args.scan or not args.patients:
        scan_outputs()
        return

    # Read patient mapping
    mapping = pd.read_csv(args.patients)
    required = ["patient_id", "group"]
    for c in required:
        if c not in mapping.columns:
            print(f"Error: mapping CSV must have '{c}' column")
            return

    print(f"Processing {len(mapping)} patients...")

    all_rows = []
    errors = []

    for idx, row in mapping.iterrows():
        pid = str(row["patient_id"]).strip()
        grp = str(row["group"]).strip()
        if not pid or not grp:
            continue

        patient_row = {"patient_id": pid, "group": grp}

        for tp in ["pre", "post", "baseline", "during"]:
            fcol = f"{tp}_file"
            fname = str(row.get(fcol, "")).strip()
            if not fname or fname.lower() == "nan":
                continue

            fpath = os.path.join(OUTPUTS_DIR, fname)
            if not os.path.exists(fpath):
                errors.append(f"  [{pid}] {fcol}: File not found: {fpath}")
                continue

            print(f"  Analyzing {pid} / {tp} ... ", end="", flush=True)
            try:
                result = analyze_file(fpath, affected_side=args.side, metric_scale=args.metric_scale)
                flat = flatten_result(result, tp)
                patient_row.update(flat)
                # Store filename for reference
                patient_row[f"{tp}_file_used"] = fname
                print(f"OK ({result.get('phases_detected', 0)} phases)")
            except Exception as e:
                errors.append(f"  [{pid}] {tp}: {e}")
                print(f"ERROR: {e}")

        if any(k.startswith(("pre_", "post_", "baseline_")) for k in patient_row if k != "patient_id" and k != "group"):
            all_rows.append(patient_row)

    # Write output
    if all_rows:
        out_df = pd.DataFrame(all_rows)

        # Organize columns: patient_id, group, then pre_*, post_*, baseline_*
        base_cols = ["patient_id", "group"]
        timepoint_cols = []
        for tp in ["pre", "post", "baseline", "during"]:
            for c in sorted(out_df.columns):
                if c.startswith(f"{tp}_") and c not in base_cols:
                    timepoint_cols.append(c)
        # Add file_used columns
        file_cols = [c for c in out_df.columns if c.endswith("_file_used")]
        other_cols = [c for c in out_df.columns if c not in base_cols + timepoint_cols + file_cols]

        ordered = base_cols + timepoint_cols + file_cols + other_cols
        ordered = [c for c in ordered if c in out_df.columns]

        out_df = out_df[ordered]
        out_df.to_csv(args.out, index=False, encoding="utf-8-sig")
        print(f"\n✓ Exported {len(all_rows)} patients to: {args.out}")
        print(f"  Columns: {len(out_df.columns)}")
    else:
        print("No data to export.")

    if errors:
        print(f"\nErrors ({len(errors)}):")
        for e in errors:
            print(e)


if __name__ == "__main__":
    main()
