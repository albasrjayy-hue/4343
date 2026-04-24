# Delivery Organizer — منظم التقارير

أداة لإعادة تنظيم كشوفات التوصيل — تجمع الطلبات حسب المتجر وترتبها حسب العنوان.
يدعم اللغة العربية الكاملة مع RTL صحيح.

## الهيكل

```
project/
├── server/
│   ├── app.js              ← الخادم (بدون مكتبات npm خارجية)
│   ├── routes/process.js   ← مسارات API
│   └── utils/runner.js     ← يشغّل Python
├── python/
│   └── generate_pdf.py     ← يقرأ PDF وينتج PDF منظّم بعربي صحيح
├── public/                 ← الواجهة الأمامية
├── uploads/
├── outputs/
├── package.json
└── requirements.txt
```

## المتطلبات

### Python
```bash
pip install pdfplumber reportlab
```

### wkhtmltopdf (للعربية الصحيحة)
```bash
# Ubuntu/Debian:
sudo apt-get install wkhtmltopdf

# أو تحميل من: https://wkhtmltopdf.org/downloads.html
```

## التشغيل

```bash
# لا يحتاج npm install (لا توجد مكتبات خارجية)
npm run dev
# أو:
node server/app.js
```

ثم افتح المتصفح على: **http://localhost:3000**

## مميزات الإخراج
- ✅ عربية صحيحة مع RTL
- ✅ مرتّب حسب المتجر ثم العنوان
- ✅ نفس تنسيق الملف الأصلي (رأس أزرق، صفوف متبادلة)
- ✅ ملخص لكل متجر (عدد الطلبات + الإجمالي)
- ✅ ملخص كامل في الأسفل
