#!/usr/bin/env python3
"""Speed up CPU analysis on the clinic VPS without changing kinematic formulas."""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

POSE_MODEL_OLD = '''POSE_MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/pose_landmarker/"
    "pose_landmarker_heavy/float16/1/pose_landmarker_heavy.task"
)
POSE_MODEL_FILE = MODEL_DIR / "pose_landmarker_heavy.task"
'''

POSE_MODEL_NEW = '''_POSE_KIND = os.environ.get("NEUROLAB_POSE_MODEL", "full").strip().lower()
if _POSE_KIND not in ("lite", "full", "heavy"):
    _POSE_KIND = "full"
POSE_MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/pose_landmarker/"
    f"pose_landmarker_{_POSE_KIND}/float16/1/pose_landmarker_{_POSE_KIND}.task"
)
POSE_MODEL_FILE = MODEL_DIR / f"pose_landmarker_{_POSE_KIND}.task"
'''

DOWNSCALE_OLD = '''def _downscale_video_for_analysis(video_path: Path, max_w: int = 1280, max_h: int = 720) -> Path:'''
DOWNSCALE_NEW = '''def _downscale_video_for_analysis(video_path: Path, max_w: int = 960, max_h: int = 540) -> Path:'''

DOWNSCALE_NAME_OLD = '''        out = video_path.with_name(f"{video_path.stem}_analyze720p{video_path.suffix}")'''
DOWNSCALE_NAME_NEW = '''        out = video_path.with_name(f"{video_path.stem}_analyze{max_h}p{video_path.suffix}")'''

EXTRACT_CALL_OLD = '''    _prog(20, "Extracting pose landmarks…")
    try:
        report = extract_from_video(
            video_path=str(video_path),
            output_csv=str(csv_path),
            model_path=str(POSE_MODEL_FILE),
            affected_side=extract_arm,
            camera_view="auto",
            use_clahe=not legacy,
            max_interpolate_gap=8,
            butterworth_cutoff_hz=cutoff,
            butterworth_order=order,
            save_raw_pose=True,
            show_progress=True,
            legacy_format=legacy,
            save_intermediate_frames=save_intermediate,
            intermediate_dir=intermediate_dir,
            save_resampled=save_intermediate,
        )
'''

EXTRACT_CALL_NEW = '''    _prog(20, "Extracting pose landmarks…")
    if job_id:
        os.environ["ANALYZE_JOB_ID"] = str(job_id)
    os.environ.setdefault("NEUROLAB_FAST_ANALYZE", "1")
    try:
        report = extract_from_video(
            video_path=str(video_path),
            output_csv=str(csv_path),
            model_path=str(POSE_MODEL_FILE),
            affected_side=extract_arm,
            camera_view="auto",
            use_clahe=False,
            max_interpolate_gap=8,
            butterworth_cutoff_hz=cutoff,
            butterworth_order=order,
            save_raw_pose=True,
            show_progress=True,
            legacy_format=legacy,
            save_intermediate_frames=save_intermediate,
            intermediate_dir=intermediate_dir,
            save_resampled=save_intermediate,
        )
'''

POSE_PROGRESS_OLD = '''        if show_progress and processed % 30 == 0:
            progress = (frame_idx / total_frames) * 100 if total_frames > 0 else 0
            print(f"   {processed} إطار ({progress:.1f}%)", end='\\r')
'''

POSE_PROGRESS_NEW = '''        if show_progress and processed % 30 == 0:
            progress = (frame_idx / total_frames) * 100 if total_frames > 0 else 0
            print(f"   {processed} إطار ({progress:.1f}%)", end='\\r')
            job_id = os.environ.get("ANALYZE_JOB_ID")
            if job_id:
                try:
                    from analyze_job_runner import set_job_progress
                    pct = 20.0 + 32.0 * (frame_idx / max(total_frames, 1))
                    set_job_progress(job_id, pct, f"Pose {processed}/{total_frames}")
                except Exception:
                    pass
'''

EXTRACT_POSE_KW_OLD = '''    pose_kwargs: Dict[str, Any] = dict(
        video_path=str(video_path),
        output_csv=str(raw_path if save_raw_pose else output_path),
        model_path=model_path,
        use_clahe=use_clahe,
        smooth=True,
        max_interpolate_gap=max_interpolate_gap,
        show_progress=show_progress,
        legacy_format=legacy_format,
    )
'''

EXTRACT_POSE_KW_NEW = '''    fast = os.environ.get("NEUROLAB_FAST_ANALYZE", "1") != "0"
    target_fps_env = os.environ.get("NEUROLAB_POSE_TARGET_FPS", "30" if fast else "")
    pose_kwargs: Dict[str, Any] = dict(
        video_path=str(video_path),
        output_csv=str(raw_path if save_raw_pose else output_path),
        model_path=model_path,
        use_clahe=False if fast else use_clahe,
        smooth=True,
        max_interpolate_gap=max_interpolate_gap,
        show_progress=show_progress,
        legacy_format=legacy_format,
    )
    try:
        target_fps = int(target_fps_env) if target_fps_env else 0
    except ValueError:
        target_fps = 0
    if target_fps > 0:
        pose_kwargs["target_fps"] = target_fps
'''

SKELETON_OLD = '''    skeleton_path = output_path.with_name(output_path.stem + "_skeleton.mp4")
    try:
        render_skeleton_validation_video(
            video_path=str(video_path),
            raw_pose_csv=str(raw_path if save_raw_pose else output_path),
            output_mp4=str(skeleton_path),
            analyzed_side=meta.get("affected_side", affected_side),
        )
        report["validation_video"] = skeleton_path.name
        print(f"✓ Skeleton validation video: {skeleton_path.name}")
    except Exception as exc:
        print(f"  Skeleton video skipped: {exc}")
        report["validation_video"] = None
'''

SKELETON_NEW = '''    skeleton_path = output_path.with_name(output_path.stem + "_skeleton.mp4")
    skip_skeleton = os.environ.get("NEUROLAB_SKIP_SKELETON", "1") != "0"
    if skip_skeleton:
        report["validation_video"] = None
        print("  Skeleton video skipped (clinic fast path; overlay uses original video)")
    else:
        try:
            render_skeleton_validation_video(
                video_path=str(video_path),
                raw_pose_csv=str(raw_path if save_raw_pose else output_path),
                output_mp4=str(skeleton_path),
                analyzed_side=meta.get("affected_side", affected_side),
            )
            report["validation_video"] = skeleton_path.name
            print(f"✓ Skeleton validation video: {skeleton_path.name}")
        except Exception as exc:
            print(f"  Skeleton video skipped: {exc}")
            report["validation_video"] = None
'''

HAND_AFTER_POSE_OLD = '''        hand_report = merge_hand_landmarks_into_raw_csv(
            str(video_path),
            str(raw_path if save_raw_pose else output_path),
            affected_side=affected_side,
            show_progress=show_progress,
        )
'''

HAND_AFTER_POSE_NEW = '''        job_id = os.environ.get("ANALYZE_JOB_ID")
        if job_id:
            try:
                from analyze_job_runner import set_job_progress
                set_job_progress(job_id, 53, "Hand landmarks…")
            except Exception:
                pass
        hand_report = merge_hand_landmarks_into_raw_csv(
            str(video_path),
            str(raw_path if save_raw_pose else output_path),
            affected_side=affected_side,
            show_progress=show_progress,
        )
'''

HAND_LOOP_OLD = '''        store_side, tag = _detect_best_hand(
            landmarker, bgr, ts_ms, raw, frame_i, fw, fh, prefer_side,
        )
        ts_ms += int(round(1000.0 / max(fps, 1.0)))
'''

HAND_LOOP_NEW = '''        stride = max(1, int(os.environ.get("NEUROLAB_HAND_STRIDE", "2")))
        if frame_i % stride != 0:
            ts_ms += int(round(1000.0 / max(fps, 1.0)))
            frame_i += 1
            continue
        store_side, tag = _detect_best_hand(
            landmarker, bgr, ts_ms, raw, frame_i, fw, fh, prefer_side,
        )
        ts_ms += int(round(1000.0 / max(fps, 1.0)))
'''

HAND_SAVE_OLD = '''    cap.release()
    landmarker.close()
    raw.to_csv(raw_csv_path, index=False)
'''

HAND_SAVE_NEW = '''    cap.release()
    landmarker.close()
    hl_cols = [c for c in raw.columns if "_HL_" in str(c)]
    if hl_cols:
        raw[hl_cols] = raw[hl_cols].interpolate(method="linear", limit=4, limit_direction="both")
    raw.to_csv(raw_csv_path, index=False)
'''

OVERLAY_RETURN_OLD = '''                    cached["version"] = DEPLOY_VERSION
                    return JSONResponse(content=cached)
'''

OVERLAY_RETURN_NEW = '''                    cached["version"] = DEPLOY_VERSION
                    from thin_overlay import thin_overlay_payload
                    return JSONResponse(content=thin_overlay_payload(cached))
'''

OVERLAY_RETURN2_OLD = '''        data["version"] = DEPLOY_VERSION
        try:
            cache_path.write_text(json.dumps(data, default=str), encoding="utf-8")
        except Exception as exc:
            print(f"Overlay cache write failed: {exc}")
        return JSONResponse(content=data)
'''

OVERLAY_RETURN2_NEW = '''        data["version"] = DEPLOY_VERSION
        try:
            cache_path.write_text(json.dumps(data, default=str), encoding="utf-8")
        except Exception as exc:
            print(f"Overlay cache write failed: {exc}")
        from thin_overlay import thin_overlay_payload
        return JSONResponse(content=thin_overlay_payload(data))
'''

EXTRACT_IMPORT_OS = '''import json
'''
EXTRACT_IMPORT_OS_NEW = '''import json
import os
'''


def _patch(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    if new.strip() in text and old not in text:
        print(f"already patched: {label}")
        return
    if old not in text:
        raise SystemExit(f"pattern not found: {label} in {path}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    print(f"patched {label}")


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: patch_fast_analyze.py /opt/neurolab", file=sys.stderr)
        return 2
    root = Path(sys.argv[1]).resolve()
    overlay = Path(__file__).resolve().parent
    shutil.copy2(overlay / "thin_overlay.py", root / "thin_overlay.py")
    print("copied thin_overlay.py")

    runner = root / "analyze_job_runner.py"
    extractor = root / "mediapipe_csv_extractor.py"
    pose = root / "extract_pose_csv_robust.py"
    hands = root / "hand_landmarker_extract.py"
    main_py = root / "main.py"
    for path in (runner, extractor, pose, hands, main_py):
        if not path.is_file():
            print(f"error: {path} missing", file=sys.stderr)
            return 1

    pose_text = pose.read_text(encoding="utf-8")
    if "import os\n" not in pose_text:
        pose.write_text(pose_text.replace("import argparse\nimport sys\n", "import argparse\nimport os\nimport sys\n", 1), encoding="utf-8")
        print("added os import to extract_pose_csv_robust.py")

    extractor_text = extractor.read_text(encoding="utf-8")
    if "import os\n" not in extractor_text:
        extractor.write_text(extractor_text.replace("import json\nimport sys\n", "import json\nimport os\nimport sys\n", 1), encoding="utf-8")
        print("added os import to mediapipe_csv_extractor.py")

    hands_text = hands.read_text(encoding="utf-8")
    if "import os\n" not in hands_text:
        hands.write_text(hands_text.replace("import sys\nfrom pathlib import Path\n", "import os\nimport sys\nfrom pathlib import Path\n", 1), encoding="utf-8")
        print("added os import to hand_landmarker_extract.py")

    _patch(runner, POSE_MODEL_OLD, POSE_MODEL_NEW, "pose model full")
    _patch(runner, DOWNSCALE_OLD, DOWNSCALE_NEW, "downscale 540p")
    _patch(runner, DOWNSCALE_NAME_OLD, DOWNSCALE_NAME_NEW, "downscale filename")
    _patch(runner, EXTRACT_CALL_OLD, EXTRACT_CALL_NEW, "extract call")
    _patch(extractor, EXTRACT_POSE_KW_OLD, EXTRACT_POSE_KW_NEW, "pose kwargs fast")
    _patch(extractor, HAND_AFTER_POSE_OLD, HAND_AFTER_POSE_NEW, "hand progress")
    _patch(extractor, SKELETON_OLD, SKELETON_NEW, "skip skeleton")
    _patch(pose, POSE_PROGRESS_OLD, POSE_PROGRESS_NEW, "pose job progress")
    _patch(hands, HAND_LOOP_OLD, HAND_LOOP_NEW, "hand stride")
    _patch(hands, HAND_SAVE_OLD, HAND_SAVE_NEW, "hand interpolate")

    _patch(main_py, OVERLAY_RETURN_OLD, OVERLAY_RETURN_NEW, "thin cached overlay")
    _patch(main_py, OVERLAY_RETURN2_OLD, OVERLAY_RETURN2_NEW, "thin built overlay")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
