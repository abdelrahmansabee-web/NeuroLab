# -*- coding: utf-8 -*-
import shutil
from pathlib import Path

from docx import Document

SRC = Path(
    r"D:\Thesis app\manuscript f\REVIZYON_PAKETI"
    r"\insan-arastirmalari-etik-kurul-basvuru-formu-DOLDURULMUS.docx"
)
OUT_DOCX = Path(r"D:\Thesis app\manuscript f\REVIZYON_PAKETI\ETIK_KURUL_FORMU_AC.docx")
OUT_HTML = Path(r"D:\Thesis app\manuscript f\REVIZYON_PAKETI\ETIK_KURUL_FORMU_AC.html")

shutil.copy2(SRC, OUT_DOCX)
doc = Document(SRC)
parts = []
for p in doc.paragraphs:
    t = p.text.strip()
    if not t:
        parts.append("<br>")
        continue
    if p.style.name.startswith("Heading"):
        parts.append(f"<h2>{t}</h2>")
    else:
        parts.append(f"<p>{t}</p>")

html = (
    "<!DOCTYPE html><html><head><meta charset='utf-8'>"
    "<title>Etik Kurul Formu</title>"
    "<style>body{font-family:Segoe UI,Arial;max-width:900px;margin:40px auto;"
    "line-height:1.6;padding:20px}h2{color:#1a365d;margin-top:1.2em}</style>"
    "</head><body>"
    + "".join(parts)
    + "</body></html>"
)
OUT_HTML.write_text(html, encoding="utf-8")
print("OK", OUT_DOCX, OUT_HTML)
