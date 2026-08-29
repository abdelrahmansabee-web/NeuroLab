"""Compute joint angles from TRC markers -> .mot file for OpenSim."""

import os, sys
import numpy as np
from pathlib import Path

os.environ["OPENSIM_HOME"] = r"D:\Thesis app\participants\mediapipe\OpenSim 4.5"
import opensim


def compute_angle(p_center, p_joint, p_end):
    """Compute joint angle (radians) at p_joint between vectors p_joint->p_center and p_joint->p_end."""
    v1 = p_center - p_joint
    v2 = p_end - p_joint
    dot = np.dot(v1, v2)
    norm = np.linalg.norm(v1) * np.linalg.norm(v2)
    if norm < 1e-10:
        return 0.0
    cos_a = np.clip(dot / norm, -1, 1)
    return np.arccos(cos_a)


def read_trc(trc_path):
    with open(trc_path) as f:
        lines = f.readlines()
    header = lines[3].strip().split("\t")
    marker_names = header[2:][0::3]
    start = 5 if len(lines) > 5 and not lines[4].startswith("Frame") else 4
    data = []
    times = []
    for line in lines[start:]:
        parts = line.strip().split("\t")
        if len(parts) < 4:
            continue
        times.append(float(parts[1]))
        vals = np.array([float(x) for x in parts[2:]]).reshape(-1, 3)
        data.append(vals)
    return np.array(data), marker_names, times


def write_mot(output_path, times, coord_names, coord_data, fps=30.0):
    n_rows = len(times)
    n_coords = len(coord_names)
    with open(output_path, "w") as f:
        f.write(f"PathFileType\t4\t(X/Y/Z)\t{os.path.basename(output_path)}\n")
        f.write("DataRate\tCameraRate\tNumFrames\tNumCoordinates\tUnits\n")
        f.write(f"{fps:.1f}\t{fps:.1f}\t{n_rows}\t{n_coords}\trad\n")
        f.write("Frame#\tTime\t" + "\t".join(coord_names) + "\n")
        for i in range(n_rows):
            f.write(f"{i+1}\t{times[i]:.5f}\t")
            f.write("\t".join([f"{v:.6f}" for v in coord_data[i]]) + "\n")
    print(f"  .mot saved: {output_path}")


def trc_to_mot(trc_path, output_mot_path, model_path):
    """Convert TRC marker data to .mot coordinate data using OpenSim model constraints."""

    data, marker_names, times = read_trc(trc_path)
    n_frames = len(data)
    fps = 30.0

    # Build index map: marker name -> column
    name_to_idx = {m: i for i, m in enumerate(marker_names)}

    # Compute joint angles for each frame
    coord_names = [
        "ground_pelvis_rotation_z", "ground_pelvis_rotation_x", "ground_pelvis_rotation_y",
        "ground_pelvis_translation_z", "ground_pelvis_translation_y", "ground_pelvis_translation_x",
        "l_upper_arm_flexion", "r_upper_arm_flexion",
        "l_forearm_flexion", "r_forearm_flexion",
        "l_thigh_flexion", "r_thigh_flexion",
        "l_shank_flexion", "r_shank_flexion",
    ]

    get = lambda name: data[:, name_to_idx[name]] if name in name_to_idx else np.full((n_frames, 3), np.nan)

    LS = get("LEFT_SHOULDER"); RS = get("RIGHT_SHOULDER")
    LE = get("LEFT_ELBOW");    RE = get("RIGHT_ELBOW")
    LW = get("LEFT_WRIST");    RW = get("RIGHT_WRIST")
    LH = get("LEFT_HIP");      RH = get("RIGHT_HIP")
    LK = get("LEFT_KNEE");     RK = get("RIGHT_KNEE")
    LA = get("LEFT_ANKLE");    RA = get("RIGHT_ANKLE")

    coord_data = []
    for i in range(n_frames):
        if np.any(np.isnan(LS[i])): LS[i] = [0,0,0]
        if np.any(np.isnan(RS[i])): RS[i] = [0,0,0]
        if np.any(np.isnan(LE[i])): LE[i] = [0,0,0]
        if np.any(np.isnan(RE[i])): RE[i] = [0,0,0]
        if np.any(np.isnan(LW[i])): LW[i] = [0,0,0]
        if np.any(np.isnan(RW[i])): RW[i] = [0,0,0]
        if np.any(np.isnan(LH[i])): LH[i] = [0,0,0]
        if np.any(np.isnan(RH[i])): RH[i] = [0,0,0]
        if np.any(np.isnan(LK[i])): LK[i] = [0,0,0]
        if np.any(np.isnan(RK[i])): RK[i] = [0,0,0]
        if np.any(np.isnan(LA[i])): LA[i] = [0,0,0]
        if np.any(np.isnan(RA[i])): RA[i] = [0,0,0]

        mid_hip = (LS[i] + RS[i]) / 2.0  # rough torso base
        mid_shoulder = (LS[i] + RS[i]) / 2.0

        # Pelvis position: mid-hip
        pelvis_x = float((LH[i][0] + RH[i][0]) / 2.0)
        pelvis_y = float((LH[i][1] + RH[i][1]) / 2.0)
        pelvis_z = float((LH[i][2] + RH[i][2]) / 2.0)

        # Simple rotation estimate from shoulder-hip vector
        spine = mid_shoulder - mid_hip

        # Joint angles (using simple 2D approximation for PinJoints)
        l_elbow = compute_angle(LS[i], LE[i], LW[i])
        r_elbow = compute_angle(RS[i], RE[i], RW[i])
        l_knee = compute_angle(LH[i], LK[i], LA[i])
        r_knee = compute_angle(RH[i], RK[i], RA[i])

        # Shoulder / hip "flexion" (simplified: angle from vertical)
        l_shoulder_angle = compute_angle(mid_shoulder, LS[i], LE[i])
        r_shoulder_angle = compute_angle(mid_shoulder, RS[i], RE[i])
        l_hip_angle = compute_angle(mid_hip, LH[i], LK[i])
        r_hip_angle = compute_angle(mid_hip, RH[i], RK[i])

        # Pelvis rotation / translation as FreeJoint coords
        # rotation_z, rotation_x, rotation_y, translation_z, translation_y, translation_x
        pelvis_rot_z = 0.0
        pelvis_rot_x = 0.0
        pelvis_rot_y = 0.0

        row = [
            pelvis_rot_z, pelvis_rot_x, pelvis_rot_y,
            pelvis_z, pelvis_y, pelvis_x,
            l_shoulder_angle, r_shoulder_angle,
            l_elbow, r_elbow,
            l_hip_angle, r_hip_angle,
            l_knee, r_knee,
        ]
        coord_data.append(row)

    write_mot(output_mot_path, times, coord_names, coord_data, fps)


if __name__ == "__main__":
    base = Path(__file__).resolve().parent / "outputs"
    target = None
    for c in sorted(base.glob("*.trc")):
        if "baseline_20260604" in c.name and "205320" in c.name:
            target = c
            break
    if not target:
        trcs = sorted(base.glob("*.trc"))
        if trcs:
            target = trcs[0]
    if target:
        osim_path = target.with_suffix(".osim")
        mot_path = target.with_suffix(".mot")
        trc_to_mot(str(target), str(mot_path), str(osim_path))
        # Copy to Desktop
        import shutil
        shutil.copy(str(mot_path), str(Path.home() / "Desktop" / "pose.mot"))
        print(f"\nCopied to Desktop as pose.mot")
    else:
        print("No TRC found")
