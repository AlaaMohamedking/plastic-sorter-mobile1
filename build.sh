#!/bin/bash
# بناء APK تلقائياً

echo "🔨 جاري البناء..."

# تثبيت المتطلبات
pip install buildozer cython

# البناء
buildozer android debug

# نسخ الملف النهائي
if [ -f "bin/plastic_sorter-1.0.0-debug.apk" ]; then
    echo "✅ تم البناء بنجاح!"
    echo "📦 الملف: bin/plastic_sorter-1.0.0-debug.apk"
else
    echo "❌ فشل البناء"
    exit 1
fi
