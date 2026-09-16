import sys; sys.path.insert(0,'.')
from kinematics_analyzer import analyze_reach_and_wipe
r = analyze_reach_and_wipe(r'outputs/pre_20260603_202733_pre.csv', affected_side='left')
print('total_duration_s:', r.get('total_duration_s'))
print('total_path_ratio:', r.get('total_path_ratio'))
print('smoothness_pause_pct:', r.get('smoothness_pause_pct'))
for n in ['forward','wipe_right','wipe_left','return']:
    p = r['phases'].get(n,{})
    d = p.get('duration_s')
    pv = p.get('peak_velocity')
    dn = p.get('distance_norm')
    print(f'{n}: dur={d}s pv={pv} dn={dn}')
