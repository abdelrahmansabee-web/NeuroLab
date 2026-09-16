from docx import Document
from pathlib import Path

p = Path(r"D:\Thesis app\phyphox\ethics commitee\proposal\Abdelrahman Sabee Proposal (1)_updated.docx")
doc = Document(str(p))

keywords = [
    "OpenCap",
    "MediaPipe",
    "Phyphox",
    "Movement Smoothness",
    "Number of Velocity Peaks",
    "Shoulder Girdle Elevation",
    "Trunk Displacement",
    "Primary Outcomes",
    "Baseline Assessment",
    "Data Collection Setup",
    "14. Wagh",
]

out = open(r"C:\Users\acer\AppData\Local\Temp\opencode\proposal_verification.txt", "w", encoding="utf-8")
for kw in keywords:
    out.write(f"\n=== {kw} ===\n")
    for p in doc.paragraphs:
        if kw in p.text:
            runs_info = []
            for r in p.runs:
                color = r.font.color.rgb if r.font.color and r.font.color.rgb else "default"
                runs_info.append(f"[{color}]{r.text[:35]}")
            out.write(p.text[:700] + "\n")
            out.write("RUNS: " + " | ".join(runs_info[:6]) + "\n")
            break
out.close()
print("Verification written")
