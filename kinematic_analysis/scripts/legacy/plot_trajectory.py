import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

df = pd.read_csv(r"C:\Users\acer\AppData\Local\Temp\opencode\pre_digital_marker_tracking.csv")

fig, axs = plt.subplots(2, 2, figsize=(12, 10))

axs[0,0].plot(df['time'], df['tracked_x'], 'r-', label='tracked x', lw=1)
axs[0,0].plot(df['time'], df['pose_wrist_x'], 'g--', alpha=0.6, label='pose wrist x', lw=1)
axs[0,0].set_xlabel('time (s)')
axs[0,0].set_ylabel('x (px)')
axs[0,0].legend()
axs[0,0].set_title('X trajectory')

axs[0,1].plot(df['time'], df['tracked_y'], 'r-', label='tracked y', lw=1)
axs[0,1].plot(df['time'], df['pose_wrist_y'], 'g--', alpha=0.6, label='pose wrist y', lw=1)
axs[0,1].set_xlabel('time (s)')
axs[0,1].set_ylabel('y (px)')
axs[0,1].legend()
axs[0,1].set_title('Y trajectory')

axs[1,0].plot(df['tracked_x'], df['tracked_y'], 'b-', lw=1)
axs[1,0].set_xlabel('x (px)')
axs[1,0].set_ylabel('y (px)')
axs[1,0].set_title('Tracked path')
axs[1,0].invert_yaxis()

axs[1,1].plot(df['time'], df['template_match_score'], 'k-', lw=1)
axs[1,1].set_xlabel('time (s)')
axs[1,1].set_ylabel('template match score')
axs[1,1].set_title('Template match score')

plt.tight_layout()
plt.savefig(r"C:\Users\acer\AppData\Local\Temp\opencode\pre_digital_marker_trajectory.png", dpi=150)
print("Saved trajectory plot")

# Compute displacement
dx = df['tracked_x'].iloc[-1] - df['tracked_x'].iloc[0]
dy = df['tracked_y'].iloc[-1] - df['tracked_y'].iloc[0]
disp = (dx**2 + dy**2)**0.5
print(f"Tracked displacement: {disp:.1f} px")
print(f"Pose wrist displacement: {((df['pose_wrist_x'].iloc[-1]-df['pose_wrist_x'].iloc[0])**2 + (df['pose_wrist_y'].iloc[-1]-df['pose_wrist_y'].iloc[0])**2)**0.5:.1f} px")
print(f"Hand detection rate: {df['hand_detected'].mean()*100:.1f}%")
print(f"Template match non-nan frames: {df['template_match_score'].notna().sum()}")
