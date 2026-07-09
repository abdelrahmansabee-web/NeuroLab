# -*- coding: utf-8 -*-
from docx import Document
from pathlib import Path

src = Path(r"D:\Thesis app\phyphox\ethics commitee\Ethics BKK Last version  (AutoRecovered).docx")
doc = Document(str(src))

for i, para in enumerate(doc.paragraphs):
    text = para.text.strip()
    if text:
        print(f"[{i}] {text[:200]}")
