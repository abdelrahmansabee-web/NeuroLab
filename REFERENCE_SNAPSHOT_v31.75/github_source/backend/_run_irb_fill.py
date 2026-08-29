# -*- coding: utf-8 -*-
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _fill_forms import fill_irb_application, OUT, OUT_COPY, TODAY_TR
import shutil

if __name__ == "__main__":
    p = fill_irb_application()
    shutil.copy2(p, OUT_COPY / p.name)
    rev = Path(r"D:\Thesis app\manuscript f\REVIZYON_PAKETI")
    rev.mkdir(exist_ok=True)
    shutil.copy2(p, rev / p.name)
    print(f"OK: {p}")
    print(f"Tarih: {TODAY_TR}")
