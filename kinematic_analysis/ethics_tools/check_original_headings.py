from docx import Document
from pathlib import Path

p = Path(r"D:\Thesis app\phyphox\ethics commitee\Ethics BKK Last version  (AutoRecovered)_backup.docx")
doc = Document(str(p))

keywords = ["Birincil Sonuç Ölçütü:", "Veri Toplama Yöntemleri", "İkincil Sonuç Ölçütleri:"]
out = open(r"C:\Users\acer\AppData\Local\Temp\opencode\original_headings_check.txt", "w", encoding="utf-8")
for kw in keywords:
    out.write(f"\n=== {kw} ===\n")
    for p in doc.paragraphs:
        if kw in p.text:
            runs_info = []
            for r in p.runs:
                color = r.font.color.rgb if r.font.color and r.font.color.rgb else "default"
                runs_info.append(f"[{color}]{r.text[:30]}")
            out.write(p.text + "\n")
            out.write("RUNS: " + " | ".join(runs_info[:5]) + "\n")
            break
out.close()
print("done")
