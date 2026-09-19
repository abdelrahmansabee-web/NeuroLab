"""Build a proper OpenSim model from CSV landmarks, run IK with TRC, and
save an .osim + .mot that the user can load in the OpenSim GUI."""

import os
import sys
import re
import subprocess
import numpy as np
import csv
from pathlib import Path
import shutil

from scipy.ndimage import uniform_filter1d

import opensim


LM = {
    "NOSE": 0, "LEFT_EYE_INNER": 1, "LEFT_EYE": 2, "LEFT_EYE_OUTER": 3,
    "RIGHT_EYE_INNER": 4, "RIGHT_EYE": 5, "RIGHT_EYE_OUTER": 6,
    "LEFT_EAR": 7, "RIGHT_EAR": 8, "MOUTH_LEFT": 9, "MOUTH_RIGHT": 10,
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

# Path to OpenSim 4.5 opensim-cmd
OPENSIM_CMD = r"D:\Thesis app\participants\mediapipe\OpenSim 4.5\bin\opensim-cmd.exe"


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


# ── TRC fix (ensure 2-line column header) ─────────────────────────────────

def fix_trc_format(path):
    with open(path) as f:
        lines = f.readlines()
    if len(lines) < 5:
        return
    # Check if line 5 (index 4) starts with X1 or tab (meaning 2-line header exists)
    line5 = lines[4].strip()
    if line5.startswith("X1") or line5.startswith("\tX1"):
        return  # already has 2-line header

    # Extract marker names from the single combined header line
    header = lines[3].strip().split("\t")
    frame_label = header[0]  # Frame#
    time_label = header[1]   # Time
    marker_names = []
    for col in header[2:]:
        # Strip _X, _Y, _Z suffixes to get marker name
        name = col
        for suffix in ["_X", "_Y", "_Z"]:
            if name.endswith(suffix):
                name = name[:-2]
                break
        if name not in marker_names:
            marker_names.append(name)

    # Build new header: line 4 = marker names, line 5 = X1 Y1 Z1 ...
    new_line4 = frame_label + "\t" + time_label + "\t" + "\t".join(marker_names) + "\n"
    axis_parts = []
    for i in range(len(marker_names)):
        idx = i + 1
        axis_parts.extend([f"X{idx}", f"Y{idx}", f"Z{idx}"])
    new_line5 = "\t\t" + "\t".join(axis_parts) + "\n"

    lines[3] = new_line4
    lines.insert(4, new_line5)

    with open(path, "w") as f:
        f.writelines(lines)
    print(f"  Fixed TRC format: {os.path.basename(path)}")


# ── Version fix ────────────────────────────────────────────────────────────

def fix_osim_version(path, target="40500"):
    with open(path) as f:
        text = f.read()
    text = re.sub(r'Version="\d+"', f'Version="{target}"', text)
    with open(path, "w") as f:
        f.write(text)
    print(f"  Patched .osim Version -> {target}")


# ── Smooth TRC data ────────────────────────────────────────────────────────

def smooth_trc_data(trc_path, window=5):
    """Apply moving average smoothing to TRC marker coordinates."""
    with open(trc_path) as f:
        lines = f.readlines()
    header = lines[:5]
    data_start = 5
    data_lines = lines[data_start:]

    if not data_lines:
        return

    # Parse data
    rows = []
    for line in data_lines:
        parts = line.strip().split("\t")
        if len(parts) < 4:
            continue
        rows.append(parts)

    if len(rows) < window:
        return

    n_cols = len(rows[0])
    arr = np.array([[float(c) for c in row[2:]] for row in rows])

    # Smooth each column
    arr_smooth = uniform_filter1d(arr, size=window, axis=0, mode='nearest')

    # Write back
    new_lines = []
    for i, row in enumerate(rows):
        coords = [f"{v:.8f}" for v in arr_smooth[i]]
        new_lines.append("\t".join(row[:2] + coords) + "\n")

    with open(trc_path, "w") as f:
        f.writelines(header + new_lines)
    print(f"  Smoothed TRC ({window}-frame moving average): {os.path.basename(trc_path)}")


# ── Smooth .mot joint angles ───────────────────────────────────────────────

def smooth_mot_data(mot_path, window=15):
    """Apply moving average smoothing to coordinate columns in .mot file."""
    with open(mot_path) as f:
        lines = f.readlines()
    header_end = 0
    for i, line in enumerate(lines):
        if line.strip() == "endheader":
            header_end = i + 1
            break
    # Check if there's a column-name line after endheader
    col_names_line = None
    data_start = header_end
    if data_start < len(lines):
        first_words = lines[data_start].strip().split()
        if len(first_words) > 1 and first_words[0] == "time":
            col_names_line = lines[data_start]
            data_start += 1
    data_lines = lines[data_start:]
    if len(data_lines) < window:
        return
    rows = [line.strip().split() for line in data_lines if line.strip()]
    arr = np.array([[float(c) for c in row[1:]] for row in rows])
    arr_smooth = uniform_filter1d(arr, size=window, axis=0, mode='nearest')
    new_lines = []
    for i, row in enumerate(rows):
        coords = [f"{v:.8f}" for v in arr_smooth[i]]
        new_lines.append(row[0] + "\t" + "\t".join(coords) + "\n")
    output = lines[:header_end]
    if col_names_line:
        output.append(col_names_line)
    output += new_lines
    with open(mot_path, "w") as f:
        f.writelines(output)
    print(f"  Smoothed .mot ({window}-frame moving average): {os.path.basename(mot_path)}")


# ── Get time range from TRC ───────────────────────────────────────────────

def get_trc_time_range(trc_path):
    with open(trc_path) as f:
        lines = f.readlines()
    # Data starts after the two header lines (lines 0-3) + axis line (line 4)
    data_start = 5
    first = lines[data_start].strip().split("\t")
    last = lines[-1].strip().split("\t")
    return float(first[1]), float(last[1])


# ── Generate IK setup XML ─────────────────────────────────────────────────

def generate_ik_setup(osim_name, trc_name, mot_name, time_range,
                      marker_weights=None):
    if marker_weights is None:
        marker_weights = {
            "NOSE": 5, "LEFT_EAR": 5, "RIGHT_EAR": 5,
            "LEFT_SHOULDER": 20, "RIGHT_SHOULDER": 20,
            "LEFT_ELBOW": 20, "RIGHT_ELBOW": 20,
            "LEFT_WRIST": 20, "RIGHT_WRIST": 20,
            "LEFT_HIP": 20, "RIGHT_HIP": 20,
            "LEFT_KNEE": 20, "RIGHT_KNEE": 20,
            "LEFT_ANKLE": 20, "RIGHT_ANKLE": 20,
            "LEFT_HEEL": 5, "RIGHT_HEEL": 5,
            "LEFT_FOOT_INDEX": 5, "RIGHT_FOOT_INDEX": 5,
            "MOUTH_LEFT": 5, "MOUTH_RIGHT": 5,
            "LEFT_PINKY": 5, "RIGHT_PINKY": 5,
            "LEFT_INDEX": 5, "RIGHT_INDEX": 5,
            "LEFT_THUMB": 5, "RIGHT_THUMB": 5,
            "LEFT_EYE_INNER": 5, "LEFT_EYE": 5, "LEFT_EYE_OUTER": 5,
            "RIGHT_EYE_INNER": 5, "RIGHT_EYE": 5, "RIGHT_EYE_OUTER": 5,
        }

    tasks = []
    for name, weight in marker_weights.items():
        tasks.append(f'\t\t\t\t<IKMarkerTask name="{name}"><apply>true</apply><weight>{weight}</weight></IKMarkerTask>')

    xml = f'''<?xml version="1.0" encoding="UTF-8" ?>
<OpenSimDocument Version="40500">
\t<InverseKinematicsTool name="mediapipe_ik">
\t\t<results_directory>./</results_directory>
\t\t<model_file>{osim_name}</model_file>
\t\t<constraint_weight>Inf</constraint_weight>
\t\t<accuracy>1e-5</accuracy>
\t\t<time_range>{time_range[0]} {time_range[1]}</time_range>
\t\t<output_motion_file>{mot_name}</output_motion_file>
\t\t<report_errors>true</report_errors>
\t\t<IKTaskSet>
\t\t\t<objects>
{chr(10).join(tasks)}
\t\t\t</objects>
\t\t\t<groups />
\t\t</IKTaskSet>
\t\t<marker_file>{trc_name}</marker_file>
\t\t<coordinate_file></coordinate_file>
\t\t<report_marker_locations>false</report_marker_locations>
\t</InverseKinematicsTool>
</OpenSimDocument>'''
    return xml


# ── Build model ─────────────────────────────────────────────────────────

def build_model(pts, mass_kg=70.0):
    model = opensim.Model()
    model.setName("MediaPipePose")

    shoulder_width = norm(vec(pts["LEFT_SHOULDER"], pts["RIGHT_SHOULDER"]))
    hip_width = norm(vec(pts["LEFT_HIP"], pts["RIGHT_HIP"]))
    mid_hip = midpoint(pts["LEFT_HIP"], pts["RIGHT_HIP"])
    mid_shoulder = midpoint(pts["LEFT_SHOULDER"], pts["RIGHT_SHOULDER"])
    torso_len = norm(vec(mid_hip, mid_shoulder))
    upper_arm_len = (norm(vec(pts["LEFT_SHOULDER"], pts["LEFT_ELBOW"])) +
                     norm(vec(pts["RIGHT_SHOULDER"], pts["RIGHT_ELBOW"]))) / 2.0
    forearm_len = (norm(vec(pts["LEFT_ELBOW"], pts["LEFT_WRIST"])) +
                   norm(vec(pts["RIGHT_ELBOW"], pts["RIGHT_WRIST"]))) / 2.0
    thigh_len = (norm(vec(pts["LEFT_HIP"], pts["LEFT_KNEE"])) +
                 norm(vec(pts["RIGHT_HIP"], pts["RIGHT_KNEE"]))) / 2.0
    shank_len = (norm(vec(pts["LEFT_KNEE"], pts["LEFT_ANKLE"])) +
                 norm(vec(pts["RIGHT_KNEE"], pts["RIGHT_ANKLE"]))) / 2.0

    m_pelvis = mass_kg * 0.142
    m_torso = mass_kg * 0.355
    m_head = mass_kg * 0.081
    m_arm = mass_kg * 0.028
    m_forearm = mass_kg * 0.016
    m_thigh = mass_kg * 0.100
    m_shank = mass_kg * 0.0465
    m_foot = mass_kg * 0.0145

    def make_body(name, mass, com, inertia_scale=0.1, radius=0.05, color=None):
        b = opensim.Body(name, mass, opensim.Vec3(*com), opensim.Inertia(
            inertia_scale, inertia_scale, inertia_scale, 0, 0, 0))
        sphere = opensim.Sphere(radius)
        sphere.setName(f"{name}_display")
        if color:
            sphere.setColor(opensim.Vec3(*color))
        sphere.updSocket("frame").connect(b)
        b.addComponent(sphere)
        return b

    ground = model.getGround()

    pelvis = make_body("pelvis", m_pelvis, [0, 0, 0], 0.15, 0.08, [0.8, 0.2, 0.2])
    torso = make_body("torso", m_torso, [0, torso_len * 0.4, 0], 0.15, 0.08, [0.8, 0.2, 0.2])
    head = make_body("head", m_head, [0, 0.05, 0], 0.1, 0.07, [0.9, 0.9, 0.2])
    l_ua = make_body("l_upper_arm", m_arm, [0, -upper_arm_len * 0.5, 0], 0.03, 0.04, [0.2, 0.8, 0.2])
    r_ua = make_body("r_upper_arm", m_arm, [0, -upper_arm_len * 0.5, 0], 0.03, 0.04, [0.2, 0.8, 0.2])
    l_fa = make_body("l_forearm", m_forearm, [0, -forearm_len * 0.5, 0], 0.02, 0.035, [0.2, 0.8, 0.2])
    r_fa = make_body("r_forearm", m_forearm, [0, -forearm_len * 0.5, 0], 0.02, 0.035, [0.2, 0.8, 0.2])
    l_th = make_body("l_thigh", m_thigh, [0, -thigh_len * 0.4, 0], 0.06, 0.06, [0.2, 0.2, 0.8])
    r_th = make_body("r_thigh", m_thigh, [0, -thigh_len * 0.4, 0], 0.06, 0.06, [0.2, 0.2, 0.8])
    l_sh = make_body("l_shank", m_shank, [0, -shank_len * 0.4, 0], 0.04, 0.05, [0.2, 0.2, 0.8])
    r_sh = make_body("r_shank", m_shank, [0, -shank_len * 0.4, 0], 0.04, 0.05, [0.2, 0.2, 0.8])
    l_ft = make_body("l_foot", m_foot, [0.05, 0, 0], 0.01, 0.03, [0.6, 0.6, 0.6])
    r_ft = make_body("r_foot", m_foot, [0.05, 0, 0], 0.01, 0.03, [0.6, 0.6, 0.6])

    for b in [pelvis, torso, head, l_ua, r_ua, l_fa, r_fa,
              l_th, r_th, l_sh, r_sh, l_ft, r_ft]:
        model.addBody(b)

    pelvis_loc = opensim.Vec3(*mid_hip)
    pelvis_joint = opensim.FreeJoint("ground_pelvis", ground, opensim.Vec3(0, 0, 0),
                                      opensim.Vec3(0, 0, 0), pelvis, pelvis_loc,
                                      opensim.Vec3(0, 0, 0))
    for i in range(6):
        pelvis_joint.updCoordinate(i).setDefaultLocked(False)
    model.addJoint(pelvis_joint)

    def pin(parent, child, loc_in_parent, axis=opensim.Vec3(0, 0, -1)):
        j = opensim.PinJoint(f"{parent.getName()}_{child.getName()}", parent,
                             loc_in_parent, opensim.Vec3(0, 0, 0),
                             child, opensim.Vec3(0, 0, 0), opensim.Vec3(0, 0, 0))
        c = j.updCoordinate()
        c.setName(f"{child.getName()}_flexion")
        c.setRangeMin(-3.14)
        c.setRangeMax(3.14)
        c.setDefaultLocked(False)
        model.addJoint(j)

    def weld(parent, child, loc_in_parent):
        j = opensim.WeldJoint(f"{parent.getName()}_{child.getName()}", parent,
                              loc_in_parent, opensim.Vec3(0, 0, 0),
                              child, opensim.Vec3(0, 0, 0), opensim.Vec3(0, 0, 0))
        model.addJoint(j)

    weld(pelvis, torso, opensim.Vec3(0, norm(vec(mid_hip, mid_shoulder)) * 0.5, 0))
    weld(torso, head, opensim.Vec3(0, torso_len * 0.5, 0))
    pin(torso, l_ua, opensim.Vec3(-shoulder_width * 0.35, torso_len * 0.5, 0))
    pin(torso, r_ua, opensim.Vec3(shoulder_width * 0.35, torso_len * 0.5, 0))
    pin(l_ua, l_fa, opensim.Vec3(0, -upper_arm_len, 0))
    pin(r_ua, r_fa, opensim.Vec3(0, -upper_arm_len, 0))
    pin(pelvis, l_th, opensim.Vec3(-hip_width * 0.25, 0, 0))
    pin(pelvis, r_th, opensim.Vec3(hip_width * 0.25, 0, 0))
    pin(l_th, l_sh, opensim.Vec3(0, -thigh_len, 0))
    pin(r_th, r_sh, opensim.Vec3(0, -thigh_len, 0))
    weld(l_sh, l_ft, opensim.Vec3(0, -shank_len, 0))
    weld(r_sh, r_ft, opensim.Vec3(0, -shank_len, 0))

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
        body = model.getBodySet().get(body_name)
        marker = opensim.Marker(mname, body, opensim.Vec3(*loc))
        model.addMarker(marker)

    model.finalizeConnections()
    return model


# ── Run IK via opensim-cmd ────────────────────────────────────────────────

def run_ik_opensim_cmd(osim_path, trc_path, mot_path, work_dir):
    osim_name = os.path.basename(osim_path)
    trc_name = os.path.basename(trc_path)
    mot_name = os.path.basename(mot_path)

    t_start, t_end = get_trc_time_range(trc_path)
    time_range = (t_start, t_end + 0.1)

    setup_xml = generate_ik_setup(osim_name, trc_name, mot_name, time_range)
    setup_path = os.path.join(work_dir, "_ik_setup.xml")
    with open(setup_path, "w") as f:
        f.write(setup_xml)

    print(f"  TRC time range: {t_start:.3f} - {t_end:.3f}")
    print(f"  Running IK via {OPENSIM_CMD}...")
    result = subprocess.run(
        [OPENSIM_CMD, "run-tool", "_ik_setup.xml"],
        capture_output=True, text=True,
        cwd=work_dir,
    )
    for line in result.stdout.splitlines():
        if "error" in line.lower() or "Error" in line:
            print(f"    {line}")
    for line in result.stderr.splitlines():
        if "error" in line.lower() or "Error" in line:
            print(f"    {line}")
    if result.returncode != 0:
        print(f"  IK ERROR: return code {result.returncode}")
        return False

    # Smooth the .mot joint angles
    if os.path.exists(mot_path):
        smooth_mot_data(mot_path, window=15)
        print(f"  IK result: {mot_path} (smoothed)")
        return True
    else:
        print(f"  IK FAILED: output not found")
        return False


def process_one(csv_path, output_dir=None, copy_to_desktop=True):
    csv_path = Path(csv_path)
    base = csv_path.stem
    out = Path(output_dir) if output_dir else csv_path.parent

    osim_path = out / f"{base}.osim"
    mot_path = out / f"{base}_ik.mot"

    # Find matching TRC
    trc_candidates = sorted(out.glob(f"{base}*.trc"))
    if not trc_candidates:
        print(f"  ERROR: no TRC found for {base}")
        return
    trc_path = trc_candidates[0]

    print(f"\nProcessing: {base}")

    pts = read_first_frame(str(csv_path))
    print(f"  Building model from first frame...")
    model = build_model(pts)
    model.printToXML(str(osim_path))
    print(f"  .osim saved: {osim_path}")

    fix_osim_version(osim_path, "40500")
    fix_trc_format(str(trc_path))
    smooth_trc_data(str(trc_path), window=15)

    print(f"  Running IK...")
    ok = run_ik_opensim_cmd(
        str(osim_path), str(trc_path), str(mot_path), str(out)
    )

    if ok and copy_to_desktop:
        desk = Path.home() / "Desktop"
        shutil.copy(osim_path, desk / "pose.osim")
        shutil.copy(trc_path, desk / "pose.trc")
        shutil.copy(mot_path, desk / "pose.mot")
        print(f"\n  Copied to Desktop: pose.osim, pose.trc, pose.mot")
        print(f"  To view: opensim-cmd viz model pose.osim pose.mot")

    print(f"\n  Done.")


def process_all(output_dir="outputs"):
    out = Path(__file__).resolve().parent / output_dir
    csvs = sorted(out.glob("*.csv"))
    for csv_path in csvs:
        base = csv_path.stem
        if base == "test_mp_buffer":
            continue
        try:
            process_one(str(csv_path))
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"  ERROR {base}: {e}")


if __name__ == "__main__":
    base = Path(__file__).resolve().parent / "outputs"
    if len(sys.argv) > 1:
        process_one(sys.argv[1])
    else:
        target = None
        for c in sorted(base.glob("*.csv")):
            if "baseline_20260604" in c.name and "205320" in c.name:
                target = c
                break
        if target:
            process_one(str(target))
        else:
            csvs = sorted(base.glob("*.csv"))
            if csvs:
                process_one(str(csvs[0]))
            else:
                print("No CSV files found")
