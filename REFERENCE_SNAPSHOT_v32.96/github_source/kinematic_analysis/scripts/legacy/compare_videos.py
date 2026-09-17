import cv2
from pathlib import Path

folder = Path(r'D:\Thesis app\participants\3 مرضى\زينب 1\زينب')
for fname in ['Pre.mov', 'Post.mov', 'Healthy side.mov']:
    cap = cv2.VideoCapture(str(folder / fname))
    fps = cap.get(cv2.CAP_PROP_FPS)
    frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    duration = frames / fps if fps else 0
    print(f'{fname}: {w}x{h}, {frames} frames, {fps:.3f} fps, {duration:.2f}s')
    cap.release()

print('\nOriginal videos in mediapipe/movs/zeyneb:')
orig = Path(r'D:\Thesis app\participants\mediapipe\movs\zeyneb')
for fname in ['pre.MOV', 'post.MOV', 'healthyside.mov']:
    cap = cv2.VideoCapture(str(orig / fname))
    fps = cap.get(cv2.CAP_PROP_FPS)
    frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    duration = frames / fps if fps else 0
    print(f'{fname}: {w}x{h}, {frames} frames, {fps:.3f} fps, {duration:.2f}s')
    cap.release()
