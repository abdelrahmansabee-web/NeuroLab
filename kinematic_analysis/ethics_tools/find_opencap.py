from docx import Document
from pathlib import Path

p = Path(r"D:\Thesis app\phyphox\ethics commitee\proposal\Abdelrahman Sabee Proposal (1)_BACKUP.docx")
doc = Document(str(p))
out = open(r"C:\Users\acer\AppData\Local\Temp\opencode\opencap_occurrences.txt", "w", encoding="utf-8")
for i, para in enumerate(doc.paragraphs):
    if 'OpenCap' in para.text or 'OpenSim' in para.text:
        out.write(f"[{i}]\n{para.text}\n\n")
out.close()
print("done")
