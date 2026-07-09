from docx import Document
from pathlib import Path

p = Path(r"D:\Thesis app\phyphox\ethics commitee\proposal\Abdelrahman Sabee Proposal (1)_updated.docx")
doc = Document(str(p))

citations = ["(8,14,15)", "(8,14).", "(17,18)."]
out = open(r"C:\Users\acer\AppData\Local\Temp\opencode\proposal_citation_check.txt", "w", encoding="utf-8")
for c in citations:
    out.write(f"\n=== {c} ===\n")
    found = False
    for i, para in enumerate(doc.paragraphs):
        if c in para.text:
            out.write(f"[{i}] {para.text[:400]}\n")
            found = True
            break
    if not found:
        out.write("Not found.\n")
out.close()
print("done")
