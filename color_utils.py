# -*- coding: utf-8 -*-
"""
color_utils.py
تحويل RGB -> CIELAB وحساب فرق الألوان (Delta E)
نفس المعادلات المستخدمة فى نسخة سطح المكتب، بدون أى اعتماد خارجى غير Python العادى
(علشان تشتغل جوه تطبيق الموبايل من غير مشاكل مع numpy على أندرويد)
"""


def _inv_gamma(c):
    return ((c + 0.055) / 1.055) ** 2.4 if c > 0.04045 else c / 12.92


def _f(t):
    return t ** (1.0 / 3.0) if t > 0.008856 else (7.787 * t + 16.0 / 116.0)


def rgb_to_lab(rgb):
    r, g, b = [max(0.0, min(255.0, c)) / 255.0 for c in rgb]
    r, g, b = _inv_gamma(r), _inv_gamma(g), _inv_gamma(b)
    x = r * 0.4124564 + g * 0.3575761 + b * 0.1804375
    y = r * 0.2126729 + g * 0.7151522 + b * 0.0721750
    z = r * 0.0193339 + g * 0.1191920 + b * 0.9503041
    xn, yn, zn = 0.95047, 1.0, 1.08883
    x, y, z = x / xn, y / yn, z / zn
    fx, fy, fz = _f(x), _f(y), _f(z)
    L = 116.0 * fy - 16.0
    a = 500.0 * (fx - fy)
    bb = 200.0 * (fy - fz)
    return (L, a, bb)


def delta_e76(lab1, lab2):
    return ((lab1[0] - lab2[0]) ** 2 + (lab1[1] - lab2[1]) ** 2 + (lab1[2] - lab2[2]) ** 2) ** 0.5


def mean_rgb_from_pixels(pixels, width, height, x, y, w, h, channels=4):
    """
    يحسب متوسط RGB لمنطقة (ROI) من مصفوفة بكسلات مسطحة (زى اللى بيرجعها texture.pixels فى Kivy).
    pixels: bytes/bytearray بترتيب RGBA غالباً لكل بكسل.
    """
    x = max(0, min(x, width - 1))
    y = max(0, min(y, height - 1))
    w = max(1, min(w, width - x))
    h = max(1, min(h, height - y))

    total_r = total_g = total_b = 0
    count = 0
    for row in range(y, y + h):
        base_row = row * width * channels
        for col in range(x, x + w):
            idx = base_row + col * channels
            total_r += pixels[idx]
            total_g += pixels[idx + 1]
            total_b += pixels[idx + 2]
            count += 1
    if count == 0:
        return (0.0, 0.0, 0.0)
    return (total_r / count, total_g / count, total_b / count)
