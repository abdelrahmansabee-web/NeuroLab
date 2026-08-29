# NeuroLab — سيرفر سهل (Hostinger)

مش Hetzner. تشتري VPS من Hostinger زي الاستضافة، وتبعتلي الـ IP وكلمة السر. أنا أركّب NeuroLab.

## اعمل السيرفر

1. افتح: https://www.hostinger.com/vps-hosting
2. اشتري **KVM 2** (2 معالج، 8 جيجا رام، 100 جيجا).
3. النظام: **Ubuntu 24.04** (أو 22.04).
4. من لوحة Hostinger انسخ:
   - IP
   - كلمة سر root

5. ابعتلي رسالة واحدة:

```
IP: xx.xx.xx.xx
PASSWORD: ........
```

لو تقدر، ابعت كمان من Hugging Face → Settings → Variables and secrets:
`JWT_SECRET` و `DB_ENCRYPTION_KEY` و `MFA_ENCRYPTION_KEY`

موقع Hugging Face **متقفلوش** لحد ما ننقل بيانات المرضى والآيباد.

بعد التركيب: استخدم `https://<IP>.sslip.io/` لشهادة HTTPS مجانية من غير شراء دومين.


