# -*- coding: utf-8 -*-
"""
storage.py
حفظ/تحميل إعدادات التطبيق كملف JSON فى مجلد بيانات التطبيق الخاص بالموبايل
(kivy.app.App.user_data_dir بيرجع مسار صحيح سواء على أندرويد أو على الكمبيوتر وقت التطوير)
"""
import os
import json

DEFAULT_SETTINGS = {
    "roi": [140, 100, 60, 60],          # x, y, w, h (بالنسبة لأبعاد معاينة الكاميرا)
    "usb_device_name": "",                # اسم جهاز USB بتاع الأردوينو (يتحفظ بعد أول اتصال ناجح)
    "relay_labels": [
        "مخرج 1", "مخرج 2", "مخرج 3", "مخرج 4", "مخرج 5",
        "الإضاءة", "الهزاز", "AUX",
    ],
    "samples": [],                       # {"name","L","a","b","outlet"}
    "unknown_outlet": 4,
    "tolerance": 12.0,
    "pulse_ms": 400,
    "cooldown_ms": 800,
    "lighting_auto": True,
    "vibrator_enabled": True,
    "aux_label": "AUX",
    "background_lab": None,
    "background_rgb": None,
    "background_threshold": 15.0,
}


def settings_path(app_user_data_dir):
    return os.path.join(app_user_data_dir, "sorter_settings.json")


def load_settings(app_user_data_dir):
    path = settings_path(app_user_data_dir)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            merged = dict(DEFAULT_SETTINGS)
            merged.update(data)
            return merged
        except Exception:
            pass
    return dict(DEFAULT_SETTINGS)


def save_settings(app_user_data_dir, settings):
    path = settings_path(app_user_data_dir)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print("خطأ فى حفظ الإعدادات:", e)
