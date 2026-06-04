"""Quick test: ZoeDepth metric depth on one frame from Zeyneb's video."""
import cv2
import torch
import numpy as np
from PIL import Image
from transformers import AutoImageProcessor, AutoModelForDepthEstimation
from pathlib import Path

SRC = Path(r"D:\Thesis app\participants\mediapipe\movs\zeyneb\baseline.MOV")
assert SRC.exists(), f"not found: {SRC}"

print("Loading ZoeDepth (this takes ~30s the first time)...")
model_name = "Intel/zoedepth-nyu"
proc = AutoImageProcessor.from_pretrained(model_name)
model = AutoModelForDepthEstimation.from_pretrained(model_name)
model.eval()

# Grab one frame
cap = cv2.VideoCapture(str(SRC))
cap.set(cv2.CAP_PROP_POS_FRAMES, 50)  # frame 50
ret, frame = cap.read()
cap.release()
assert ret, "could not read frame"
rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
pil_img = Image.fromarray(rgb)
print(f"Frame size: {pil_img.size}")

# Run depth
inputs = proc(pil_img, return_tensors="pt")
with torch.no_grad():
    outputs = model(**inputs)

# Post-process to get metric depth
pp = proc.post_process_depth_estimation(outputs, source_sizes=[(pil_img.height, pil_img.width)])
depth_tensor = pp[0]["predicted_depth"]  # shape (H, W) in meters
depth_np = depth_tensor.numpy()

print(f"Depth map shape: {depth_np.shape}")
print(f"Depth range:     {depth_np.min():.3f} – {depth_np.max():.3f} m")
print(f"Depth mean:      {depth_np.mean():.3f} m")
print(f"Depth center:    {depth_np[depth_np.shape[0]//2, depth_np.shape[1]//2]:.3f} m")

# Check depth at likely head/shoulder region (upper-center)
h, w = depth_np.shape
roi = depth_np[int(h*0.15):int(h*0.45), int(w*0.25):int(w*0.75)]
print(f"Upper-body ROI depth: {roi.min():.3f} – {roi.max():.3f} m  mean={roi.mean():.3f}")
