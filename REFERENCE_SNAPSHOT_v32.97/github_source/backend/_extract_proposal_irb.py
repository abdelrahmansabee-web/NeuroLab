# -*- coding: utf-8 -*-
from docx import Document
from pathlib import Path

doc = Document(r"D:\Thesis app\manuscript f\Abdelrahman Sabee Proposal .docx")
keys = [
    "Inclusion", "Exclusion", "MAS", "MMSE", "28", "Research Question",
    "smoothness", "17 minute", "45 s", "Biruni", "WMFT", "KVIQ", "Statistical",
    "Sample Size", "Participants", "Intervention", "Control",
]
lines = []
for i, p in enumerate(doc.paragraphs):
    t = p.text.strip()
    if not t:
        continue
    if any(k.lower() in t.lower() for k in keys):
        lines.append(f"{i}|{t[:300]}")
Path(r"D:\Thesis app\NeuroLab\forms_extract\_proposal_for_irb.txt").write_text(
    "\n".join(lines), encoding="utf-8"
)
print(len(lines))
