# -*- coding: utf-8 -*-
"""Patch control protocol section into ethics form .doc"""
import shutil
import time
from pathlib import Path

import pythoncom
import win32com.client

SRC = Path(r"D:\Thesis app\manuscript f\REVIZYON_PAKETI\insan-arastirmalari-etik-kurul-basvuru-formu-DOLDURULMUS.doc.bak")
DOC = Path(r"D:\Thesis app\manuscript f\REVIZYON_PAKETI\insan-arastirmalari-etik-kurul-basvuru-formu-DOLDURULMUS.doc")
FALLBACK = Path(r"D:\Thesis app\NeuroLab\forms_completed\insan-arastirmalari-etik-kurul-basvuru-formu-DOLDURULMUS.doc")
ETHICS_TXT = Path(r"D:\Thesis app\manuscript f\REVIZYON_PAKETI\ETIK_FORM_UYGULANACAK_YAKLASIM_GUNCELLENMIS.txt")
LOG = Path(r"D:\Thesis app\NeuroLab\forms_completed\_etik_patch_log.txt")

START = "Kontrol ko\u015fulu"
END = "\u00d6l\u00e7\u00fcmler:"


def load_replacement() -> str:
    text = ETHICS_TXT.read_text(encoding="utf-8")
    i = text.find(START)
    j = text.find(END)
    if i == -1 or j == -1:
        raise RuntimeError("markers missing in ethics txt")
    return text[i:j].rstrip() + "\r\r"


def patch_doc(path: Path) -> bool:
    pythoncom.CoInitialize()
    word = win32com.client.Dispatch("Word.Application")
    word.Visible = False
    word.DisplayAlerts = 0
    try:
        doc = word.Documents.Open(str(path), ReadOnly=False, AddToRecentFiles=False)
        time.sleep(2)
        start_rng = doc.Content
        f = start_rng.Find
        f.Text = START
        f.Forward = True
        f.Wrap = 0
        if not f.Execute():
            return False
        start_pos = start_rng.Start
        end_rng = doc.Range(start_pos, doc.Content.End)
        f2 = end_rng.Find
        f2.Text = END
        f2.Forward = True
        f2.Wrap = 0
        if not f2.Execute():
            return False
        section = doc.Range(start_pos, end_rng.Start)
        section.Text = load_replacement()
        doc.Save()
        doc.Close()
        return True
    finally:
        word.Quit()
        pythoncom.CoUninitialize()


def main():
    out = Path(
        r"D:\Thesis app\NeuroLab\forms_completed"
        r"\insan-arastirmalari-etik-kurul-basvuru-formu-GUNCELLENDI.doc"
    )
    if not out.exists():
        source = SRC if SRC.exists() else FALLBACK
        shutil.copy2(source, out)

    ok = patch_doc(out)
    LOG.write_text(f"patched={ok}\nfile={out}\n", encoding="ascii")


if __name__ == "__main__":
    main()
