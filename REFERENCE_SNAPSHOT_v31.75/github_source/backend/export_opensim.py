"""Generate an OpenSim .osim model + corrected TRC from a pose CSV."""

import csv
import os
import math
import numpy as np
from pathlib import Path

# MediaPipe landmark indices
LM = {
    "NOSE": 0, "LEFT_EYE_INNER": 1, "LEFT_EYE": 2, "LEFT_EYE_OUTER": 3,
    "RIGHT_EYE_INNER": 4, "RIGHT_EYE": 5, "RIGHT_EYE_OUTER": 6,
    "LEFT_EAR": 7, "RIGHT_EAR": 8,
    "MOUTH_LEFT": 9, "MOUTH_RIGHT": 10,
    "LEFT_SHOULDER": 11, "RIGHT_SHOULDER": 12,
    "LEFT_ELBOW": 13, "RIGHT_ELBOW": 14,
    "LEFT_WRIST": 15, "RIGHT_WRIST": 16,
    "LEFT_PINKY": 17, "RIGHT_PINKY": 18,
    "LEFT_INDEX": 19, "RIGHT_INDEX": 20,
    "LEFT_THUMB": 21, "RIGHT_THUMB": 22,
    "LEFT_HIP": 23, "RIGHT_HIP": 24,
    "LEFT_KNEE": 25, "RIGHT_KNEE": 26,
    "LEFT_ANKLE": 27, "RIGHT_ANKLE": 28,
    "LEFT_HEEL": 29, "RIGHT_HEEL": 30,
    "LEFT_FOOT_INDEX": 31, "RIGHT_FOOT_INDEX": 32,
}

LANDMARK_NAMES = {v: k for k, v in LM.items()}


def read_first_frame(csv_path):
    with open(csv_path, newline="") as f:
        reader = csv.reader(f)
        header = next(reader)
        first_row = next(reader)

    pts = {}
    for name, idx in LM.items():
        x_col = header.index(f"{name}_X")
        y_col = header.index(f"{name}_Y")
        z_col = header.index(f"{name}_Z")
        try:
            pts[name] = np.array([
                float(first_row[x_col]),
                float(first_row[y_col]),
                float(first_row[z_col]),
            ])
        except (ValueError, IndexError):
            pts[name] = np.array([0.0, 0.0, 0.0])
    return pts


def midpoint(p1, p2):
    return (p1 + p2) / 2.0


def vec(p1, p2):
    return p2 - p1


def norm(v):
    return np.linalg.norm(v)


def unit(v):
    n = norm(v)
    return v / n if n > 0 else np.array([0.0, 0.0, 0.0])


def body_in_ground(pts, name):
    """Return the position of a landmark in ground coordinates."""
    return pts[name]


def xml_escape(s):
    return str(s)


def write_osim(osim_path, pts, mass_kg=70.0, height_m=1.70):
    """Write a minimal OpenSim model with 33 MediaPipe markers."""

    # Estimate anthropometry
    shoulder_width = norm(vec(pts["LEFT_SHOULDER"], pts["RIGHT_SHOULDER"]))
    hip_width = norm(vec(pts["LEFT_HIP"], pts["RIGHT_HIP"]))
    torso_len = norm(vec(midpoint(pts["LEFT_HIP"], pts["RIGHT_HIP"]),
                         midpoint(pts["LEFT_SHOULDER"], pts["RIGHT_SHOULDER"])))
    upper_arm_len = (norm(vec(pts["LEFT_SHOULDER"], pts["LEFT_ELBOW"])) +
                     norm(vec(pts["RIGHT_SHOULDER"], pts["RIGHT_ELBOW"]))) / 2.0
    forearm_len = (norm(vec(pts["LEFT_ELBOW"], pts["LEFT_WRIST"])) +
                   norm(vec(pts["RIGHT_ELBOW"], pts["RIGHT_WRIST"]))) / 2.0
    thigh_len = (norm(vec(pts["LEFT_HIP"], pts["LEFT_KNEE"])) +
                 norm(vec(pts["RIGHT_HIP"], pts["RIGHT_KNEE"]))) / 2.0
    shank_len = (norm(vec(pts["LEFT_KNEE"], pts["LEFT_ANKLE"])) +
                 norm(vec(pts["RIGHT_KNEE"], pts["RIGHT_ANKLE"]))) / 2.0

    # Segment masses (Dempster proportions)
    m_pelvis = mass_kg * 0.142
    m_torso = mass_kg * 0.355
    m_head = mass_kg * 0.081
    m_upper_arm = mass_kg * 0.028
    m_forearm = mass_kg * 0.016
    m_thigh = mass_kg * 0.100
    m_shank = mass_kg * 0.0465
    m_foot = mass_kg * 0.0145

    # Mid-hip = pelvis origin (in ground)
    mid_hip = midpoint(pts["LEFT_HIP"], pts["RIGHT_HIP"])
    mid_shoulder = midpoint(pts["LEFT_SHOULDER"], pts["RIGHT_SHOULDER"])

    lines = []
    def L(s):
        lines.append(s)

    L('<?xml version="1.0" encoding="UTF-8"?>')
    L('<OpenSimDocument Version="40000">')
    L('  <Model name="MediaPipePose">')
    L('    <!-- Ground body (required) -->')
    L('    <ground>')
    L('      <body name="ground">')
    L('        <mass>0</mass>')
    L('        <mass_center>0 0 0</mass_center>')
    L('        <inertia>0 0 0 0 0 0</inertia>')
    L('      </body>')
    L('    </ground>')

    # Define bodies
    bodies = {}

    # Body definitions: name, mass, com_offset, inertia_xx, scale
    body_defs = [
        ("pelvis", m_pelvis, [0, 0, 0], 0.1, hip_width),
        ("torso", m_torso, [0, torso_len * 0.4, 0], 0.15, shoulder_width),
        ("head", m_head, [0, 0.05, 0], 0.08, 0.15),
        ("l_upper_arm", m_upper_arm, [0, -upper_arm_len * 0.5, 0], 0.03, 0.08),
        ("r_upper_arm", m_upper_arm, [0, -upper_arm_len * 0.5, 0], 0.03, 0.08),
        ("l_forearm", m_forearm, [0, -forearm_len * 0.5, 0], 0.02, 0.06),
        ("r_forearm", m_forearm, [0, -forearm_len * 0.5, 0], 0.02, 0.06),
        ("l_thigh", m_thigh, [0, -thigh_len * 0.4, 0], 0.06, 0.12),
        ("r_thigh", m_thigh, [0, -thigh_len * 0.4, 0], 0.06, 0.12),
        ("l_shank", m_shank, [0, -shank_len * 0.4, 0], 0.04, 0.08),
        ("r_shank", m_shank, [0, -shank_len * 0.4, 0], 0.04, 0.08),
        ("l_foot", m_foot, [0.05, 0, 0], 0.01, 0.03),
        ("r_foot", m_foot, [0.05, 0, 0], 0.01, 0.03),
    ]

    L('')
    L('    <BodySet>')
    L('      <objects>')
    for bname, bmass, com, inertia_scale, width in body_defs:
        ix = inertia_scale
        loc = f"{com[0]:.4f} {com[1]:.4f} {com[2]:.4f}"
        L(f'        <Body name="{bname}">')
        L(f'          <mass>{bmass:.4f}</mass>')
        L(f'          <mass_center>{loc}</mass_center>')
        L(f'          <inertia>{ix:.4f} {ix:.4f} {ix:.4f} 0 0 0</inertia>')
        L(f'        </Body>')
        bodies[bname] = True
    L('      </objects>')
    L('      <groups/>')
    L('    </BodySet>')

    # Joints
    L('')
    L('    <JointSet>')
    L('      <objects>')

    # Pelvis to ground (free joint)
    pelvis_loc = f"{mid_hip[0]:.6f} {mid_hip[1]:.6f} {mid_hip[2]:.6f}"
    L('        <FreeJoint name="ground_pelvis">')
    L('          <parent_body>ground</parent_body>')
    L('          <location_in_parent>0 0 0</location_in_parent>')
    L('          <orientation_in_parent>0 0 0</orientation_in_parent>')
    L(f'          <location>{pelvis_loc}</location>')
    L('          <orientation>0 0 0</orientation>')
    L('        </FreeJoint>')

    def weld(parent, child, loc_in_parent, ori="0 0 0", loc="0 0 0"):
        L(f'        <WeldJoint name="{parent}_{child}">')
        L(f'          <parent_body>{parent}</parent_body>')
        L(f'          <location_in_parent>{loc_in_parent}</location_in_parent>')
        L(f'          <orientation_in_parent>{ori}</orientation_in_parent>')
        L(f'          <location>{loc}</location>')
        L(f'          <orientation>{ori}</orientation>')
        L(f'        </WeldJoint>')

    # Torso on pelvis
    pelvis_torso_loc = f"0 {norm(vec(mid_hip, mid_shoulder)) * 0.5:.4f} 0"
    weld("pelvis", "torso", pelvis_torso_loc)

    # Head on torso
    weld("torso", "head", f"0 {torso_len * 0.5:.4f} 0")

    # Left arm on torso
    l_shoulder_offset = f"{-shoulder_width * 0.35:.4f} {torso_len * 0.5:.4f} 0"
    weld("torso", "l_upper_arm", l_shoulder_offset)
    weld("l_upper_arm", "l_forearm", f"0 {-upper_arm_len:.4f} 0")

    # Right arm on torso
    r_shoulder_offset = f"{shoulder_width * 0.35:.4f} {torso_len * 0.5:.4f} 0"
    weld("torso", "r_upper_arm", r_shoulder_offset)
    weld("r_upper_arm", "r_forearm", f"0 {-upper_arm_len:.4f} 0")

    # Legs on pelvis
    l_hip_offset = f"{-hip_width * 0.25:.4f} 0 0"
    r_hip_offset = f"{hip_width * 0.25:.4f} 0 0"
    weld("pelvis", "l_thigh", l_hip_offset)
    weld("pelvis", "r_thigh", r_hip_offset)
    weld("l_thigh", "l_shank", f"0 {-thigh_len:.4f} 0")
    weld("r_thigh", "r_shank", f"0 {-thigh_len:.4f} 0")
    weld("l_shank", "l_foot", f"0 {-shank_len:.4f} 0")
    weld("r_shank", "r_foot", f"0 {-shank_len:.4f} 0")

    L('      </objects>')
    L('      <groups/>')
    L('    </JointSet>')

    # Markers
    L('')
    L('    <MarkerSet>')
    L('      <objects>')

    # Map each landmark to a body and location in body frame
    marker_map = [
        ("NOSE", "head", [0, 0.1, 0]),
        ("LEFT_EYE_INNER", "head", [-0.02, 0.1, 0.02]),
        ("LEFT_EYE", "head", [-0.03, 0.1, 0.02]),
        ("LEFT_EYE_OUTER", "head", [-0.04, 0.1, 0.02]),
        ("RIGHT_EYE_INNER", "head", [0.02, 0.1, 0.02]),
        ("RIGHT_EYE", "head", [0.03, 0.1, 0.02]),
        ("RIGHT_EYE_OUTER", "head", [0.04, 0.1, 0.02]),
        ("LEFT_EAR", "head", [-0.08, 0.08, 0]),
        ("RIGHT_EAR", "head", [0.08, 0.08, 0]),
        ("MOUTH_LEFT", "head", [-0.03, 0.07, 0.02]),
        ("MOUTH_RIGHT", "head", [0.03, 0.07, 0.02]),
        ("LEFT_SHOULDER", "torso", [-shoulder_width * 0.4, torso_len * 0.5, 0]),
        ("RIGHT_SHOULDER", "torso", [shoulder_width * 0.4, torso_len * 0.5, 0]),
        ("LEFT_ELBOW", "l_upper_arm", [0, -upper_arm_len, 0]),
        ("RIGHT_ELBOW", "r_upper_arm", [0, -upper_arm_len, 0]),
        ("LEFT_WRIST", "l_forearm", [0, -forearm_len, 0]),
        ("RIGHT_WRIST", "r_forearm", [0, -forearm_len, 0]),
        ("LEFT_PINKY", "l_forearm", [0, -forearm_len, -0.02]),
        ("RIGHT_PINKY", "r_forearm", [0, -forearm_len, 0.02]),
        ("LEFT_INDEX", "l_forearm", [0, -forearm_len, 0.01]),
        ("RIGHT_INDEX", "r_forearm", [0, -forearm_len, -0.01]),
        ("LEFT_THUMB", "l_forearm", [0, -forearm_len * 0.9, -0.03]),
        ("RIGHT_THUMB", "r_forearm", [0, -forearm_len * 0.9, 0.03]),
        ("LEFT_HIP", "pelvis", [-hip_width * 0.3, 0, 0]),
        ("RIGHT_HIP", "pelvis", [hip_width * 0.3, 0, 0]),
        ("LEFT_KNEE", "l_thigh", [0, -thigh_len, 0]),
        ("RIGHT_KNEE", "r_thigh", [0, -thigh_len, 0]),
        ("LEFT_ANKLE", "l_shank", [0, -shank_len, 0]),
        ("RIGHT_ANKLE", "r_shank", [0, -shank_len, 0]),
        ("LEFT_HEEL", "l_foot", [-0.02, 0, 0]),
        ("RIGHT_HEEL", "r_foot", [0.02, 0, 0]),
        ("LEFT_FOOT_INDEX", "l_foot", [0.1, 0, 0]),
        ("RIGHT_FOOT_INDEX", "r_foot", [0.1, 0, 0]),
    ]

    for mname, body_name, loc in marker_map:
        loc_str = f"{loc[0]:.4f} {loc[1]:.4f} {loc[2]:.4f}"
        L(f'        <Marker name="{mname}">')
        L(f'          <body>{body_name}</body>')
        L(f'          <location>{loc_str}</location>')
        L(f'          <fixed>false</fixed>')
        L(f'        </Marker>')

    L('      </objects>')
    L('      <groups/>')
    L('    </MarkerSet>')

    # ForceSet (empty)
    L('')
    L('    <ForceSet>')
    L('      <objects/>')
    L('      <groups/>')
    L('    </ForceSet>')

    L('  </Model>')
    L('</OpenSimDocument>')

    with open(osim_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"  .osim written: {osim_path}")


def fix_trc(csv_path, old_trc_path, new_trc_path):
    """Regenerate TRC with proper marker names from the CSV."""
    # Read CSV header for column order
    with open(csv_path, newline="") as f:
        reader = csv.reader(f)
        header = next(reader)
        cols = header[2:]  # skip frame,time

    n_markers = 33
    marker_names = [cols[i].replace("_X", "") for i in range(0, len(cols), 3)]
    assert len(marker_names) == n_markers, f"Expected {n_markers} markers, got {len(marker_names)}"

    # Read data from old TRC
    with open(old_trc_path) as f:
        trc_lines = f.readlines()

    # Parse old TRC
    old_header = trc_lines[3].strip().split("\t")
    data_start = 5 if len(trc_lines) > 5 and not trc_lines[4].startswith("Frame") else 4

    fps_line = trc_lines[2].strip().split("\t")
    fps = float(fps_line[0])

    frames = []
    for line in trc_lines[data_start:]:
        parts = line.strip().split("\t")
        if len(parts) < 4:
            continue
        frame_num = int(parts[0])
        time_val = float(parts[1])
        values = [float(x) if x != "0" else 0.0 for x in parts[2:]]
        frames.append((frame_num, time_val, values))

    n_frames = len(frames)
    # Write new TRC with OpenSim-compatible header (8 fields on line 2, 2-line column header)
    with open(new_trc_path, "w") as f:
        f.write(f"PathFileType\t4\t(X/Y/Z)\t{os.path.basename(new_trc_path)}\n")
        f.write("DataRate\tCameraRate\tNumFrames\tNumMarkers\tUnits\tOrigDataRate\tOrigDataStartFrame\tOrigNumFrames\n")
        f.write(f"{fps}\t{fps}\t{n_frames}\t{n_markers}\tm\t{fps}\t1\t{n_frames}\n")
        f.write("Frame#\tTime\t" + "\t".join(marker_names) + "\n")
        f.write("\t\t" + "\t".join([f"X{i+1}\tY{i+1}\tZ{i+1}" for i in range(n_markers)]) + "\n")
        for frame_num, time_val, values in frames:
            line = f"{frame_num}\t{time_val:.5f}\t"
            line += "\t".join([f"{v:.5f}" for v in values])
            f.write(line + "\n")

    print(f"  TRC fixed: {new_trc_path}")


def process_one(csv_path):
    """Generate .osim + fix TRC for one CSV."""
    csv_path = Path(csv_path)
    base = csv_path.stem
    out_dir = csv_path.parent

    osim_path = out_dir / f"{base}.osim"
    trc_old = out_dir / f"{base}.trc"
    trc_fixed = out_dir / f"{base}.trc"  # overwrite in place

    pts = read_first_frame(str(csv_path))
    write_osim(str(osim_path), pts)

    if trc_old.exists():
        fix_trc(str(csv_path), str(trc_old), str(trc_fixed))
    else:
        print(f"  No TRC found for {base}, skipping TRC fix")


def process_all(output_dir="outputs"):
    """Process every CSV in the output directory."""
    out = Path(__file__).resolve().parent / output_dir
    csvs = sorted(out.glob("*.csv"))
    if not csvs:
        print(f"No CSVs found in {out}")
        return
    for csv_path in csvs:
        base = csv_path.stem
        if base == "test_mp_buffer":
            continue
        print(f"Processing: {base}")
        try:
            process_one(str(csv_path))
        except Exception as e:
            print(f"  ERROR: {e}")


if __name__ == "__main__":
    process_all()
