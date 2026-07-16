# ============================================
# neurolab_kinematics.py
# ============================================
"""
Kinematic Analysis Module for Reaching Task
Integrated with MediaPipe Pose for real joint tracking
Compatible with: Streamlit / Gradio / Flask (Hugging Face Spaces)
"""

import cv2
import numpy as np
from scipy.signal import find_peaks
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional
import math


# ---------- MediaPipe Setup ----------
try:
    import mediapipe as mp
    MP_AVAILABLE = True
    mp_pose = mp.solutions.pose
    mp_drawing = mp.solutions.drawing_utils
except ImportError:
    MP_AVAILABLE = False
    print("WARNING: mediapipe not installed. Run: pip install mediapipe")


@dataclass
class KinematicValues:
    """القيم الكينماتيكية المستخرجة لكل حالة"""
    sparc: float           # Spectral Arc Length (log10) — أقل سالبية = أكثر سلاسة
    trunk_ratio: float     # نسبة مساهمة الجذع (%) — أقل = أفضل
    shoulder_elev: float   # ارتفاع الحزام الكتفي (mm أو %) — أقل = أفضل
    elbow_angle: float     # زاوية تمدد المرفق (°) — أكثر = أفضل
    peak_velocity: float   # السرعة القصوى لليد (cm/s) — أعلى = أفضل


@dataclass
class ReferenceValues:
    """القيم المرجعية من الأدبيات الموثوقة"""
    sparc: float = -1.436
    trunk_ratio: float = 3.0
    shoulder_elev: float = 6.5
    elbow_angle: float = 93.0
    peak_velocity: float = 62.2


class PoseExtractor:
    """
    يستخرج landmarks من الفيديو باستخدام MediaPipe Pose
    """

    # Landmarks IDs (MediaPipe Pose)
    L_SHOULDER = 11
    R_SHOULDER = 12
    L_ELBOW = 13
    R_ELBOW = 14
    L_WRIST = 15
    R_WRIST = 16
    L_HIP = 23
    R_HIP = 24
    L_KNEE = 25
    R_KNEE = 26
    NOSE = 0

    def __init__(self, static_image_mode=False, model_complexity=1,
                 min_detection_confidence=0.5, min_tracking_confidence=0.5):
        if not MP_AVAILABLE:
            raise ImportError("mediapipe is required. Install: pip install mediapipe")

        self.pose = mp_pose.Pose(
            static_image_mode=static_image_mode,
            model_complexity=model_complexity,
            min_detection_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence
        )

    def extract_from_video(self, video_path: str, target_side: str = 'right') -> Dict:
        """
        يستخرج الـ landmarks من كل frame في الفيديو

        Args:
            video_path: مسار الفيديو
            target_side: 'right' أو 'left' — الجانب المصاب/المحلل

        Returns:
            dict فيه trajectories لكل landmark + metadata
        """
        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        # اختيار landmarks حسب الجانب المستهدف
        if target_side == 'right':
            shoulder_id = self.R_SHOULDER
            elbow_id = self.R_ELBOW
            wrist_id = self.R_WRIST
            hip_id = self.R_HIP
            knee_id = self.R_KNEE
        else:
            shoulder_id = self.L_SHOULDER
            elbow_id = self.L_ELBOW
            wrist_id = self.L_WRIST
            hip_id = self.L_HIP
            knee_id = self.L_KNEE

        trajectories = {
            'shoulder': [], 'elbow': [], 'wrist': [],
            'hip': [], 'knee': [], 'nose': [],
            'timestamps': []
        }

        frame_idx = 0
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            # Convert BGR to RGB
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = self.pose.process(rgb)

            if results.pose_landmarks:
                lm = results.pose_landmarks.landmark

                def get_lm(idx):
                    return np.array([lm[idx].x * width, lm[idx].y * height, lm[idx].z])

                trajectories['shoulder'].append(get_lm(shoulder_id))
                trajectories['elbow'].append(get_lm(elbow_id))
                trajectories['wrist'].append(get_lm(wrist_id))
                trajectories['hip'].append(get_lm(hip_id))
                trajectories['knee'].append(get_lm(knee_id))
                trajectories['nose'].append(get_lm(self.NOSE))
                trajectories['timestamps'].append(frame_idx / fps)

            frame_idx += 1

        cap.release()

        # Convert to numpy arrays
        for key in ['shoulder', 'elbow', 'wrist', 'hip', 'knee', 'nose']:
            trajectories[key] = np.array(trajectories[key])
        trajectories['timestamps'] = np.array(trajectories['timestamps'])
        trajectories['fps'] = fps
        trajectories['frame_count'] = frame_idx

        return trajectories


class KinematicCalculator:
    """
    يحسب المتغيرات الكينماتيكية الخمسة من الـ trajectories
    """

    @staticmethod
    def angle_3points(a: np.ndarray, b: np.ndarray, c: np.ndarray) -> float:
        """
        يحسب الزاوية عند النقطة b (بالدرجات)
        a--b--c
        """
        ba = a[:2] - b[:2]
        bc = c[:2] - b[:2]

        cos_angle = np.dot(ba, bc) / (np.linalg.norm(ba) * np.linalg.norm(bc) + 1e-8)
        cos_angle = np.clip(cos_angle, -1.0, 1.0)
        angle = np.degrees(np.arccos(cos_angle))
        return angle

    @staticmethod
    def calc_sparc(velocity: np.ndarray, fs: float) -> float:
        """
        Spectral Arc Length (SPARC) — مقياس السلاسة
        القيم الأقل سالبية = حركة أكثر سلاسة

        Based on: Balasubramanian et al. (2015)
        """
        from scipy.fft import fft, fftfreq

        # Normalize velocity to [0, 1] time
        T = len(velocity) / fs
        t = np.linspace(0, T, len(velocity))

        # Interpolate to uniform sampling
        from scipy.interpolate import interp1d
        f_interp = interp1d(t, velocity, kind='cubic', fill_value='extrapolate')
        t_uniform = np.linspace(0, T, 1000)
        v_uniform = f_interp(t_uniform)

        # FFT
        V = fft(v_uniform)
        freqs = fftfreq(len(v_uniform), d=t_uniform[1] - t_uniform[0])

        # Positive frequencies only
        pos_mask = freqs > 0
        freqs_pos = freqs[pos_mask]
        V_pos = np.abs(V[pos_mask])

        # Normalize amplitude
        V_norm = V_pos / np.max(V_pos + 1e-10)

        # Find cutoff frequency (where amplitude drops below threshold)
        threshold = 0.05
        cutoff_idx = np.where(V_norm < threshold)[0]
        if len(cutoff_idx) > 0:
            cutoff_freq = freqs_pos[cutoff_idx[0]]
        else:
            cutoff_freq = freqs_pos[-1]

        # Spectral arc length
        valid_mask = freqs_pos <= cutoff_freq
        f_valid = freqs_pos[valid_mask]
        V_valid = V_norm[valid_mask]

        # Arc length in frequency domain
        df = np.diff(f_valid)
        dV = np.diff(V_valid)
        arc_length = np.sum(np.sqrt(df**2 + dV**2))

        # SPARC = -arc_length (more negative = less smooth)
        sparc = -arc_length
        return sparc

    @classmethod
    def calculate_all(cls, trajectories: Dict, side: str = 'right') -> KinematicValues:
        """
        يحسب الخمس متغيرات من trajectories

        Args:
            trajectories: dict مستخرج من PoseExtractor
            side: 'right' أو 'left'
        """
        t = trajectories['timestamps']
        shoulder = trajectories['shoulder']
        elbow = trajectories['elbow']
        wrist = trajectories['wrist']
        hip = trajectories['hip']
        nose = trajectories['nose']
        fps = trajectories['fps']

        # ---- 1. Elbow Angle (Extension) ----
        elbow_angles = []
        for i in range(len(shoulder)):
            angle = cls.angle_3points(shoulder[i], elbow[i], wrist[i])
            elbow_angles.append(angle)

        elbow_angle = np.max(elbow_angles)

        # ---- 2. Wrist Velocity & Peak Velocity ----
        wrist_2d = wrist[:, :2]
        dt = np.diff(t)
        dx = np.diff(wrist_2d[:, 0])
        dy = np.diff(wrist_2d[:, 1])
        displacement = np.sqrt(dx**2 + dy**2)

        velocity = displacement / (dt + 1e-8)

        from scipy.ndimage import gaussian_filter1d
        velocity_smooth = gaussian_filter1d(velocity, sigma=2)

        peak_velocity_px = np.max(velocity_smooth)
        peak_velocity = peak_velocity_px * 0.15

        # ---- 3. SPARC (Smoothness) ----
        if len(velocity_smooth) > 10:
            sparc = cls.calc_sparc(velocity_smooth, fps)
        else:
            sparc = -1.5

        # ---- 4. Trunk Ratio (displacement / hand displacement, as 0–1 ratio) ----
        trunk_disp = np.linalg.norm(nose[-1, :2] - nose[0, :2])
        hand_disp = np.linalg.norm(wrist[-1, :2] - wrist[0, :2])

        if hand_disp > 1e-6:
            trunk_ratio = trunk_disp / hand_disp
        else:
            trunk_ratio = 0.0

        # ---- 5. Shoulder Elevation (norm, 0–1) ----
        shoulder_y_start = shoulder[0, 1]
        shoulder_y_end = shoulder[-1, 1]
        shoulder_elev_px = abs(shoulder_y_start - shoulder_y_end)

        torso_height = np.linalg.norm(shoulder[0, :2] - hip[0, :2])
        if torso_height > 1e-6:
            shoulder_elev = shoulder_elev_px / torso_height
        else:
            shoulder_elev = 0.0

        return KinematicValues(
            sparc=float(sparc),
            trunk_ratio=float(trunk_ratio),
            shoulder_elev=float(shoulder_elev),
            elbow_angle=float(elbow_angle),
            peak_velocity=float(peak_velocity)
        )

    @classmethod
    def calculate_reach_window(cls, trajectories: Dict, start: int, end: int, fps: float) -> KinematicValues:
        """Neurolab 5-var formulas restricted to the active reach window."""
        shoulder = trajectories["shoulder"][start : end + 1]
        elbow = trajectories["elbow"][start : end + 1]
        wrist = trajectories["wrist"][start : end + 1]
        hip = trajectories["hip"][start : end + 1]
        nose = trajectories["nose"][start : end + 1]
        t = trajectories["timestamps"][start : end + 1]

        elbow_angles = [
            cls.angle_3points(shoulder[i], elbow[i], wrist[i]) for i in range(len(shoulder))
        ]
        elbow_angle = float(np.max(elbow_angles)) if elbow_angles else float("nan")

        wrist_2d = wrist[:, :2]
        dt = np.diff(t)
        if len(dt) == 0:
            dt = np.array([1.0 / max(fps, 1.0)])
        dx = np.diff(wrist_2d[:, 0])
        dy = np.diff(wrist_2d[:, 1])
        displacement = np.sqrt(dx**2 + dy**2)
        velocity = displacement / (dt + 1e-8)

        from scipy.ndimage import gaussian_filter1d
        velocity_smooth = gaussian_filter1d(velocity, sigma=2) if len(velocity) > 3 else velocity
        peak_velocity = float(np.max(velocity_smooth)) * 0.15 if len(velocity_smooth) else float("nan")

        if len(velocity_smooth) > 10:
            sparc = cls.calc_sparc(velocity_smooth, fps)
        else:
            sparc = -1.5

        trunk_disp = np.linalg.norm(nose[-1, :2] - nose[0, :2])
        hand_disp = np.linalg.norm(wrist[-1, :2] - wrist[0, :2])
        trunk_ratio = float(trunk_disp / hand_disp) if hand_disp > 1e-6 else 0.0

        shoulder_elev_px = abs(float(shoulder[0, 1] - shoulder[-1, 1]))
        torso_height = np.linalg.norm(shoulder[0, :2] - hip[0, :2])
        shoulder_elev = float(shoulder_elev_px / torso_height) if torso_height > 1e-6 else 0.0

        return KinematicValues(
            sparc=float(sparc),
            trunk_ratio=trunk_ratio,
            shoulder_elev=shoulder_elev,
            elbow_angle=elbow_angle,
            peak_velocity=peak_velocity,
        )


class ReachingAnalyzer:
    """
    الواجهة الرئيسية للتحليل
    """

    VARIABLES = ['SPARC', 'Trunk Ratio', 'Shoulder Elevation',
                 'Elbow Angle', 'Peak Velocity']
    DIRECTIONS = ['higher', 'lower', 'lower', 'higher', 'higher']

    def __init__(self):
        self.ref = ReferenceValues()
        self.extractor = PoseExtractor()
        self.calculator = KinematicCalculator()

    @staticmethod
    def calc_improvement(pre: float, post: float, direction: str) -> float:
        if direction == 'higher':
            return (post - pre) / abs(pre) * 100
        return (pre - post) / pre * 100

    @staticmethod
    def calc_gap(post: float, healthy: float, direction: str) -> float:
        if direction == 'higher':
            return abs(healthy - post) / abs(healthy) * 100
        return post - healthy

    def analyze_video(self, video_path: str, side: str = 'right') -> KinematicValues:
        """
        يحلل فيديو واحد ويرجع القيم الكينماتيكية
        """
        trajectories = self.extractor.extract_from_video(video_path, side)

        if len(trajectories['wrist']) < 5:
            raise ValueError("لم يتم العثور على pose كافٍ في الفيديو")

        return self.calculator.calculate_all(trajectories, side)

    def analyze_video_reach_window(
        self, video_path: str, side: str = 'right', start: int = 0, end: Optional[int] = None
    ) -> KinematicValues:
        """Neurolab metrics on a movement window (matches manuscript reaching task)."""
        trajectories = self.extractor.extract_from_video(video_path, side)
        if len(trajectories['wrist']) < 5:
            raise ValueError("لم يتم العثور على pose كافٍ في الفيديو")
        if end is None:
            end = len(trajectories['wrist']) - 1
        end = min(max(end, start), len(trajectories['wrist']) - 1)
        return self.calculator.calculate_reach_window(trajectories, start, end, trajectories['fps'])


def enrich_stroke_analysis_for_table(
    analysis: Dict,
    video_path: str,
    side: str,
) -> Dict:
    """
    Legacy hook — do NOT overwrite stroke_kinematic_pipeline locked metrics.
    trunk_ratio, SPARC, shoulder_vert_norm, movement_time, peak_velocity come
    from analyze_stroke_kinematic_csv (reach_only window) only.
    """
    return analysis

    def compare_three_videos(self, healthy_path: str, post_path: str,
                             pre_path: str, side: str = 'right') -> Dict:
        """
        يقارن بين 3 فيديوهات ويرجع الجدول الكامل
        """
        st = self
        healthy = st.analyze_video(healthy_path, side)
        post = st.analyze_video(post_path, side)
        pre = st.analyze_video(pre_path, side)

        return self.compare_three_conditions(healthy, post, pre)

    def compare_three_conditions(self, healthy: KinematicValues,
                                  post: KinematicValues,
                                  pre: KinematicValues) -> Dict:
        """
        يقارن بين 3 حالات (ممكن تستخدمها لو عندك قيم جاهزة)
        """
        values = {
            'SPARC': {'healthy': healthy.sparc, 'post': post.sparc, 'pre': pre.sparc},
            'Trunk Ratio': {'healthy': healthy.trunk_ratio, 'post': post.trunk_ratio, 'pre': pre.trunk_ratio},
            'Shoulder Elevation': {'healthy': healthy.shoulder_elev, 'post': post.shoulder_elev, 'pre': pre.shoulder_elev},
            'Elbow Angle': {'healthy': healthy.elbow_angle, 'post': post.elbow_angle, 'pre': pre.elbow_angle},
            'Peak Velocity': {'healthy': healthy.peak_velocity, 'post': post.peak_velocity, 'pre': pre.peak_velocity},
        }

        results = []
        for i, (var, vals) in enumerate(values.items()):
            direction = self.DIRECTIONS[i]
            pre_v = vals['pre']
            post_v = vals['post']
            healthy_v = vals['healthy']

            improvement = self.calc_improvement(pre_v, post_v, direction)
            gap = self.calc_gap(post_v, healthy_v, direction)

            results.append({
                'variable': var,
                'pre': round(pre_v, 2),
                'post': round(post_v, 2),
                'healthy': round(healthy_v, 2),
                'direction': direction,
                'pre_to_post_pct': round(improvement, 1),
                'post_to_healthy_pct': round(gap, 1),
                'pre_to_post_str': f"تحسن {abs(improvement):.0f}%",
                'post_to_healthy_str': f"فرق {abs(gap):.1f}%"
            })

        return {
            'results': results,
            'healthy': healthy,
            'post': post,
            'pre': pre,
            'summary': {
                'best_improvement': max(results, key=lambda x: x['pre_to_post_pct']),
                'smallest_gap': min(results, key=lambda x: x['post_to_healthy_pct']),
            }
        }


STREAMLIT_APP = '''
import streamlit as st
import pandas as pd
from neurolab_kinematics import ReachingAnalyzer

st.set_page_config(page_title="NeuroLab - Kinematic Analysis", layout="wide")
st.title("🧠 NeuroLab — Kinematic Analysis (Reaching Task)")
st.markdown("Powered by **MediaPipe Pose**")

analyzer = ReachingAnalyzer()

# Sidebar
st.sidebar.header("⚙️ الإعدادات")
target_side = st.sidebar.selectbox("الجانب المحلل", ["right", "left"], index=0)
st.sidebar.markdown("---")
st.sidebar.info("ارفع 3 فيديوهات: Healthy | Post | Pre")

# File uploaders
col1, col2, col3 = st.columns(3)
with col1:
    st.subheader("🟢 Healthy Side")
    healthy_file = st.file_uploader("اختر الفيديو", type=["mp4", "mov", "avi"], key="h")
with col2:
    st.subheader("🔵 Post (After)")
    post_file = st.file_uploader("اختر الفيديو", type=["mp4", "mov", "avi"], key="p")
with col3:
    st.subheader("🔴 Pre (Before)")
    pre_file = st.file_uploader("اختر الفيديو", type=["mp4", "mov", "avi"], key="r")

if all([healthy_file, post_file, pre_file]):
    with st.spinner("جاري تحليل الفيديوهات باستخدام MediaPipe Pose..."):
        # Save temp files
        for f, name in [(healthy_file, "healthy"), (post_file, "post"), (pre_file, "pre")]:
            with open(f"/tmp/{name}.mp4", "wb") as out:
                out.write(f.read())

        # Analyze
        try:
            result = analyzer.compare_three_videos(
                "/tmp/healthy.mp4", "/tmp/post.mp4", "/tmp/pre.mp4",
                side=target_side
            )

            st.success("✅ تم التحليل بنجاح!")

            # Results table
            st.subheader("📊 جدول المقارنة")
            df = pd.DataFrame([
                {
                    'المتغير': r['variable'],
                    'Pre': r['pre'],
                    'Post': r['post'],
                    'Healthy': r['healthy'],
                    'Pre → Post': r['pre_to_post_str'],
                    'Post → Healthy': r['post_to_healthy_str']
                }
                for r in result['results']
            ])
            st.dataframe(df, use_container_width=True, hide_index=True)

            # Bar chart
            st.subheader("📈 الرسوم البيانية")
            chart_df = pd.DataFrame({
                'Healthy': [r['healthy'] for r in result['results']],
                'Post': [r['post'] for r in result['results']],
                'Pre': [r['pre'] for r in result['results']]
            }, index=[r['variable'] for r in result['results']])
            st.bar_chart(chart_df)

            # Summary cards
            st.subheader("🎯 ملخص التحليل")
            c1, c2 = st.columns(2)
            with c1:
                best = result['summary']['best_improvement']
                st.metric("أفضل تحسن (Pre→Post)", best['variable'], best['pre_to_post_str'])
            with c2:
                closest = result['summary']['smallest_gap']
                st.metric("أقرب للطبيعي (Post→Healthy)", closest['variable'], closest['post_to_healthy_str'])

        except Exception as e:
            st.error(f"❌ حدث خطأ: {str(e)}")
            st.info("تأكد من وضوح الشخص في الفيديو وإن الإضاءة كويسة")
'''


if __name__ == "__main__":
    print("=" * 60)
    print("NeuroLab Kinematics Module")
    print("=" * 60)
    print("\nTo use in your HF Space:")
    print("1. Save this file as: neurolab_kinematics.py")
    print("2. Create app.py with the Streamlit code above")
    print("3. Add to requirements.txt:")
    print("   opencv-python-headless")
    print("   mediapipe")
    print("   numpy")
    print("   scipy")
    print("   pandas")
    print("   streamlit")
