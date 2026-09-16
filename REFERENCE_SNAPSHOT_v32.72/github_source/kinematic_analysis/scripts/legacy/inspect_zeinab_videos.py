import cv2
from pathlib import Path

p = Path(r"D:\Thesis app\participants\mediapipe\movs\zeyneb\pre_20260603_202733_pre_2d.mp4")
cap = cv2.VideoCapture(str(p))
n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
print(f"frames: {n}")
for i, pct in enumerate([0.1, 0.3, 0.5, 0.7, 0.9]):
    fnum = int(n * pct)
    cap.set(cv2.CAP_PROP_POS_FRAMES, fnum)
    ret, frame = cap.read()
    if ret:
        out = Path(r"C:\Users\acer\AppData\Local\Temp\opencode") / f"zeyneb_pre_{i}.jpg"
        cv2.imwrite(str(out), frame)
        print(f"saved {out}")
cap.release()

p = Path(r"D:\Thesis app\participants\mediapipe\movs\zeyneb\post_20260603_202954_post_2d.mp4")
cap = cv2.VideoCapture(str(p))
n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
print(f"\nframes: {n}")
for i, pct in enumerate([0.1, 0.3, 0.5, 0.7, 0.9]):
    fnum = int(n * pct)
    cap.set(cv2.CAP_PROP_POS_FRAMES, fnum)
    ret, frame = cap.read()
    if ret:
        out = Path(r"C:\Users\acer\AppData\Local\Temp\opencode") / f"zeyneb_post_{i}.jpg"
        cv2.imwrite(str(out), frame)
        print(f"saved {out}")
cap.release()
