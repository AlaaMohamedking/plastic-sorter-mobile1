[app]

title = فرز البلاستيك
package.name = plasticsorter
package.domain = org.plasticsorter

source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json

version = 1.0.0

requirements = python3,kivy==2.2.1,pyserial

orientation = portrait
fullscreen = 0

permissions = INTERNET,CAMERA,READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE

android.permissions = INTERNET,CAMERA,READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE
android.features = android.hardware.usb.host

android.api = 31
android.minapi = 21
android.ndk = 25b

android.archs = arm64-v8a,armeabi-v7a

android.accept_sdk_license = True

android.entrypoint = org.kivy.android.PythonActivity

[buildozer]

log_level = 2
warn_on_root = 1
