# نسخة احتياطية كاملة — NeuroLab 32.447

التاريخ: 2026-10-03
النسخة الحية: 32.447
الكوميت: 1ddca646e7afe0a467d3068235fb937fe33c6182
ملف الواجهة: frontend/build/static/js/main.2d78f0a2.js
ملف التنسيق: frontend/build/static/css/main.e09ae02f.css

المجلد ده نسخة كاملة من البرنامج الحي على Hugging Face، مع سورس الواجهة اللي بيبنى منها.

ماذا في النسخة دي:
- علامات المرحلة تحت فيديو Validation (Start, Cup, Mouth, Leaves mouth, Table) وبعدها Apply.
- مقابض المرحلة تتحرك مع الإصبع على شريط التقدم أثناء السحب.
- التحكم المختصر في الجزء الأيسر الموسّع، وNVP بعد Apply داخل Start→Cup + Cup→Mouth فقط (من غير Kalman).

سورس الواجهة:
- `_frontend_source`: كود الواجهة اللي اتعمل منه البناء (من شجرة المرحلة؛ كوميت سورس قريب: 13e520a).
  البناء: `cd _frontend_source\frontend` ثم `npm install` ثم `CI=false npm run build`.

المكان:
- على الجهاز: `D:\Thesis app\BACKUPS\raedai-32.447`
- Hugging Face Space (main لم يتغيّر = `1ddca64`):
  - برانش: `cursor/backup-full-v32447`
  - تاجات: `backup-32.447` و `backup/2026-10-03-full-v32.447`
- GitHub: برانش `cursor/backup-full-v32447` + تاج `backup/2026-10-03-full-v32.447`

النسخة السابقة `raedai-32.443` تفضل موجودة في مجلد backups بدون حذف.

قاعدة الاسترجاع: المجلد المحلي أعلاه هو النسخة الكاملة (Space + `_frontend_source`). برانشات/تاجات الريموت مؤشرات على نفس نقطة 32.447؛ لا تلمس `main` الحي.
