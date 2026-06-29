# ============================================
# neuro_kinematics.py
# ============================================
"""
Backend Kinematic Analysis Module
- Auto affected side detection
- Table calibration (60cm)
- MediaPipe Pose tracking
- 5 kinematic variables
- Pre/Post/Healthy comparison

NO FRONTEND CODE — pure Python module.
"""

from __future__ import annotations

import cv2
import numpy as np
from scipy.signal import savgol_filter
from scipy.fft import fft, fftfreq
from scipy.interpolate import interp1d
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Tuple

import mediapipe as mp


TABLE_WIDTH_CM = 60.0
SHOULDER_WIDTH_CM = 40.0  # fallback scale when blue table not detected
SIDE_DETECTION_THRESHOLD = 1.3


@dataclass
class KinematicValues:
    sparc: float
    trunk_ratio: float
    shoulder_elev: float
    elbow_angle: float
    peak_velocity: float


@dataclass
class SideDetectionResult:
    affected_side: str
    healthy_side: str
    left_motion: float
    right_motion: float
    confidence: float

    def to_dict(self) -> Dict:
        return asdict(self)


# ============================================
# 1. AUTO AFFECTED SIDE DETECTOR
# ============================================

class AffectedSideDetector:
    """
    Detects which arm moves more (affected / paretic side).
    - MediaPipe: LEFT_WRIST vs RIGHT_WRIST (patient anatomy).
    - Frame diff fallback: image-left half ≈ patient RIGHT (frontal view).
    """

    def __init__(self, motion_threshold_ratio: float = SIDE_DETECTION_THRESHOLD):
        self.threshold = motion_threshold_ratio

    def detect(self, video_path: str) -> SideDetectionResult:
        cap = cv2.VideoCapture(video_path)
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))

        frames = []
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            frames.append(frame)
        cap.release()

        if len(frames) < 2:
            raise ValueError("Video too short")

        gray_frames = [cv2.cvtColor(f, cv2.COLOR_BGR2GRAY) for f in frames]

        # Patient-anatomical wrist motion (preferred: MediaPipe body left/right)
        patient_left_motion = 0.0
        patient_right_motion = 0.0
        method = "frame_diff"

        try:
            left_mp, right_mp = self._mediapipe_method(frames, w)
            if left_mp > 0 and right_mp > 0:
                patient_left_motion = left_mp
                patient_right_motion = right_mp
                method = "mediapipe"
        except Exception:
            pass

        if method != "mediapipe":
            image_left, image_right = self._frame_diff_method(gray_frames, w)
            # Frontal camera: image left half ≈ patient's RIGHT arm
            patient_right_motion = image_left
            patient_left_motion = image_right

        if patient_right_motion > patient_left_motion:
            affected = "right"
            healthy = "left"
            confidence = patient_right_motion / (patient_left_motion + 1e-8)
        else:
            affected = "left"
            healthy = "right"
            confidence = patient_left_motion / (patient_right_motion + 1e-8)

        return SideDetectionResult(
            affected_side=affected,
            healthy_side=healthy,
            left_motion=round(float(patient_left_motion), 2),
            right_motion=round(float(patient_right_motion), 2),
            confidence=round(float(confidence), 2),
        )

    def _frame_diff_method(self, gray_frames: List[np.ndarray], w: int) -> Tuple[float, float]:
        left_motion = []
        right_motion = []
        mid = w // 2

        for i in range(len(gray_frames) - 1):
            diff = cv2.absdiff(gray_frames[i], gray_frames[i + 1])
            left_motion.append(np.mean(diff[:, :mid]))
            right_motion.append(np.mean(diff[:, mid:]))

        return np.sum(left_motion), np.sum(right_motion)

    def _mediapipe_method(self, frames: List[np.ndarray], w: int) -> Tuple[float, float]:
        pose = mp.solutions.pose.Pose(
            static_image_mode=False,
            model_complexity=1,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )

        left_wrist = []
        right_wrist = []

        try:
            for frame in frames:
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                results = pose.process(rgb)

                if results.pose_landmarks:
                    lm = results.pose_landmarks.landmark
                    h = frame.shape[0]
                    left_wrist.append([lm[15].x * w, lm[15].y * h])
                    right_wrist.append([lm[16].x * w, lm[16].y * h])
        finally:
            pose.close()

        if len(left_wrist) < 2 or len(right_wrist) < 2:
            return 0, 0

        left_arr = np.array(left_wrist)
        right_arr = np.array(right_wrist)

        left_disp = np.sum(np.linalg.norm(np.diff(left_arr, axis=0), axis=1))
        right_disp = np.sum(np.linalg.norm(np.diff(right_arr, axis=0), axis=1))

        return left_disp, right_disp


# ============================================
# 2. TABLE CALIBRATOR
# ============================================

class TableCalibrator:
    def __init__(self, real_width_cm: float = TABLE_WIDTH_CM):
        self.real_width_cm = real_width_cm
        self.scale_cm_per_px: Optional[float] = None
        self.table_width_px: Optional[float] = None

    def detect(self, frame: np.ndarray) -> bool:
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        lower = np.array([90, 40, 40])
        upper = np.array([140, 255, 255])
        mask = cv2.inRange(hsv, lower, upper)

        kernel = np.ones((5, 5), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        if not contours:
            return False

        h, w = frame.shape[:2]
        min_area = (h * w) * 0.03
        frame_max = float(max(w, h))

        candidates = []
        for cnt in sorted(contours, key=cv2.contourArea, reverse=True):
            area = cv2.contourArea(cnt)
            if area < min_area:
                continue
            x, y, bw, bh = cv2.boundingRect(cnt)
            extent = float(max(bw, bh))
            # Reject blobs that span nearly the full frame (background false positive)
            if bw > w * 0.85 or bh > h * 0.85:
                continue
            if extent > frame_max * 0.65:
                continue
            if bw < 40 and bh < 40:
                continue
            candidates.append((area, bw, bh, x, y, cnt))

        if not candidates:
            return False

        # Prefer wide, lower-frame blobs (physical table surface)
        def score(item):
            area, bw, bh, x, y, _ = item
            cy = y + bh / 2.0
            wide_bonus = bw / max(bh, 1)
            lower_bonus = cy / max(h, 1)
            return area * (1.0 + 0.35 * wide_bonus + 0.25 * lower_bonus)

        _, bw, bh, _, _, _ = max(candidates, key=score)
        self.table_width_px = float(max(bw, bh))
        self.scale_cm_per_px = self.real_width_cm / self.table_width_px

        return True

    def get_scale(self) -> Optional[float]:
        return self.scale_cm_per_px

    def get_table_width_px(self) -> Optional[float]:
        return self.table_width_px

    @staticmethod
    def shoulder_fallback_scale(frame: np.ndarray) -> Optional[float]:
        """Estimate cm/px from MediaPipe shoulder width when table HSV fails."""
        try:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            pose = mp.solutions.pose.Pose(
                static_image_mode=True, model_complexity=1, min_detection_confidence=0.5
            )
            res = pose.process(rgb)
            pose.close()
            if not res.pose_landmarks:
                return None
            lm = res.pose_landmarks.landmark
            h, w = frame.shape[:2]
            ls = np.array([lm[11].x * w, lm[11].y * h])
            rs = np.array([lm[12].x * w, lm[12].y * h])
            sw = float(np.linalg.norm(rs - ls))
            if sw < 20:
                return None
            return SHOULDER_WIDTH_CM / sw
        except Exception:
            return None


# ============================================
# 3. POSE EXTRACTOR
# ============================================

class PoseExtractor:
    NOSE = 0
    L_SHOULDER = 11
    R_SHOULDER = 12
    L_ELBOW = 13
    R_ELBOW = 14
    L_WRIST = 15
    R_WRIST = 16
    L_HIP = 23
    R_HIP = 24

    def __init__(self):
        self.pose = mp.solutions.pose.Pose(
            static_image_mode=False,
            model_complexity=1,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )

    def close(self) -> None:
        self.pose.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def extract(self, video_path: str, side: str = "right") -> Dict:
        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        if side == "right":
            ids = {
                "shoulder": self.R_SHOULDER,
                "elbow": self.R_ELBOW,
                "wrist": self.R_WRIST,
                "hip": self.R_HIP,
            }
        else:
            ids = {
                "shoulder": self.L_SHOULDER,
                "elbow": self.L_ELBOW,
                "wrist": self.L_WRIST,
                "hip": self.L_HIP,
            }

        traj = {k: [] for k in ["shoulder", "elbow", "wrist", "hip", "nose"]}
        traj["timestamps"] = []

        frame_idx = 0
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            res = self.pose.process(rgb)

            if res.pose_landmarks:
                lm = res.pose_landmarks.landmark

                def p(idx):
                    return np.array([lm[idx].x * w, lm[idx].y * h])

                for key, idx in ids.items():
                    traj[key].append(p(idx))
                traj["nose"].append(p(self.NOSE))
                traj["timestamps"].append(frame_idx / fps)

            frame_idx += 1

        cap.release()

        for k in ["shoulder", "elbow", "wrist", "hip", "nose"]:
            traj[k] = np.array(traj[k])
        traj["timestamps"] = np.array(traj["timestamps"])
        traj["fps"] = fps

        return traj


# ============================================
# 4. KINEMATIC ANALYZER
# ============================================

class KinematicAnalyzer:
    def __init__(self, calibrator: TableCalibrator):
        self.calib = calibrator
        self.pose_extractor = PoseExtractor()

    def close(self) -> None:
        self.pose_extractor.close()

    @staticmethod
    def angle(a: np.ndarray, b: np.ndarray, c: np.ndarray) -> float:
        ba = a[:2] - b[:2]
        bc = c[:2] - b[:2]
        cos = np.dot(ba, bc) / (np.linalg.norm(ba) * np.linalg.norm(bc) + 1e-8)
        return np.degrees(np.arccos(np.clip(cos, -1, 1)))

    @staticmethod
    def calc_sparc(velocity: np.ndarray, fs: float) -> float:
        if len(velocity) < 20:
            return -1.5

        t_orig = np.linspace(0, 1, len(velocity))
        t_uniform = np.linspace(0, 1, 1000)
        f_interp = interp1d(t_orig, velocity, kind="cubic", fill_value="extrapolate")
        v_uniform = f_interp(t_uniform)

        v_norm = v_uniform / (np.sum(v_uniform) + 1e-10)
        V = fft(v_norm)
        freqs = fftfreq(len(v_norm), d=t_uniform[1] - t_uniform[0])

        pos = freqs > 0
        freqs_pos = freqs[pos]
        V_pos = np.abs(V[pos])
        V_amp = V_pos / (np.max(V_pos) + 1e-10)

        cutoff_idx = np.where(V_amp < 0.05)[0]
        f_max = freqs_pos[cutoff_idx[0]] if len(cutoff_idx) > 0 else freqs_pos[-1]

        valid = freqs_pos <= f_max
        f_v = freqs_pos[valid]
        a_v = V_amp[valid]

        df = np.diff(f_v)
        da = np.diff(a_v)
        arc_len = np.sum(np.sqrt(df**2 + da**2))

        sparc = -arc_len
        sparc_mapped = -1.4 - (sparc + 0.5) * 0.4
        return float(np.clip(sparc_mapped, -2.5, -0.5))

    def analyze_video(self, video_path: str, side: str = "right") -> KinematicValues:
        cap = cv2.VideoCapture(video_path)
        ret, first_frame = cap.read()
        cap.release()

        if not ret:
            raise ValueError("Cannot read video")

        table_ok = self.calib.detect(first_frame)
        scale = self.calib.get_scale()
        scale_source = "table_hsv"

        if not table_ok or scale is None:
            scale = TableCalibrator.shoulder_fallback_scale(first_frame)
            scale_source = "shoulder_fallback"
            if scale is None:
                raise ValueError("Table detection failed and shoulder fallback unavailable")

        traj = self.pose_extractor.extract(video_path, side)

        if len(traj["wrist"]) < 5:
            raise ValueError("Not enough pose data")

        t = traj["timestamps"]
        shoulder = traj["shoulder"]
        elbow = traj["elbow"]
        wrist = traj["wrist"]
        hip = traj["hip"]
        nose = traj["nose"]
        fps = traj["fps"]

        angles = [self.angle(shoulder[i], elbow[i], wrist[i]) for i in range(len(shoulder))]
        elbow_angle = float(np.max(angles))

        wrist_px = wrist[:, :2]
        dt = np.diff(t)
        dx = np.diff(wrist_px[:, 0])
        dy = np.diff(wrist_px[:, 1])
        dist_px = np.sqrt(dx**2 + dy**2)
        vel_px_s = dist_px / (dt + 1e-8)

        if len(vel_px_s) > 11:
            vel_smooth = savgol_filter(vel_px_s, min(11, len(vel_px_s) // 2 * 2 + 1), 3)
        else:
            vel_smooth = vel_px_s

        vel_cm_s = vel_smooth * scale
        peak_velocity = float(np.max(vel_cm_s))

        # Reach window: 10–90% cumulative wrist displacement (reduces idle-frame noise)
        wx = wrist[:, 0]
        cum = np.abs(np.cumsum(np.diff(wx, prepend=wx[0])))
        span = float(cum.max() - cum.min()) if len(cum) else 0.0
        if span > 1e-6:
            lo, hi = span * 0.10, span * 0.90
            idx = np.where((cum >= lo) & (cum <= hi))[0]
            if len(idx) >= 8:
                s, e = int(idx[0]), int(idx[-1])
                nose_w, wrist_w, shoulder_w = nose[s : e + 1], wrist[s : e + 1], shoulder[s : e + 1]
                hip_w = hip[s]
                vel_w = vel_cm_s[max(0, s - 1) : min(len(vel_cm_s), e)]
                angles_w = angles[s : e + 1]
            else:
                nose_w, wrist_w, shoulder_w, hip_w, vel_w, angles_w = nose, wrist, shoulder, hip[0], vel_cm_s, angles
        else:
            nose_w, wrist_w, shoulder_w, hip_w, vel_w, angles_w = nose, wrist, shoulder, hip[0], vel_cm_s, angles

        sparc = self.calc_sparc(vel_w, fps)
        elbow_angle = float(np.max(angles_w)) if angles_w else elbow_angle

        trunk_disp = np.linalg.norm(nose_w[-1, :2] - nose_w[0, :2])
        hand_disp = np.linalg.norm(wrist_w[-1, :2] - wrist_w[0, :2])
        trunk_ratio = float(
            np.clip((trunk_disp / hand_disp * 100) if hand_disp > 10 else 0, 0, 60)
        )

        shoulder_y_move = abs(float(shoulder_w[-1, 1] - shoulder_w[0, 1]))
        torso_h = np.linalg.norm(shoulder_w[0, :2] - hip_w[:2])
        shoulder_elev = float(
            np.clip((shoulder_y_move / torso_h * 100) if torso_h > 10 else 0, 0, 50)
        )

        return KinematicValues(
            sparc=round(sparc, 2),
            trunk_ratio=round(trunk_ratio, 1),
            shoulder_elev=round(shoulder_elev, 1),
            elbow_angle=round(elbow_angle, 1),
            peak_velocity=round(peak_velocity, 1),
        )


# ============================================
# 5. COMPARISON FUNCTIONS (EXACT — do not change)
# ============================================

def calc_improvement(pre: float, post: float, direction: str) -> float:
    if direction == "higher":
        return (post - pre) / abs(pre) * 100
    return (pre - post) / pre * 100


def calc_gap(post: float, healthy: float, direction: str) -> float:
    if direction == "higher":
        return abs(healthy - post) / abs(healthy) * 100
    return post - healthy


DIRECTIONS = ["higher", "lower", "lower", "higher", "higher"]


def compare_conditions(
    healthy: KinematicValues,
    post: KinematicValues,
    pre: KinematicValues,
) -> List[Dict]:
    values = {
        "SPARC": {"h": healthy.sparc, "p": post.sparc, "r": pre.sparc},
        "Trunk Ratio": {"h": healthy.trunk_ratio, "p": post.trunk_ratio, "r": pre.trunk_ratio},
        "Shoulder Elevation": {"h": healthy.shoulder_elev, "p": post.shoulder_elev, "r": pre.shoulder_elev},
        "Elbow Angle": {"h": healthy.elbow_angle, "p": post.elbow_angle, "r": pre.elbow_angle},
        "Peak Velocity": {"h": healthy.peak_velocity, "p": post.peak_velocity, "r": pre.peak_velocity},
    }

    results = []
    for i, (var, vals) in enumerate(values.items()):
        direction = DIRECTIONS[i]
        imp = calc_improvement(vals["r"], vals["p"], direction)
        gap = calc_gap(vals["p"], vals["h"], direction)

        results.append(
            {
                "variable": var,
                "pre": vals["r"],
                "post": vals["p"],
                "healthy": vals["h"],
                "direction": direction,
                "pre_to_post_pct": round(imp, 1),
                "post_to_healthy_pct": round(gap, 1),
                "pre_to_post_str": f"تحسن {abs(imp):.0f}%",
                "post_to_healthy_str": f"فرق {abs(gap):.1f}%",
            }
        )

    return results


def kinematic_values_to_api(kv: KinematicValues, side: str = "right") -> Dict:
    """Map module output to NeuroLab frontend JSON keys."""
    return {
        "sparc": kv.sparc,
        "trunk_ratio": kv.trunk_ratio / 100.0,
        "shoulder_vert_norm": kv.shoulder_elev / 100.0,
        "shoulder_elevation_norm": kv.shoulder_elev / 100.0,
        "elbow_angle_mean": kv.elbow_angle,
        "elbow_angle_reliable": True,
        "peak_velocity_cm_s": kv.peak_velocity,
        "peak_velocity_px_s": kv.peak_velocity,
        "side_analyzed": side,
        "_analyzer": "neuro_kinematics",
    }


def resolve_arm_for_phase(phase: str, side_info: SideDetectionResult) -> str:
    ph = (phase or "pre").strip().lower()
    if ph in ("baseline", "healthy"):
        return side_info.healthy_side
    return side_info.affected_side


def analyze_single_phase(
    video_path: str,
    phase: str,
    affected_side: Optional[str] = None,
    healthy_side: Optional[str] = None,
) -> Tuple[KinematicValues, Dict]:
    """
    Analyze one video (pre / post / healthy).
    If affected_side is omitted, runs AffectedSideDetector on this video.
    """
    calibrator = TableCalibrator(real_width_cm=TABLE_WIDTH_CM)
    analyzer = KinematicAnalyzer(calibrator)
    try:
        if affected_side and healthy_side:
            side = healthy_side if phase.lower() in ("baseline", "healthy") else affected_side
            meta = {"affected_side": affected_side, "healthy_side": healthy_side, "confidence": None}
        else:
            det = AffectedSideDetector()
            side_info = det.detect(video_path)
            side = resolve_arm_for_phase(phase, side_info)
            meta = side_info.to_dict()
        vals = analyzer.analyze_video(video_path, side=side)
        meta["side_analyzed"] = side
        meta["table_scale_cm_per_px"] = calibrator.get_scale()
        meta["table_width_px"] = calibrator.get_table_width_px()
        return vals, meta
    finally:
        analyzer.close()


# ============================================
# 6. MAIN ENTRY POINT
# ============================================

def analyze_patient_session(
    healthy_path: str,
    post_path: str,
    pre_path: str,
) -> Tuple[List[Dict], SideDetectionResult]:
    """
    Complete workflow:
    1. Auto-detect affected side from Pre video
    2. Analyze all 3 videos
    3. Compare and return results

    Returns: (comparison_results, side_detection_info)
    """
    detector = AffectedSideDetector()
    side_info = detector.detect(pre_path)

    affected = side_info.affected_side
    healthy_side = side_info.healthy_side

    calibrator = TableCalibrator(real_width_cm=TABLE_WIDTH_CM)
    analyzer = KinematicAnalyzer(calibrator)

    try:
        healthy_vals = analyzer.analyze_video(healthy_path, side=healthy_side)
        post_vals = analyzer.analyze_video(post_path, side=affected)
        pre_vals = analyzer.analyze_video(pre_path, side=affected)
    finally:
        analyzer.close()

    comparison = compare_conditions(healthy_vals, post_vals, pre_vals)

    return comparison, side_info


__all__ = [
    "TABLE_WIDTH_CM",
    "SIDE_DETECTION_THRESHOLD",
    "KinematicValues",
    "SideDetectionResult",
    "AffectedSideDetector",
    "TableCalibrator",
    "PoseExtractor",
    "KinematicAnalyzer",
    "calc_improvement",
    "calc_gap",
    "DIRECTIONS",
    "compare_conditions",
    "kinematic_values_to_api",
    "resolve_arm_for_phase",
    "analyze_single_phase",
    "analyze_patient_session",
]
