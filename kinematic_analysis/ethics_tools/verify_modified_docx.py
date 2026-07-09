from docx import Document
from pathlib import Path

p = Path(r"D:\Thesis app\phyphox\ethics commitee\Ethics BKK Last version  (AutoRecovered)_modified.docx")
doc = Document(str(p))

keywords = [
    "MediaPipe Pose Landmarker",
    "Phyphox",
    "Birincil sonuç ölçütü",
    "Kinematik parametreler",
    "Ulaşma–Dönüş görevi",
    "Çalışmanın birincil sonucu",
    "Anlık kinematik değişiklikleri",
    "Birincil Sonuç Ölçütü",
    "SPARC hesaplamasında",
    "Gövde kompanzasyonu",
    "Omuz elevasyonu",
    "Dirsek açısı",
    "Hareket süresi",
    "Tepe hız",
    "Veri Toplama Yöntemleri",
    "Sistem kalibrasyonunun ardından",
    "19. Staacks",
]

out = open(r"C:\Users\acer\AppData\Local\Temp\opencode\verification_output.txt", "w", encoding="utf-8")
for kw in keywords:
    out.write(f"\n=== {kw} ===\n")
    for p in doc.paragraphs:
        if kw in p.text:
            runs_info = []
            for r in p.runs:
                color = r.font.color.rgb if r.font.color and r.font.color.rgb else "default"
                runs_info.append(f"[{color}]{r.text[:30]}")
            out.write(p.text[:600] + "\n")
            out.write("RUNS: " + " | ".join(runs_info[:6]) + "\n")
            break
out.close()
print("Verification written to C:\\Users\\acer\\AppData\\Local\\Temp\\opencode\\verification_output.txt")
