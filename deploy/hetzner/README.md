# NeuroLab على Hetzner CX33

السيرفر الجديد: Hetzner Cloud **CX33** (4 vCPU / 8 GB / 80 GB NVMe). يفضل شغال 24 ساعة، من غير نوم Hugging Face.

أنا ما أقدرش أفتح حساب Hetzner بدلًا منك. أنت تعمل السيرفر، وتبعتلي الـ IP. أنا أركّب NeuroLab.

## 1) اعمل السيرفر (حوالي 5 دقايق)

1. افتح صفحة التسجيل: https://accounts.hetzner.com/login ثم **Register now**.
   بعد التسجيل ادخل الكونسول من: https://console.hetzner.com
   (الرابط القديم `console.hetzner.cloud` مش شغال.)
2. سجّل بحساب جديد (إيميل + كارت). لا تستخدم VPN وقت التسجيل.
3. اعمل Project اسمه `NeuroLab`.
4. من القائمة: **Servers** → **Add Server**.
5. اختار كده بالظبط:
   - Location: **Falkenstein** (ألمانيا)
   - Image: **Ubuntu 24.04** أو **Ubuntu 22.04**
   - Type: **CX33** — 4 vCPU, 8 GB RAM, 80 GB (مش CX23)
   - Networking: **IPv4** شغّال
   - SSH key: **Add SSH key** والصق المفتاح اللي تحت
   - Name: `neurolab`
6. اضغط **Create & Buy now**.
7. انسخ **IPv4** (شكلها زي `49.13.xx.xx`).
8. ابعتلي رسالة واحدة:

```
IP: 49.13.xx.xx
```

لو تقدر، ابعت كمان الأسرار من Hugging Face Space → Settings → Variables and secrets:
`JWT_SECRET` و `DB_ENCRYPTION_KEY` و `MFA_ENCRYPTION_KEY`
من غيرهم الحسابات القديمة للعيادة مش هتفتح على السيرفر الجديد.

## 2) المفتاح — انسخ السطر كله

```
ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIAAppVKQrbdX4u2rBbQKZbONBj6+eCGG1Pp0xDbqAn5/ neurolab-hetzner-cursor-agent
```

لو Hetzner سأل عن اسم المفتاح: `cursor-agent`.

## 3) بعد ما تبعت الـ IP

أنا هدخل السيرفر وأركّب التطبيق. الرابط هيبقى:

`http://IP/`

موقع Hugging Face **متقفلوش** لحد ما ننقل بيانات الآيباد والمرضى.

## 4) ترتيب النقل بعد ما السيرفر يشتغل

1. نفتح العيادة على الرابط الجديد ونتأكد إن التحليل شغال.
2. نرفع كاش الفاليديشن من الآيباد (`/sync-ipad`) — لازم من نفس الآيباد.
3. ننسخ ملفات المرضى من Hugging Face.
4. بعد التأكد: الآيباد يستخدم الرابط الجديد بس. Hugging Face يفضل للديمو لو حبيت.
