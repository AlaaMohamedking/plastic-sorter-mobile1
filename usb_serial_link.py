# -*- coding: utf-8 -*-
"""
usb_serial_link.py
اتصال USB مباشر (Serial عبر كابل OTG) مع الأردوينو Mega — بديل البلوتوث بالكامل.
الموبايل هنا بيشتغل زى ما الكمبيوتر كان شغال بالظبط: نفس بروتوكول الأوامر
    R:<idx>:<0/1>   تشغيل/إيقاف ريليه رقم idx
    P:<idx>:<ms>    نبضة على ريليه رقم idx لمدة ms
    A               إيقاف كل الريليهات فوراً

يعتمد على مكتبتين بايثون خاصتين بأندرويد (لازم تتضاف فى buildozer.spec):
    usb4a
    usbserial4a

المتطلبات على الهاردوير:
    - كابل OTG (USB-C أو Micro-USB حسب موبايلك) لتوصيل الموبايل بمنفذ USB بتاع الأردوينو Mega مباشرة.
    - الموبايل لازم يدعم وضع USB Host (أغلب موبايلات أندرويد الحديثة بتدعمه).

لو شغال على الكمبيوتر وقت التطوير (من غير أندرويد) هيشتغل فى "وضع محاكاة"
بحيث تقدر تجرب الواجهة من غير أردوينو حقيقى متوصل.
"""
import threading

BAUD_RATE = 115200

try:
    from usb4a import usb
    from usbserial4a import serial4a
    ANDROID = True
except Exception:
    ANDROID = False


class UsbSerialLink:
    def __init__(self, log_callback=None):
        self.log_callback = log_callback or (lambda msg: None)
        self.serial_port = None
        self.lock = threading.Lock()
        self._connected = False
        self._simulated = not ANDROID

    # ------------------------------------------------------------------
    def list_devices(self):
        """يرجع [(اسم_للعرض, device_name), ...] لكل أجهزة USB المتوصلة دلوقتى بكابل OTG"""
        if self._simulated:
            return [("محاكاة (بدون أندرويد)", "SIM")]
        try:
            devices = usb.get_usb_device_list()
            result = []
            for d in devices:
                name = "{} (VID:{} PID:{})".format(
                    d.getDeviceName(), d.getVendorId(), d.getProductId())
                result.append((name, d.getDeviceName()))
            if not result:
                self.log_callback("مفيش أى جهاز USB متوصل — وصّل كابل OTG بالأردوينو")
            return result
        except Exception as e:
            self.log_callback("خطأ فى قراءة أجهزة USB: {}".format(e))
            return []

    # ------------------------------------------------------------------
    def connect(self, device_name):
        if self._simulated:
            self._connected = True
            self.log_callback("(محاكاة) تم الاتصال بـ {}".format(device_name))
            return
        try:
            device = usb.get_usb_device(device_name)
            if device is None:
                raise RuntimeError("الجهاز مش موجود، حاول تحدّث القائمة تانى")

            if not usb.has_usb_permission(device):
                # هيظهر تنبيه أذونات من أندرويد نفسه؛ المستخدم لازم يوافق ثم يضغط اتصال تانى
                usb.request_usb_permission(device)
                self.log_callback("وافق على إذن USB اللي هيظهر، وبعدين اضغط اتصال تانى")
                return

            self.serial_port = serial4a.get_serial_port(
                device_name, BAUD_RATE, 8, 1, 0  # baudrate, databits, stopbits, parity(0=None)
            )
            if self.serial_port is None or not self.serial_port.isOpen():
                raise RuntimeError("تعذر فتح منفذ USB")
            self._connected = True
            self.log_callback("تم الاتصال بالأردوينو عبر USB ({})".format(device_name))
        except Exception as e:
            self._connected = False
            self.log_callback("فشل الاتصال بـ USB: {}".format(e))
            raise

    def disconnect(self):
        self._connected = False
        if self._simulated:
            self.log_callback("(محاكاة) تم قطع الاتصال")
            return
        try:
            if self.serial_port is not None:
                self.serial_port.close()
        except Exception:
            pass
        self.serial_port = None
        self.log_callback("تم قطع الاتصال بالأردوينو")

    @property
    def is_connected(self):
        return self._connected

    # ------------------------------------------------------------------
    def _send(self, line):
        if not self._connected:
            return
        if self._simulated:
            self.log_callback("(محاكاة) إرسال: {}".format(line))
            return
        with self.lock:
            try:
                data = (line + "\n").encode("ascii", errors="ignore")
                self.serial_port.write(data)
            except Exception as e:
                self.log_callback("خطأ إرسال USB: {}".format(e))
                self._connected = False

    def set_relay(self, idx, on):
        self._send("R:{}:{}".format(idx, 1 if on else 0))

    def pulse_relay(self, idx, ms):
        self._send("P:{}:{}".format(idx, int(ms)))

    def all_stop(self):
        self._send("A")
