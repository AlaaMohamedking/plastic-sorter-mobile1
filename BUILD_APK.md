# 🚀 تحويل المشروع إلى APK - الخطوات السريعة

## المتطلبات:
- Python 3.10+
- Java 11
- Git

## الخطوات:

### 1. تحميل البرامج
```bash
pip install buildozer cython
```

### 2. تحميل المشروع
```bash
git clone https://github.com/AlaaMohamedking/plastic-sorter-mobile1.git
cd plastic-sorter-mobile1
```

### 3. بناء APK (أهم خطوة!)
```bash
buildozer android debug
```

### 4. الملف النهائي
```
bin/plastic_sorter-1.0.0-debug.apk
```

### 5. التثبيت على Poco X3
```bash
adb install -r bin/plastic_sorter-1.0.0-debug.apk
```

## المشاكل الشائعة:

| المشكلة | الحل |
|--------|------|
| Java غير موجود | حمّل: https://www.oracle.com/java/technologies/javase/jdk11-archive-downloads.html |
| buildozer ما يشتغل | أعد التثبيت: `pip install --upgrade buildozer` |
| APK كبير جداً | طبيعي (50-80 MB) |
| أذونات الكاميرا | وافق عند أول تشغيل |

⏱️ **الوقت:** أول مرة = 30-45 دقيقة | المرات القادمة = أسرع
