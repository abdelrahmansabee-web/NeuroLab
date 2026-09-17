# -*- coding: utf-8 -*-
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

WNS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
p = Path(r"D:\Thesis app\manuscript f\Abdelrahman Sabee Proposal (1).docx")
with zipfile.ZipFile(p) as z:
    root = ET.fromstring(z.read("word/document.xml"))
lines = []
for i, sdt in enumerate(root.iter(f"{WNS}sdt")):
    t = "".join(x.text or "" for x in sdt.iter(f"{WNS}t"))
    tag = sdt.find(f".//{WNS}tag")
    alias = sdt.find(f".//{WNS}alias")
    lines.append(f"SDT {i} tag={tag.get(f'{WNS}val') if tag is not None else None} alias={alias.get(f'{WNS}val') if alias is not None else None}")
    lines.append(t[:500])
    lines.append("---")
Path(r"D:\Thesis app\NeuroLab\forms_extract\proposal_sdts.txt").write_text("\n".join(lines), encoding="utf-8")
