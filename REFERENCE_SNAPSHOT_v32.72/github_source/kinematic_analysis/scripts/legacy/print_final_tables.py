import json
from pathlib import Path
import math

p = Path(r'C:\Users\acer\AppData\Local\Temp\opencode\all_patients_graph_metrics.json')
with open(p, 'r', encoding='utf-8') as f:
    data = json.load(f)

print("\n" + "="*140)
print("TABLE 1: Absolute Kinematic Values")
print("="*140)
print(f"{'Patient':<12} {'Label':<8} {'SPARC':<10} {'NJC':<18} {'PSI':<8} {'CVspeed':<10} {'ReachAmp(SW)':<14} {'MT(s)':<10} {'PV%':<8} {'TR':<8} {'ShElev(cm)':<12} {'ElbAng(deg)':<12}")
print("-"*140)
for pid in ['murat', 'kurusal', 'zeinab', '33_ana']:
    if pid not in data:
        continue
    for label in ['pre', 'post', 'affected']:
        if label not in data[pid]:
            continue
        v = data[pid][label]
        print(f"{pid:<12} {label:<8} {v['sparc']:<10} {v['njc']:<18.1f} {v['path_straightness']:<8} {v['cv_speed']:<10} {v['reach_amp_sw']:<14} {v['movement_time']:<10} {str(v['peak_velocity_pct']):<8} {v['trunk_ratio']:<8} {str(v['shoulder_elevation_cm']):<12} {str(v['elbow_angle_deg']):<12}")

print("\n" + "="*140)
print("TABLE 2: Relative to Healthy (%)")
print("="*140)
print(f"{'Patient':<12} {'Label':<8} {'SPARC%':<10} {'NJC%':<10} {'PSI%':<10} {'CVspeed%':<12} {'ReachAmp%':<12} {'MT%':<10} {'PV%':<8} {'TR%':<10} {'ShElev%':<10} {'ElbAng%':<10}")
print("-"*140)
for pid in ['murat', 'kurusal', 'zeinab', '33_ana']:
    if pid not in data:
        continue
    for label in ['pre', 'post', 'affected']:
        if label not in data[pid]:
            continue
        v = data[pid][label]
        print(f"{pid:<12} {label:<8} {v['sparc']:<10} {v['njc_pct']:<10} {v['path_straightness_pct']:<10} {v['cv_speed_pct']:<12} {v['reach_amp_pct']:<12} {v['movement_time_pct']:<10} {str(v['peak_velocity_pct']):<8} {v['trunk_ratio_pct']:<10} {v['shoulder_elevation_pct']:<10} {v['elbow_angle_pct']:<10}")

print("\n" + "="*140)
print("TABLE 3: Pre-to-Post Change (for patients with pre/post)")
print("="*140)
print(f"{'Patient':<12} {'SPARC d':<12} {'NJC% d':<12} {'PSI% d':<12} {'CV% d':<12} {'ReachAmp% d':<14} {'MT% d':<12} {'TR% d':<12} {'ElbAng% d':<12}")
print("-"*140)
for pid in ['murat', 'kurusal', 'zeinab']:
    if 'pre' not in data[pid] or 'post' not in data[pid]:
        continue
    pre = data[pid]['pre']
    post = data[pid]['post']
    def d(a, b):
        if a is None or b is None:
            return "N/A"
        return f"{b - a:+.1f}"
    print(f"{pid:<12} {d(pre['sparc'], post['sparc']):<12} {d(pre['njc_pct'], post['njc_pct']):<12} {d(pre['path_straightness_pct'], post['path_straightness_pct']):<12} {d(pre['cv_speed_pct'], post['cv_speed_pct']):<12} {d(pre['reach_amp_pct'], post['reach_amp_pct']):<14} {d(pre['movement_time_pct'], post['movement_time_pct']):<12} {d(pre['trunk_ratio_pct'], post['trunk_ratio_pct']):<12} {d(pre['elbow_angle_pct'], post['elbow_angle_pct']):<12}")

print("\nInterpretation:")
print("- SPARC: less negative = smoother. H > Post > Pre is expected recovery.")
print("- NJC%: higher = more segmented/less smooth.")
print("- PSI%: higher = straighter path (closer to 1 = straight line).")
print("- TR%: higher = more trunk compensation.")
print("- ElbAng%: lower = more flexor synergy/less extension.")
