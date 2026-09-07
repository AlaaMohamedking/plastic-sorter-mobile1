# -*- coding: utf-8 -*-
"""
arabic_text.py
Kivy مبيعرفش يشكّل الحروف العربية (يوصلها ببعض) ولا يعكس اتجاهها تلقائياً.
عشان أى نص عربي يظهر صح فى أى Label/Button لازم يمر على الدالة ar() دى قبل ما يتعرض.

يحتاج المكتبتين دول فى requirements بتاع buildozer:
    arabic_reshaper
    python-bidi
"""
try:
    import arabic_reshaper
    from bidi.algorithm import get_display
    _AVAILABLE = True
except Exception:
    _AVAILABLE = False


def ar(text):
    """رجّع النص جاهز للعرض داخل Kivy. استخدمها فى كل مكان بيتعرض فيه نص عربي."""
    if not text:
        return text
    if not _AVAILABLE:
        return text
    try:
        reshaped = arabic_reshaper.reshape(text)
        return get_display(reshaped)
    except Exception:
        return text
