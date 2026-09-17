import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

df = pd.read_csv(r"C:\Users\acer\AppData\Local\Temp\opencode\pre_colored_marker_tracking.csv")

fig, axs = plt.subplots(2, 2, figsize=(12, 10))

axs[0,0].plot(df['time'], df['tracked_x'], 'r-', label='tracked x', lw=1)
axs[0,0].plot(df['time'], df['pose_wrist_x'], 'g--', alpha=0.5, label='pose wrist x', lw=1)
axs[0,0].set_xlabel('time (s)'); axs[0,0].set_ylabel('x (px)')
axs[0,0].legend(); axs[0,0].set_title('X trajectory')

axs[0,1].plot(df['time'], df['tracked_y'], 'r-', label='tracked y', lw=1)
axs[0,1].plot(df['time'], df['pose_wrist_y'], 'g--', alpha=0.5, label='pose wrist y', lw=1)
axs[0,1].set_xlabel('time (s)'); axs[0,1].set_ylabel('y (px)')
axs[0,1].legend(); axs[0,1].set_title('Y trajectory')

axs[1,0].plot(df['tracked_x'], df['tracked_y'], 'b-', lw=1)
axs[1,0].set_xlabel('x (px)'); axs[1,0].set_ylabel('y (px)')
axs[1,0].set_title('Tracked path')
axs[1,0].invert_yaxis()

axs[1,1].plot(df['time'], df['marker_detected'], 'k-', lw=1)
axs[1,1].set_xlabel('time (s)'); axs[1,1].set_ylabel('detected')
axs[1,1].set_title('Marker detection flag')

plt.tight_layout()
plt.savefig(r"C:\Users\acer\AppData\Local\Temp\opencode\pre_colored_marker_trajectory.png", dpi=150)
print("Saved colored marker trajectory plot")

print("Detection rate:", df['marker_detected'].mean()*100, "%")
print("Radius stats:", df['marker_radius'].describe())
print("Displacement:", ((df['tracked_x'].iloc[-1]-df['tracked_x'].iloc[0])**2 + (df['tracked_y'].iloc[-1]-df['tracked_y'].iloc[0])**2)**0.5)
