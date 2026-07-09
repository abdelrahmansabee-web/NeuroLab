import pandas as pd
import numpy as np

df = pd.read_csv(r"C:\Users\acer\AppData\Local\Temp\opencode\pre_digital_marker_tracking.csv")
print("Shape:", df.shape)
print(df.head())
print("\nHand detection rate:", df['hand_detected'].mean()*100, "%")
print("Template match score stats:")
print(df['template_match_score'].describe())
print("\nTracked point range:")
print("x:", df['tracked_x'].min(), "-", df['tracked_x'].max())
print("y:", df['tracked_y'].min(), "-", df['tracked_y'].max())
