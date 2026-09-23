import re
from pathlib import Path
import win32com.client

src = Path(r"D:\Thesis app\manuscript f\forms_completed\insan-arastirmalari-etik-kurul-basvuru-formu-DOLDURULMUS.doc")
out = Path(r"D:\Thesis app\NeuroLab\forms_extract\verify_irb_filled.txt")
out.parent.mkdir(parents=True, exist_ok=True)

word = win32com.client.Dispatch("Word.Application")
word.Visible = False
word.DisplayAlerts = 0
doc = word.Documents.Open(str(src.resolve()), ReadOnly=True)

lines = []
color_runs = []

for pi in range(1, doc.Paragraphs.Count + 1):
    para = doc.Paragraphs(pi)
    pr = para.Range
    full = pr.Text.replace("\r", "").replace("\x07", "")
    if full.strip():
        lines.append(full)
    try:
        idx = 1
        while idx <= pr.Characters.Count:
            ch_rng = pr.Characters(idx)
            col = int(ch_rng.Font.Color)
            if col not in (0, -16777216, 9999999):
                chunk = ""
                while idx <= pr.Characters.Count:
                    cr = pr.Characters(idx)
                    if int(cr.Font.Color) == col:
                        chunk += cr.Text
                        idx += 1
                    else:
                        break
                if chunk.strip() and len(chunk.strip()) > 2:
                    color_runs.append((pi, col, chunk.strip()[:120]))
            else:
                idx += 1
    except Exception:
        pass

text = "\n".join(lines)
out.write_text(text, encoding="utf-8")

audit = out.with_suffix(".colors.txt")
audit_lines = [f"Paragraph {p}: color={c} text={t!r}" for p, c, t in color_runs[:500]]
audit.write_text("\n".join(audit_lines) if audit_lines else "(no non-default colored runs)", encoding="utf-8")

doc.Close(False)
word.Quit()

print(f"Wrote {len(text)} chars, {len(lines)} paragraphs to {out}")
print(f"Color runs: {len(color_runs)}")
