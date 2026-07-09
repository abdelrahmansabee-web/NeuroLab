import pandas as pd
old = pd.read_csv(r'D:\Thesis app\participants\mediapipe\movs\zeyneb\pre_20260603_165439_pre.csv')
new = pd.read_csv(r'D:\Thesis app\participants\زينب\pre_extracted_new.csv')
print('OLD meta:', old[['frame_width_px','frame_height_px','camera_view','affected_side','shoulder_width','fps']].iloc[0].to_dict())
print('NEW meta:', new[['frame_width_px','frame_height_px','camera_view','affected_side','shoulder_width','fps']].iloc[0].to_dict())
print('OLD palm x range:', old['palm_x'].min(), old['palm_x'].max())
print('NEW palm x range:', new['palm_x'].min(), new['palm_x'].max())
print('OLD shoulder x range:', old['shoulder_x'].min(), old['shoulder_x'].max())
print('NEW shoulder x range:', new['shoulder_x'].min(), new['shoulder_x'].max())
