# -*- coding: utf-8 -*-
"""Targeted protocol section replace in ethics .doc (preserves form layout)."""
import shutil
import sys
import time
from pathlib import Path

import pythoncom
import win32com.client

DOC_PATH = Path(
    r"D:\Thesis app\NeuroLab\forms_completed"
    r"\insan-arastirmalari-etik-kurul-basvuru-formu-GUNCELLENDI-v2.doc"
)
BACKUP = Path(
    r"D:\Thesis app\manuscript f\REVIZYON_PAKETI"
    r"\insan-arastirmalari-etik-kurul-basvuru-formu-DOLDURULMUS.doc.bak"
)
LOG = Path(r"D:\Thesis app\NeuroLab\forms_completed\_etik_update_log.txt")

START_MARK = "G\u00f6rev:"  # Görev:
END_MARK = "\u00d6l\u00e7\u00fcmler:"  # Ölçümler:

NEW_PROTOCOL = """G\u00f6rev: \u00c7apraz v\u00fccut ula\u015fma\u2013d\u00f6n\u00fc\u015f (Reach & Return); etkilenen \u00fcst ekstremite ile uyluktan \u00f6ne ula\u015fma, k\u0131sa duraklama ve uylu\u011fa d\u00f6n\u00fc\u015f. Pre/post de\u011ferlendirmede \u00fc\u00e7 deneme, ortalama analiz. M\u00fcdahale s\u0131ras\u0131nda fiziksel hareket uygulanmaz.

PETTLEP \u00e7er\u00e7evesi (Holmes & Collins, 2001):
P (Physical): Ger\u00e7ek oturma d\u00fczeni, normal k\u0131yafet, de\u011ferlendirme ile ayn\u0131 sandalye ve oda d\u00fczeni.
E (Environment): De\u011ferlendirme odas\u0131 ile ayn\u0131 ortam; tablet ekran\u0131nda etkilenen taraf\u0131n ayna videosu.
T (Task): \u00c7apraz v\u00fccut ula\u015fma\u2013d\u00f6n\u00fc\u015f (Reach & Return); g\u00fcnl\u00fck ya\u015fama uygun, tek ak\u0131c\u0131 hareket dizisi.
T (Timing): Ger\u00e7ek zamanl\u0131 kinestetik motor imgeleme; Blok 3\u20134'te frekans tonlar\u0131 ile ula\u015fma\u2013duraklama\u2013d\u00f6n\u00fc\u015f kronometrisi.
L (Learning): Bloklar aras\u0131 k\u0131sa d\u00fczeltici rehberlik (g\u00f6vde sabitli\u011fi, omuz kontrol\u00fc, dirsek a\u00e7\u0131l\u0131m\u0131).
E (Emotion): Rahatl\u0131k, g\u00fcven, do\u011fal kas hissi; "haz\u0131r" an\u0131ndan sonra ula\u015fma.
P (Perspective): Watch a\u015famas\u0131nda d\u0131\u015f perspektif (3. ki\u015fi video); Imagine a\u015famas\u0131nda i\u00e7 perspektif (1. ki\u015fi kinestetik MI).

Seans zaman yap\u0131s\u0131 (toplam ~13 dk; fiziksel uygulama YOK):
\u2022 Kalibrasyon (Calibration): 60 sn \u2014 notice\u2013name\u2013transfer; etkilenmemi\u015f kol ile bir kez yava\u015f ula\u015fma, hissi etkilenen tarafa aktarma.
\u2022 4 e\u011fitim bloku \u00d7 3 dk (her blok: Watch 45 sn + Imagine 90 sn + Rest 45 sn).

Blok 1 \u2014 Ba\u015flatma ve g\u00f6vde (Initiation + Trunk):
Watch (45 sn): "Elinizi uylu\u011funuzda b\u0131rak\u0131n ve ekrana bak\u0131n. Kendi kolunuzu \u2014 etkilenen taraf\u0131 \u2014 izliyorsunuz. \u00d6nce g\u00f6vdenin sandalyede nas\u0131l sessiz kald\u0131\u011f\u0131na bak\u0131n. G\u00f6vde \u00f6ne e\u011filmez. Sonra el hareket etmeye ba\u015flar \u2014 sakin ve net, h\u0131zl\u0131 de\u011fil. Kol kendi ba\u015f\u0131na uzan\u0131r; v\u00fccut onun pe\u015finden gitmez."
Imagine (90 sn): "G\u00f6zlerinizi kapat\u0131n. Ayaklar yerde, el uylu\u011funuzda. \u00d6nce v\u00fccudunuzun haz\u0131rland\u0131\u011f\u0131n\u0131 hissedin \u2014 g\u00f6vde sabit, s\u0131rt destekli. Zihninizde haz\u0131r deyin. Hareket etmeden \u00f6nce v\u00fccut haz\u0131rlan\u0131r. Sonra, o haz\u0131rl\u0131k an\u0131ndan sonra eliniz yumu\u015fak\u00e7a ileri ba\u015flar. G\u00f6vdeniz sandalyede geride kal\u0131r; sadece kolunuz uzan\u0131r. V\u00fccudunuzun \u00f6ne e\u011fildi\u011fini hayal ederseniz durun ve haz\u0131rdan tekrar ba\u015flay\u0131n."
Rest (45 sn): "G\u00f6zlerinizi a\u00e7\u0131n. Kolunuzu uylu\u011funuzda b\u0131rak\u0131n. Normal nefes al\u0131n. \u015eimdi bir \u015fey \u00e7al\u0131\u015fmay\u0131n \u2014 sadece dinlenin."

Blok 2 \u2014 Omuz kontrol\u00fc (Shoulder Control):
Watch (45 sn): "Ekrandaki omuza bak\u0131n. Kol \u00f6ne uzan\u0131rken omuz al\u00e7ak ve gev\u015fek kal\u0131r, kulaktan uzak."
Imagine (90 sn): "G\u00f6zlerinizi kapat\u0131n. Omu\u011funuzun a\u011f\u0131r ve a\u015fa\u011f\u0131da oldu\u011funu hayal edin \u2014 \u00f6nce yerle\u015fsin. Sonra dirse\u011finiz a\u00e7\u0131l\u0131r ve eliniz \u00f6ne uzan\u0131r. Omuz kula\u011fa kalkmaz; kol hareket ederken sakin ve al\u00e7ak kal\u0131r."
Rest (45 sn): "G\u00f6zlerinizi a\u00e7\u0131n ve dinlenin. \u015eimdilik hayal kurmay\u0131n."

Blok 3 \u2014 Dirsek ve kronometri (Elbow + Chronometry):
Watch (45 sn): "El ilerlerken dirse\u011fin nas\u0131l yumu\u015fak\u00e7a a\u00e7\u0131ld\u0131\u011f\u0131n\u0131 izleyin. Kaslar sakin g\u00f6r\u00fcn\u00fcr \u2014 sert de\u011fil, zorlanm\u0131\u015f de\u011fil."
Imagine (90 sn): "G\u00f6zlerinizi kapat\u0131n. Omuz a\u015fa\u011f\u0131da. Kolunuzun \u00f6n\u00fcn\u00fcn yumu\u015fak ve sakin oldu\u011funu hissedin. Dirse\u011finiz yumu\u015fak\u00e7a a\u00e7\u0131l\u0131r, eliniz \u00f6n\u00fcn\u00fczdeki noktaya uzan\u0131r, k\u0131sa durur, sonra yumu\u015fak\u00e7a uylu\u011funuza d\u00f6ner. L\u00fctfen duydu\u011funuz frekans seslerini takip edin ve hareketi bu ritimle e\u015f zamanl\u0131 olarak zihninizde canland\u0131r\u0131n."
Rest + kronometri (45 sn): "G\u00f6zlerinizi a\u00e7\u0131n ve dinlenin. K\u0131sa bir soru: o uzanmay\u0131 hayal ederken, ger\u00e7ekten rahat bir uzanma ile ayn\u0131 h\u0131zda m\u0131 hissettiniz \u2014 \u00e7ok h\u0131zl\u0131 de\u011fil, donmu\u015f de\u011fil? Evet veya hay\u0131r diyebilirsiniz."

Blok 4 \u2014 Tam ula\u015fma\u2013d\u00f6n\u00fc\u015f (Full Reach + Chronometry):
Watch (45 sn): "T\u00fcm hareketi izleyin: el uylukta, \u00f6ne uzanma, k\u0131sa duraklama, uylu\u011fa d\u00f6n\u00fc\u015f. Tek ak\u0131c\u0131 s\u0131ra \u2014 \u00f6nce v\u00fccut haz\u0131r, sonra kol."
Imagine (90 sn): "G\u00f6zlerinizi kapat\u0131n. Ayn\u0131 sandalye, ayn\u0131 duru\u015f. Bir tam uzanma hayal edin: v\u00fccudunuz haz\u0131r ve g\u00f6vde sabit, omuz a\u015fa\u011f\u0131, dirsek yumu\u015fak\u00e7a a\u00e7\u0131l\u0131yor, el \u00f6n\u00fcn\u00fczdeki noktaya uzan\u0131yor, k\u0131sa bir duraklama, sonra yumu\u015fak\u00e7a uylu\u011funuza d\u00f6n\u00fc\u015f. Zihninizde bir kez daha yap\u0131n \u2014 ayn\u0131 s\u0131ra, ayn\u0131 sakin h\u0131z. L\u00fctfen duydu\u011funuz frekans seslerini takip edin ve hareketi bu ritimle e\u015f zamanl\u0131 olarak zihninizde canland\u0131r\u0131n."
Rest + kronometri (45 sn): "G\u00f6zlerinizi a\u00e7\u0131n ve dinlenin. \u0130ki k\u0131sa soru. Birincisi: kolunuz hareket etmeden \u00f6nce v\u00fccudunuz haz\u0131r hissetti mi? \u0130kincisi: t\u00fcm uzanma ger\u00e7ek zamanl\u0131 h\u0131zda m\u0131yd\u0131 \u2014 do\u011fal, aceleci de\u011fil? Her biri i\u00e7in evet veya hay\u0131r. Te\u015fekk\u00fcrler. Seans bitti."

Frekans tonlar\u0131 (Blok 3\u20134, Imagine 90 sn): D\u00fc\u015f\u00fck ton \u2014 ula\u015fma (uzanma); orta ton \u2014 duraklama (bekleme); farkl\u0131 ton \u2014 d\u00f6n\u00fc\u015f; 4 sn tam sessizlik \u2014 dinlenme ve bir sonraki deneme i\u00e7in haz\u0131rl\u0131k.

Kalibrasyon scripti (60 sn):
"Rahat oturun, s\u0131rt\u0131n\u0131z\u0131 sandalyeye yaslay\u0131n. \u0130ki aya\u011f\u0131n\u0131z yere bass\u0131n. Etkilenen elinizi avucunuz a\u00e7\u0131k \u015fekilde uylu\u011funuzda dinlendirin. \u015eimdi etkilenmemi\u015f kolunuzla bir kez yava\u015f\u00e7a \u00f6ne uzan\u0131n \u2014 bir barda\u011fa uzan\u0131r gibi. Nas\u0131l hissetti\u011finize dikkat edin. Belki v\u00fccudunuz sabit kal\u0131r, belki ba\u015flang\u0131\u00e7 kolay gelir. Bu his i\u00e7in tek bir kelime se\u00e7in \u2014 sabit, kolay veya yumu\u015fak \u2014 ve sessizce s\u00f6yleyin. G\u00f6zlerinizi kapat\u0131n. Ayn\u0131 kelimeyi ve hissi etkilenen kolunuza g\u00f6nderin; sanki o kol da ayn\u0131 kalitede hareket edebilirmi\u015f gibi."

Kontrol ko\u015fulu (motor olmayan imgeleme; zaman e\u015fle\u015ftirilmi\u015f ~13 dk):
\u2022 60 sn giri\u015f gev\u015femesi (sandalyede rahat oturma, normal nefes; v\u00fccut hareketi veya motor imgeleme YOK).
\u2022 4 blok \u00d7 3 dk: Dinleme 45 sn (n\u00f6tr do\u011fa/manzara betimlemesi) + G\u00f6rselle\u015ftirme 90 sn (motor olmayan sahne imgeleme: renkler, nesneler, mek\u00e2n detaylar\u0131; kol/g\u00f6vde/ula\u015fma imgesi YASAK) + Dinlenme 45 sn.
\u2022 Ayn\u0131 kulakl\u0131k, oda, sandalye ve seans s\u00fcresi; yaln\u0131zca imgeleme i\u00e7eri\u011fi motor d\u0131\u015f\u0131d\u0131r (Schuster et al., 2011; Di Rienzo et al., 2016).

Fiziksel Reach & Return yaln\u0131zca pre/post de\u011ferlendirmede uygulan\u0131r."""

REPLACEMENTS = [
    ("Reach & Wipe", "Reach & Return (ula\u015fma\u2013d\u00f6n\u00fc\u015f)"),
    ("ula\u015fma-silme", "ula\u015fma\u2013d\u00f6n\u00fc\u015f"),
    ("havlu ile masada ula\u015fma-silme", "uyluktan \u00f6ne ula\u015fma ve uylu\u011fa d\u00f6n\u00fc\u015f"),
    ("ger\u00e7ek havlu", "ger\u00e7ek oturma d\u00fczeni"),
    ("toplam ~17 dk", "toplam ~13 dk"),
    ("~17 dk e\u015fle\u015ftirilmi\u015f", "~13 dk e\u015fle\u015ftirilmi\u015f"),
    ("5 blok \u00d7 3 dk", "4 blok \u00d7 3 dk"),
    ("Imagine 75 sn", "Imagine 90 sn"),
    ("Rest 60 sn", "Rest 45 sn"),
    ("2 dk kalibrasyon", "60 sn kalibrasyon"),
]


def log(msg: str) -> None:
    with LOG.open("a", encoding="ascii", errors="replace") as fh:
        fh.write(msg + "\n")


def find_start(doc, needle: str):
    rng = doc.Content
    f = rng.Find
    f.ClearFormatting()
    f.Text = needle
    f.Forward = True
    f.Wrap = 0
    if f.Execute():
        return rng.Start
    return None


def replace_section(doc, start_needle: str, end_needle: str, new_text: str) -> bool:
    start = find_start(doc, start_needle)
    if start is None:
        return False
    end_rng = doc.Range(start, doc.Content.End)
    f = end_rng.Find
    f.ClearFormatting()
    f.Text = end_needle
    f.Forward = True
    f.Wrap = 0
    if not f.Execute():
        return False
    section = doc.Range(start, end_rng.Start)
    section.Text = new_text + "\r"
    return True


def global_replace(doc, old: str, new: str) -> None:
    rng = doc.Content
    f = rng.Find
    f.ClearFormatting()
    f.Replacement.ClearFormatting()
    f.Text = old
    f.Replacement.Text = new
    f.Forward = True
    f.Wrap = 1
    f.Execute(Replace=2)


def com_retry(fn, attempts=5, delay=1.0):
    last = None
    for _ in range(attempts):
        try:
            return fn()
        except Exception as exc:
            last = exc
            time.sleep(delay)
    raise last


def main() -> None:
    LOG.write_text("start\n", encoding="ascii")
    if not DOC_PATH.exists():
        shutil.copy2(BACKUP, DOC_PATH)

    pythoncom.CoInitialize()
    word = win32com.client.gencache.EnsureDispatch("Word.Application")
    word.Visible = False
    word.DisplayAlerts = 0

    try:
        doc = com_retry(
            lambda: word.Documents.Open(
                str(DOC_PATH.resolve()),
                ConfirmConversions=False,
                ReadOnly=False,
                AddToRecentFiles=False,
            )
        )
        log(f"opened type={type(doc).__name__}")

        ok = com_retry(lambda: replace_section(doc, START_MARK, END_MARK, NEW_PROTOCOL))
        log(f"section_replaced={ok}")
        if not ok:
            raise RuntimeError("protocol section not found")

        for old, new in REPLACEMENTS:
            com_retry(lambda o=old, n=new: global_replace(doc, o, n))

        com_retry(doc.Save)
        doc.Close()
        log("saved")
    finally:
        word.Quit()
        pythoncom.CoUninitialize()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        log(f"error={exc!r}")
        sys.exit(1)
