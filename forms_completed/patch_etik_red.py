# -*- coding: utf-8 -*-
"""Patch ethics form in-place: same layout, changed text in RED."""
import shutil
import time
from pathlib import Path

import pythoncom
import win32com.client

SRC = Path(r"D:\Thesis app\ايتيك كrول\insan-arastirmalari-etik-kurul-basvuru-formu-DOLDURULMUS.docx")
if not SRC.exists():
    SRC = Path(r"D:\Thesis app\ايتيك كرول\insan-arastirmalari-etik-kurul-basvuru-formu-DOLDURULMUS.docx")

OUT = SRC.parent / "insan-arastirmalari-etik-kurul-basvuru-formu-GUNCELLENMIS.docx"
BACKUP = SRC.with_suffix(".docx.orijinal.bak")
WD_RED = 255
MAX_FIND = 240

EXP_BLOCK = """Toplam doz: 60 sn kalibrasyon + 4 × 3 dk eğitim bloğu = ~13 dk. Her 3 dakikalık blok: Watch 45 sn + Imagine 90 sn + Rest 45 sn.

Faz 1 — Kalibrasyon (60 sn):
Amaç: Notice–name–transfer; etkilenmemiş kol ile bir kez yavaş ulaşma, hissi etkilenen tarafa aktarma.
Script (kulaklık): "Rahat oturun, sırtınızı sandalyeye yaslayın. İki ayağınız yere bassın. Etkilenen elinizi avucunuz açık şekilde uyluğunuzda dinlendirin. Şimdi etkilenmemiş kolunuzla bir kez yavaşça öne uzanın — bir bardağa uzanır gibi. Nasıl hissettiğinize dikkat edin. Bu his için tek bir kelime seçin — sabit, kolay veya yumuşak — ve sessizce söyleyin. Gözlerinizi kapatın. Aynı kelimeyi ve hissi etkilenen kolunuza gönderin."

Faz 2 — Eğitim Blokları (4 tekrar):
Her blok aynı Watch → Imagine → Rest sırasını izler.

Blok 1 — Başlatma ve Gövde:
Watch (45 sn): "Elinizi uyluğunuzda bırakın ve ekrana bakın. Etkilenen kolunuzu izleyin. Gövde öne eğilmez; kol kendi başına uzanır."
Imagine (90 sn): "Gözlerinizi kapatın. Gövde sabit; zihninizde hazır deyin. Sonra el yumuşakça ileri başlar; gövde sandalyede kalır."
Rest (45 sn): "Gözlerinizi açın. Sadece dinlenin."

Blok 2 — Omuz Kontrolü:
Watch (45 sn): "Omuz alçak ve gevşek kalır, kulaktan uzak."
Imagine (90 sn): "Omuz ağır ve aşağıda; dirsek açılır, el öne uzanır."
Rest (45 sn): "Gözlerinizi açın ve dinlenin."

Blok 3 — Dirsek + Kronometri:
Watch (45 sn): "Dirsek yumuşakça açılır; kaslar sakin."
Imagine (90 sn): "Dirsek açılır, el ulaşır, kısa durur, uyluğa döner. Frekans seslerini takip edin."
Rest (45 sn): "Gözlerinizi açın. Uzanma hızı rahat mıydı? Evet/hayır."

Blok 4 — Tam Ulaşma–Dönüş + Kronometri:
Watch (45 sn): "El uylukta → ulaşma → duraklama → dönüş."
Imagine (90 sn): "Tam uzanma hayal edin; frekans seslerini takip edin."
Rest (45 sn): "Gözlerinizi açın. Vücut hazır mıydı? Hız doğal mıydı? Evet/hayır. Seans bitti."

Frekans tonları (Blok 3–4): ulaşma (düşük) | duraklama (orta) | dönüş (farklı) | 4 sn sessizlik.

"""

CTRL_BLOCK = """Katılımcılar, motor olmayan imgeleme ve zihinsel arınma protokolünü takip edeceklerdir. Süre ve dikkat yükü deneysel grupla eşleştirilmiştir (~13 dk). Video izleme ve frekans tonları uygulanmaz. 60 sn giriş + 4 blok × 3 dk (Zihinsel Arınma 45 sn + İmgeleme 90 sn + Dinlenme 45 sn). Dinlenme dönemlerinde soru sorulmaz.

Giriş — Zihin Hazırlığı (60 sn): Rahat oturun. Gözlerinizi kapatın. Derin nefes alın ve verin. Düşünceleri bırakın. Hareket, kol veya uzanma hayal etmeyin.

Blok 1 — Nefes ve Zihinsel Arınma: Zihinsel Arınma (45 sn): nefes al… ver… düşünceleri bırakın. İmgeleme (90 sn): sakin gökyüzü veya yumuşak ışık; sahne hareketsiz. Dinlenme (45 sn): gözlerinizi açın, sadece dinlenin.

Blok 2 — Renk ve Işık: Zihinsel Arınma (45 sn): zihni sadeleştirin. İmgeleme (90 sn): sakin renk ve ışık; vücut imgeleri yok. Dinlenme (45 sn): dinlenin.

Blok 3 — Sakin Doğa: Zihinsel Arınma (45 sn): gerginliği bırakın. İmgeleme (90 sn): durgun göl, ağaçlar; donmuş sahne. Dinlenme (45 sn): sadece dinlenin.

Blok 4 — Kapanış: Zihinsel Arınma (45 sn): motor düşünceleri bırakın. İmgeleme (90 sn): Blok 1 veya 3 sahnesini tekrarlayın. Dinlenme (45 sn): sadece dinlenin. Teşekkürler. Seans bitti.

"""

REPLACEMENTS = [
    ("bilişsel ve somatik kontrol", "imgeleme ve zihinsel arınma kontrol"),
    ("Bilişsel ve Somatik Kontrol", "İmgeleme ve Zihinsel Arınma Kontrolü"),
    ("Reach & Wipe — Ulaş-Sil", "Reach & Return — Ulaşma–Dönüş"),
    ("Reach & Wipe", "Reach & Return"),
    ("Ulaş-Sil", "Ulaşma–Dönüş"),
    ("yaklaşık 17 dakika", "yaklaşık 13 dakika"),
    ("(~17 dk)", "(~13 dk)"),
    ("~17 dk", "~13 dk"),
    ("= 17 dk", "= ~13 dk"),
    ("17 dk.", "13 dk."),
    ("5 × 3 dk", "4 × 3 dk"),
    ("5 blok × 3 dk", "4 blok × 3 dk"),
    ("(5 tekrar)", "(4 tekrar)"),
    ("Imagine 75 sn", "Imagine 90 sn"),
    ("Rest 60 sn", "Rest 45 sn"),
    ("Rest / Nöral Dinlenme (60 sn)", "Rest / Nöral Dinlenme (45 sn)"),
    ("forward, wipe, return", "forward, pause, return"),
    ("ulaş… sil… dön", "ulaş… bekle… dön"),
    ("gerçek havlu altında el", "etkilenen el uylukta dinlenmiş"),
    ("hedef nesneyi (havlu)", "değerlendirme ortamını"),
    ("masaya ulaşıp silme hareketi", "uyluktan öne ulaşma ve uyluğa dönüş hareketi"),
    ("Silme Fazı (Pürüzsüzlük):", "Dönüş Fazı (Pürüzsüzlük):"),
    ("Yana silme, koordineli dirsek ve el hareketi gerektirir.", "Ulaşma sonrası yumuşak dönüş, koordineli dirsek fleksiyonu gerektirir."),
    ("Bir yüzeye ulaşıp temizleme yeteneği", "Uyluktan hedefe ulaşıp kontrollü dönüş yeteneği"),
]

BLOCKS = [
    (
        "Toplam doz: 2 dk kalibrasyon + 5 × 3 dk eğitim bloğu = 17 dk.",
        "Müdahale Uyumu:",
        EXP_BLOCK,
    ),
    (
        "Katılımcılar, motor olmayan bilişsel sistemi uyararak",
        "PETTLEP Çerçevesinin Uygulanması:",
        CTRL_BLOCK,
    ),
    (
        "birincil sonuç (smoothness_pause_pct) değiştirilmemiştir.",
        "  (Ayrıntılı olarak yazılmalıdır.)",
        "birincil sonuç (smoothness_pause_pct) değiştirilmemiştir. Ek revizyon: motor görev Reach & Return (ulaşma–dönüş); deneysel müdahale 4 blok × 3 dk (~13 dk); kontrol koşulu imgeleme + zihinsel arınma.",
    ),
]


def red_replace_all(doc, old: str, new: str) -> int:
    if len(old) > MAX_FIND or len(new) > MAX_FIND:
        return -1
    rng = doc.Content
    f = rng.Find
    f.ClearFormatting()
    f.Replacement.ClearFormatting()
    f.Text = old
    f.Replacement.Text = new
    f.Replacement.Font.Color = WD_RED
    f.Forward = True
    f.Wrap = 1
    f.Format = False
    f.MatchCase = False
    return f.Execute(Replace=2)


def replace_block(doc, start_text: str, end_text: str, new_text: str) -> bool:
    doc.Content.Find.ClearFormatting()
    start_rng = doc.Content
    f = start_rng.Find
    f.Text = start_text
    f.Forward = True
    f.Wrap = 0
    if not f.Execute():
        return False
    sp = start_rng.Start
    end_rng = doc.Range(sp, doc.Content.End)
    f2 = end_rng.Find
    f2.Text = end_text
    f2.Forward = True
    f2.Wrap = 0
    if not f2.Execute():
        return False
    block = doc.Range(sp, end_rng.Start)
    block.Text = new_text + "\r"
    block.Font.Color = WD_RED
    return True


def main():
    if not SRC.exists():
        raise FileNotFoundError(SRC)
    if not BACKUP.exists():
        shutil.copy2(SRC, BACKUP)
    shutil.copy2(BACKUP, OUT)

    pythoncom.CoInitialize()
    word = win32com.client.Dispatch("Word.Application")
    word.Visible = False
    word.DisplayAlerts = 0
    log = []
    try:
        doc = word.Documents.Open(str(OUT.resolve()), AddToRecentFiles=False)
        time.sleep(2)

        for old, new in REPLACEMENTS:
            n = red_replace_all(doc, old, new)
            log.append(f"replace '{old[:40]}...' -> {n}")

        for start, end, text in BLOCKS:
            ok = replace_block(doc, start, end, text)
            log.append(f"block {start[:30]} -> {ok}")

        # Add reference if missing
        ref = "14. Di Rienzo F, et al. Motor imagery training in stroke: a systematic review. Front Hum Neurosci. 2016."
        if "Di Rienzo" not in doc.Content.Text:
            rng = doc.Content
            rng.Find.Text = "13. Schuster C"
            if rng.Find.Execute():
                ins = doc.Range(rng.End, rng.End)
                ins.InsertAfter("\r" + ref)
                ins.Font.Color = WD_RED
                log.append("added ref 14")

        doc.Save()
        doc.Close()
    finally:
        word.Quit()
        pythoncom.CoUninitialize()

    log_path = OUT.parent / "_patch_red_log.txt"
    log_path.write_text("\n".join(log), encoding="utf-8")
    print("DONE", OUT)
    print("\n".join(log))


if __name__ == "__main__":
    main()
