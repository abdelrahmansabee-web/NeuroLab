import json
import math
from pathlib import Path

p = Path(r'C:\Users\acer\AppData\Local\Temp\opencode\all_patients_graph_metrics.json')
with open(p, 'r', encoding='utf-8') as f:
    data = json.load(f)

print(f"{'Patient':<12} {'Label':<8} {'SPARC':<10} {'NJC raw':<18} {'NJC %':<10} {'log10(NJC)':<12}")
print("="*70)
for pid, labels in data.items():
    for label, v in labels.items():
        njc = v['njc']
        pct = v['njc_pct']
        logv = round(math.log10(njc), 2) if njc and njc > 0 else None
        print(f"{pid:<12} {label:<8} {v['sparc']:<10} {njc:<18.1f} {pct:<10} {logv}")
