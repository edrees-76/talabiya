# طلبية — Talabiya

برنامج سطح مكتب (Windows، عربي، يعمل بلا إنترنت) لتسجيل مشتريات المطاعم اليومية والعهدة النقدية،
بديلاً عن ملف الإكسل اليومي.

## التشغيل من المصدر
```bash
pip install -e .[dev]
python -m talabiya
```
البيانات في `%APPDATA%\Talabiya\talabiya.db` (أو المجلد في المتغير `TALABIYA_HOME`).

## الاختبارات
```bash
python -m pytest tests -q
```

## بيانات تجريبية ولقطات الشاشات
```bash
python scripts/demo_data.py <path-to-new.db>
python scripts/screenshots.py <out-folder> light
```

## البناء والمثبّت
```bash
bash build_exe/build.sh
```
ينتج `build_exe/dist/Talabiya/Talabiya.exe` ثم `installer/Output/Talabiya_Setup_0.1.0.exe`
(يحتاج Inno Setup 6). إلغاء التثبيت لا يحذف قاعدة البيانات ولا النسخ الاحتياطية.

## البنية
- `talabiya/core` — قاعدة البيانات، الحسابات (`ledger`)، العمليات (`repo`)، الدخول، النسخ الاحتياطي.
- `talabiya/gui` — الواجهة (PySide6) والصفحات والطباعة والهوية البصرية.
- `talabiya-brand/` — دليل الهوية، `prototype/` — النموذج الأولي HTML.
