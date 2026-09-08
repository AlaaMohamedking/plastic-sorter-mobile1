[app]
title = فرز البلاستيك
package.name = plasticsorter
package.domain = org.example

source.dir = .
source.include_exts = py,png,jpg,kv,atlas

version = 1.0

# المكتبات المطلوبة - usb4a/usbserial4a للاتصال بالأردوينو عبر كابل OTG
# arabic_reshaper و python-bidi لعرض النص العربى صح
requirements = python3==3.11.9,kivy,pyjnius,usb4a,usbserial4a,arabic_reshaper,python-bidi

orientation = portrait
fullscreen = 0

icon.filename = %(source.dir)s/icon.png

# الأذونات المطلوبة على أندرويد (إذن USB بيظهر تلقائى وقت الاتصال، مش محتاج فى المانفست)
android.permissions = CAMERA

# نسخة أندرويد المستهدفة (عدّلها لو محتاج نسخة تانية)
android.api = 33
android.minapi = 23
android.ndk = 25b
android.archs = arm64-v8a,armeabi-v7a

# موافقة تلقائية على تراخيص Android SDK (بدونها البناء بيقف على GitHub Actions)
android.accept_sdk_license = True

# مهم: الكاميرا محتاجة هذا السطر عشان تشتغل صح مع بعض مزودى p4a
android.add_src =

[buildozer]
log_level = 2
warn_on_root = 1
