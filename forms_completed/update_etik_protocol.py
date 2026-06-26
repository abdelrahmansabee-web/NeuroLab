# -*- coding: utf-8 -*-
"""Update ethics form protocol section — Reach-Return PETTLEP-AOMI (Turkish)."""
import re
import shutil
from pathlib import Path

try:
    import win32com.client
except ImportError as exc:
    raise SystemExit("pip install pywin32") from exc

DOC_PATH = Path(
    r"D:\Thesis app\manuscript f\REVIZYON_PAKETI"
    r"\insan-arastirmalari-etik-kurul-basvuru-formu-DOLDURULMUS.doc"
)
BACKUP = DOC_PATH.with_suffix(".doc.bak")

OLD_TASK_SNIPPETS = [
    "Reach & Wipe",
    "Reach and Wipe",
    "ulaşma-silme",
    "havlu",
    "5 blok",
    "5 blok × 3 dk",
    "Imagine 75 sn",
    "Rest 60 sn",
    "2 dk kalibrasyon",
    "toplam ~17 dk",
    "~17 dk",
    "3 sn ulaş / 3 sn silme / 3 sn dönüş",
    "Beden Taraması / Mekânsal Navigasyon",
]

NEW_PROTOCOL = r"""
Görev: Çapraz vücut ulaşma–dönüş (Reach & Return); etkilenen üst ekstremite ile uyluktan öne ulaşma, kısa duraklama ve uyluğa dönüş. Pre/post değerlendirmede üç deneme, ortalama analiz. Müdahale sırasında fiziksel hareket uygulanmaz.

PETTLEP çerçevesi (Holmes & Collins, 2001):
P (Physical): Gerçek oturma düzeni, normal kıyafet, değerlendirme ile aynı sandalye ve oda düzeni.
E (Environment): Değerlendirme odası ile aynı ortam; tablet ekranında etkilenen tarafın ayna videosu.
T (Task): Çapraz vücut ulaşma–dönüş (Reach & Return); günlük yaşama uygun, tek akıcı hareket dizisi.
T (Timing): Gerçek zamanlı kinestetik motor imgeleme; Blok 3–4’te frekans tonları ile ulaşma–duraklama–dönüş kronometrisi.
L (Learning): Bloklar arası kısa düzeltici rehberlik (gövde sabitliği, omuz kontrolü, dirsek açılımı).
E (Emotion): Rahatlık, güven, doğal kas hissi; “hazır” anından sonra ulaşma.
P (Perspective): Watch aşamasında dış perspektif (3. kişi video); Imagine aşamasında iç perspektif (1. kişi kinestetik MI).

Seans zaman yapısı (toplam ~13 dk; fiziksel uygulama YOK):
• Kalibrasyon (Calibration): 60 sn — notice–name–transfer; etkilenmemiş kol ile bir kez yavaş ulaşma, hissi etkilenen tarafa aktarma.
• 4 eğitim bloku × 3 dk (her blok: Watch 45 sn + Imagine 90 sn + Rest 45 sn).

Blok 1 — Başlatma ve gövde (Initiation + Trunk):
Watch (45 sn): “Elinizi uyluğunuzda bırakın ve ekrana bakın. Kendi kolunuzu — etkilenen tarafı — izliyorsunuz. Önce gövdenin sandalyede nasıl sessiz kaldığına bakın. Gövde öne eğilmez. Sonra el hareket etmeye başlar — sakin ve net, hızlı değil. Kol kendi başına uzanır; vücut onun peşinden gitmez.”
Imagine (90 sn): “Gözlerinizi kapatın. Ayaklar yerde, el uyluğunuzda. Önce vücudunuzun hazırlandığını hissedin — gövde sabit, sırt destekli. Zihninizde hazır deyin. Hareket etmeden önce vücut hazırlanır. Sonra, o hazırlık anından sonra eliniz yumuşakça ileri başlar. Gövdeniz sandalyede geride kalır; sadece kolunuz uzanır. Vücudunuzun öne eğildiğini hayal ederseniz durun ve hazırdan tekrar başlayın.”
Rest (45 sn): “Gözlerinizi açın. Kolunuzu uyluğunuzda bırakın. Normal nefes alın. Şimdi bir şey çalışmayın — sadece dinlenin.”

Blok 2 — Omuz kontrolü (Shoulder Control):
Watch (45 sn): “Ekrandaki omuza bakın. Kol öne uzanırken omuz alçak ve gevşek kalır, kulaktan uzak.”
Imagine (90 sn): “Gözlerinizi kapatın. Omuğunuzun ağır ve aşağıda olduğunu hayal edin — önce yerleşsin. Sonra dirseğiniz açılır ve eliniz öne uzanır. Omuz kulağa kalkmaz; kol hareket ederken sakin ve alçak kalır.”
Rest (45 sn): “Gözlerinizi açın ve dinlenin. Şimdilik hayal kurmayın.”

Blok 3 — Dirsek ve kronometri (Elbow + Chronometry):
Watch (45 sn): “El ilerlerken dirseğin nasıl yumuşakça açıldığını izleyin. Kaslar sakin görünür — sert değil, zorlanmış değil.”
Imagine (90 sn): “Gözlerinizi kapatın. Omuz aşağıda. Kolunuzun önünün yumuşak ve sakin olduğunu hissedin. Dirseğiniz yumuşakça açılır, eliniz önünüzdeki noktaya uzanır, kısa durur, sonra yumuşakça uyluğunuza döner. Lütfen duyduğunuz frekans seslerini takip edin ve hareketi bu ritimle eş zamanlı olarak zihninizde canlandırın.”
Rest + kronometri (45 sn): “Gözlerinizi açın ve dinlenin. Kısa bir soru: o uzanmayı hayal ederken, gerçekten rahat bir uzanma ile aynı hızda mı hissettiniz — çok hızlı değil, donmuş değil? Evet veya hayır diyebilirsiniz.”

Blok 4 — Tam ulaşma–dönüş (Full Reach + Chronometry):
Watch (45 sn): “Tüm hareketi izleyin: el uylukta, öne uzanma, kısa duraklama, uyluğa dönüş. Tek akıcı sıra — önce vücut hazır, sonra kol.”
Imagine (90 sn): “Gözlerinizi kapatın. Aynı sandalye, aynı duruş. Bir tam uzanma hayal edin: vücudunuz hazır ve gövde sabit, omuz aşağı, dirsek yumuşakça açılıyor, el önünüzdeki noktaya uzanıyor, kısa bir duraklama, sonra yumuşakça uyluğunuza dönüş. Zihninizde bir kez daha yapın — aynı sıra, aynı sakin hız. Lütfen duyduğunuz frekans seslerini takip edin ve hareketi bu ritimle eş zamanlı olarak zihninizde canlandırın.”
Rest + kronometri (45 sn): “Gözlerinizi açın ve dinlenin. İki kısa soru. Birincisi: kolunuz hareket etmeden önce vücudunuz hazır hissetti mi? İkincisi: tüm uzanma gerçek zamanlı hızda mıydı — doğal, aceleci değil? Her biri için evet veya hayır. Teşekkürler. Seans bitti.”

Frekans tonları (Blok 3–4, Imagine 90 sn): Düşük ton — ulaşma (uzanma); orta ton — duraklama (bekleme); farklı ton — dönüş; 4 sn tam sessizlik — dinlenme ve bir sonraki deneme için hazırlık.

Kalibrasyon scripti (60 sn):
“Rahat oturun, sırtınızı sandalyeye yaslayın. İki ayağınız yere bassın. Etkilenen elinizi avucunuz açık şekilde uyluğunuzda dinlendirin. Şimdi etkilenmemiş kolunuzla bir kez yavaşça öne uzanın — bir bardağa uzanır gibi. Nasıl hissettiğinize dikkat edin. Belki vücudunuz sabit kalır, belki başlangıç kolay gelir. Bu his için tek bir kelime seçin — sabit, kolay veya yumuşak — ve sessizce söyleyin. Gözlerinizi kapatın. Aynı kelimeyi ve hissi etkilenen kolunuza gönderin; sanki o kol da aynı kalitede hareket edebilirmiş gibi.”

Kontrol koşulu (motor olmayan imgeleme; zaman eşleştirilmiş ~13 dk):
• 60 sn giriş gevşemesi (sandalyede rahat oturma, normal nefes; vücut hareketi veya motor imgeleme YOK).
• 4 blok × 3 dk: Dinleme 45 sn (nötr doğa/manzara sesli betimleme) + Görselleştirme 90 sn (motor olmayan sahne imgeleme: renkler, nesneler, mekân detayları; kol/gövde/ulaşma imgesi YASAK) + Dinlenme 45 sn.
• Aynı kulaklık, oda, sandalye ve seans süresi; yalnızca imgeleme içeriği motor dışıdır (Schuster et al., 2011; Di Rienzo et al., 2016).

Fiziksel Reach & Return yalnızca pre/post değerlendirmede uygulanır.
""".strip()


def replace_protocol_section(full_text: str) -> str:
    """Replace methodology block from Görev/PETTLEP through control paragraph."""
    start_markers = ["Görev:", "Gorev:", "Reach & Wipe", "Reach and Wipe"]
    end_markers = ["Ölçümler:", "Olcumler:", "İstatistik:", "Istatistik:"]

    start = -1
    for m in start_markers:
        idx = full_text.find(m)
        if idx != -1:
            start = idx
            break

    if start == -1:
        # Insert before Ölçümler if Görev missing
        for m in end_markers:
            idx = full_text.find(m)
            if idx != -1:
                return full_text[:idx].rstrip() + "\n\n" + NEW_PROTOCOL + "\n\n" + full_text[idx:]

    end = len(full_text)
    for m in end_markers:
        idx = full_text.find(m, start if start != -1 else 0)
        if idx != -1:
            end = idx
            break

    if start == -1:
        raise RuntimeError("Protocol section markers not found in document.")

    prefix = full_text[:start].rstrip()
    suffix = full_text[end:].lstrip()
    return prefix + "\n\n" + NEW_PROTOCOL + "\n\n" + suffix


def patch_reach_wipe_mentions(text: str) -> str:
    text = text.replace("Reach & Wipe", "Reach & Return (ulaşma–dönüş)")
    text = text.replace("Reach and Wipe", "Reach & Return (ulaşma–dönüş)")
    text = text.replace("reach-wipe", "reach-return")
    text = text.replace("ulaşma-silme", "ulaşma–dönüş")
    text = text.replace("havlu ile masada ulaşma-silme", "uyluktan öne ulaşma ve uyluğa dönüş")
    text = text.replace("gerçek havlu", "gerçek oturma düzeni")
    return text


def main() -> None:
    if not DOC_PATH.exists():
        raise FileNotFoundError(DOC_PATH)

    if not BACKUP.exists():
        shutil.copy2(DOC_PATH, BACKUP)

    word = win32com.client.Dispatch("Word.Application")
    word.Visible = False
    word.DisplayAlerts = 0
    doc = word.Documents.Open(str(DOC_PATH.resolve()))

    original = doc.Content.Text
    updated = replace_protocol_section(original)
    updated = patch_reach_wipe_mentions(updated)

    doc.Content.Text = updated
    doc.Save()
    doc.Close()
    word.Quit()

    # Minimal verification output (no full document dump)
    checks = {s: (s in updated) for s in ["Reach & Return", "4 eğitim bloku", "motor olmayan imgeleme"]}
    removed = {s: (s not in updated) for s in ["Reach & Wipe", "5 blok × 3 dk", "Beden Taraması"]}
    print("UPDATED:", DOC_PATH)
    print("CHECKS:", checks)
    print("REMOVED:", removed)


if __name__ == "__main__":
    main()
