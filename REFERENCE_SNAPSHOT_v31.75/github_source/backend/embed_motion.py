"""Embed motion data directly into the .osim model file."""
import os
os.environ["OPENSIM_HOME"] = r"D:\Thesis app\participants\mediapipe\OpenSim 4.5"
import opensim
from pathlib import Path
import sys
import shutil
sys.path.insert(0, str(Path(__file__).resolve().parent))

from opensim_pipeline import read_first_frame, build_model
from run_ik import run_ik


def build_and_embed(csv_path):
    csv_path = Path(csv_path)
    base = csv_path.stem
    out_dir = csv_path.parent

    osim_path = out_dir / f"{base}.osim"
    trc_path = out_dir / f"{base}.trc"
    mot_path = out_dir / f"{base}_ik.mot"

    # Build model and save to file
    print(f"Building model from {csv_path.name}...")
    pts = read_first_frame(str(csv_path))
    model = build_model(pts)
    model.printToXML(str(osim_path))
    print(f"  Model saved with {model.getCoordinateSet().getSize()} coords")

    # Run IK to generate .mot
    print("Running IK...")
    run_ik(str(osim_path), str(trc_path), str(mot_path))

    # Load the .mot as TimeSeriesTable
    table = opensim.TimeSeriesTable(str(mot_path))

    # Reload the model (clean state)
    model = opensim.Model(str(osim_path))

    # Create PositionMotion from table
    print("Creating PositionMotion...")
    motion = opensim.PositionMotion.createFromTable(model, table)
    motion.setName("mediapipe_motion")
    motion.setDefaultEnabled(True)
    model.addComponent(motion)
    model.finalizeConnections()
    print("  Motion embedded")

    # Save model with motion embedded
    model.printToXML(str(osim_path))
    print(f"Saved {osim_path}")

    # Copy to Desktop
    desk = Path.home() / "Desktop"
    shutil.copy(osim_path, desk / "pose.osim")
    shutil.copy(trc_path, desk / "pose.trc")
    print("Copied to Desktop")


if __name__ == "__main__":
    base = Path(__file__).resolve().parent / "outputs"
    target = base / "baseline_20260604_205320_baseline.csv"
    build_and_embed(target)
