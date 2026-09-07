# -*- coding: utf-8 -*-
"""
main.py — نظام فرز البلاستيك بالألوان (نسخة الموبايل)
Kivy + كاميرا الموبايل + اتصال USB مباشر (كابل OTG) بالأردوينو Mega
نفس بروتوكول أوامر النسخة المكتبية بالظبط: R:idx:0/1 | P:idx:ms | A
"""
import time

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.spinner import Spinner
from kivy.uix.slider import Slider
from kivy.uix.checkbox import CheckBox
from kivy.uix.popup import Popup
from kivy.uix.tabbedpanel import TabbedPanel, TabbedPanelItem
from kivy.uix.camera import Camera
from kivy.graphics import Color, Line

from color_utils import rgb_to_lab, delta_e76, mean_rgb_from_pixels
from storage import load_settings, save_settings
from usb_serial_link import UsbSerialLink
from arabic_text import ar

RELAY_COUNT = 8
LIGHT_INDEX = 5
VIBRATOR_INDEX = 6
AUX_INDEX = 7

# طلب أذونات أندرويد وقت التشغيل (الكاميرا بس - إذن USB بيظهر تلقائى من النظام
# لما توصل كابل OTG وتحاول تتصل، مش محتاج إذن مسبق فى المانفست)
try:
    from android.permissions import request_permissions, Permission
    request_permissions([Permission.CAMERA])
except Exception:
    pass


def lbl(text, **kw):
    return Label(text=ar(text), **kw)


def btn(text, **kw):
    return Button(text=ar(text), **kw)


class NameOutletPopup(Popup):
    """نافذة صغيرة لإدخال اسم العينة ورقم المخرج عند التقاط عينة جديدة"""
    def __init__(self, on_confirm, **kw):
        super().__init__(title=ar("عينة جديدة"), size_hint=(0.85, 0.5), **kw)
        self.on_confirm = on_confirm
        root = BoxLayout(orientation="vertical", spacing=10, padding=10)
        root.add_widget(lbl("اسم اللون/العينة:"))
        self.name_input = TextInput(multiline=False, font_name=None)
        root.add_widget(self.name_input)
        root.add_widget(lbl("رقم المخرج (1-5):"))
        self.outlet_spinner = Spinner(text="1", values=[str(i) for i in range(1, 6)])
        root.add_widget(self.outlet_spinner)
        row = BoxLayout(size_hint_y=None, height=48, spacing=10)
        ok = btn("حفظ")
        ok.bind(on_release=self._confirm)
        cancel = btn("إلغاء")
        cancel.bind(on_release=lambda *_: self.dismiss())
        row.add_widget(ok)
        row.add_widget(cancel)
        root.add_widget(row)
        self.content = root

    def _confirm(self, *_):
        name = self.name_input.text.strip()
        if not name:
            return
        outlet = int(self.outlet_spinner.text) - 1
        self.on_confirm(name, outlet)
        self.dismiss()


class SorterApp(App):
    def build(self):
        Window.clearcolor = (0.96, 0.96, 0.96, 1)
        self.title = "فرز البلاستيك - موبايل"

        self.settings = load_settings(self.user_data_dir)
        self.usb = UsbSerialLink(log_callback=self._log)
        self.relay_state = [False] * RELAY_COUNT

        self.latest_rgb = None
        self.latest_lab = None
        self.machine_running = False
        self.sorting_active = False
        self.last_trigger_ms = 0.0

        self.camera_widget = None
        self.roi = list(self.settings["roi"])  # x, y, w, h بالنسبة لعرض/ارتفاع الكاميرا الفعلى

        root = BoxLayout(orientation="vertical")

        self.tabs = TabbedPanel(do_default_tab=False, tab_pos="top_mid")
        self._build_camera_tab()
        self._build_samples_tab()
        self._build_sorting_tab()
        self._build_usb_tab()
        self._build_relays_tab()
        self._build_relay_test_tab()
        self._build_light_tab()
        self._build_vibrator_tab()
        self._build_aux_tab()
        root.add_widget(self.tabs)

        # ---- شريط سفلى ثابت: السجل + زر إيقاف الكل ----
        bottom = BoxLayout(orientation="vertical", size_hint_y=None, height=170)

        self.log_scroll = ScrollView(size_hint_y=None, height=110)
        self.log_label = Label(text="", size_hint_y=None, halign="right", valign="top")
        self.log_label.bind(texture_size=self._update_log_height)
        self.log_scroll.add_widget(self.log_label)
        bottom.add_widget(self.log_scroll)

        stop_btn = Button(text=ar("⛔ إيقاف الكل STOP ALL"), background_color=(0.75, 0.2, 0.2, 1),
                           size_hint_y=None, height=56, bold=True)
        stop_btn.bind(on_release=lambda *_: self._emergency_stop_all())
        bottom.add_widget(stop_btn)

        root.add_widget(bottom)

        Clock.schedule_interval(self._analyze_frame, 0.2)
        return root

    def _update_log_height(self, instance, size):
        instance.height = size[1]
        instance.text_size = (self.log_scroll.width - 10, None)

    def _log(self, msg):
        ts = time.strftime("%H:%M:%S")
        self.log_label.text = "[{}] {}\n".format(ts, msg) + self.log_label.text
        print(msg)

    # ------------------------------------------------------------------
    def _cmd_set_relay(self, idx, on):
        self.usb.set_relay(idx, on)
        self.relay_state[idx] = on
        self._refresh_relay_status()

    def _cmd_pulse_relay(self, idx, ms):
        self.usb.pulse_relay(idx, ms)
        self.relay_state[idx] = True
        self._refresh_relay_status()
        Clock.schedule_once(lambda dt: self._clear_relay(idx), ms / 1000.0)

    def _clear_relay(self, idx):
        self.relay_state[idx] = False
        self._refresh_relay_status()

    def _refresh_relay_status(self):
        if hasattr(self, "relay_status_label"):
            lines = []
            for i in range(RELAY_COUNT):
                state = "يعمل" if self.relay_state[i] else "متوقف"
                lines.append("{}: {}".format(self.settings["relay_labels"][i], state))
            self.relay_status_label.text = ar("\n".join(lines))

    # ------------------------------------------------------------------
    # تبويب الكاميرا
    # ------------------------------------------------------------------
    def _build_camera_tab(self):
        tab = TabbedPanelItem(text=ar("الكاميرا"))
        root = BoxLayout(orientation="vertical", padding=8, spacing=6)

        cam_area = FloatLayout(size_hint_y=0.65)
        try:
            self.camera_widget = Camera(play=True, resolution=(640, 480))
        except Exception as e:
            self.camera_widget = Label(text=ar("تعذر فتح الكاميرا: {}".format(e)))
        cam_area.add_widget(self.camera_widget)

        self.roi_overlay = FloatLayout()
        with self.roi_overlay.canvas:
            Color(0, 1, 0, 1)
            self.roi_line = Line(rectangle=(0, 0, 0, 0), width=2)
        cam_area.add_widget(self.roi_overlay)
        cam_area.bind(size=self._redraw_roi, pos=self._redraw_roi)
        root.add_widget(cam_area)

        info = BoxLayout(size_hint_y=None, height=40)
        self.lab_display = Label(text=ar("L: --  a: --  b: --"))
        info.add_widget(self.lab_display)
        root.add_widget(info)

        bg_row = BoxLayout(size_hint_y=None, height=44, spacing=6)
        cap_bg = btn("📷 التقاط الخلفية (السير فارغ)")
        cap_bg.bind(on_release=lambda *_: self._capture_background())
        bg_row.add_widget(cap_bg)
        root.add_widget(bg_row)

        self.bg_display = lbl("الخلفية: لا يوجد", size_hint_y=None, height=30)
        root.add_widget(self.bg_display)

        thr_row = BoxLayout(size_hint_y=None, height=40)
        thr_row.add_widget(lbl("حساسية اكتشاف القطعة:", size_hint_x=0.5))
        self.bg_threshold_slider = Slider(min=2, max=60, value=self.settings["background_threshold"])
        self.bg_threshold_slider.bind(value=self._on_bg_threshold_change)
        thr_row.add_widget(self.bg_threshold_slider)
        root.add_widget(thr_row)

        note = lbl("ملحوظة: منطقة القراءة (ROI) هى مربع صغير فى نص الشاشة تلقائياً",
                   size_hint_y=None, height=30, font_size=12)
        root.add_widget(note)

        tab.add_widget(root)
        self.tabs.add_widget(tab)
        self._update_background_display()

    def _redraw_roi(self, *_):
        w, h = self.roi_overlay.size
        # مربع الـ ROI فى نص الشاشة، حجمه 25% من أصغر بُعد
        side = min(w, h) * 0.25
        cx, cy = w / 2.0, h / 2.0
        self.roi_line.rectangle = (cx - side / 2, cy - side / 2, side, side)
        self._roi_screen_rect = (cx - side / 2, cy - side / 2, side, side)

    def _capture_background(self):
        if self.latest_lab is None:
            self._log("شغّل الكاميرا ووجّهها على السير فارغ الأول")
            return
        self.settings["background_lab"] = list(self.latest_lab)
        self.settings["background_rgb"] = list(self.latest_rgb) if self.latest_rgb else None
        save_settings(self.user_data_dir, self.settings)
        self._update_background_display()
        self._log("تم تحديد لون الخلفية بنجاح")

    def _on_bg_threshold_change(self, instance, value):
        self.settings["background_threshold"] = value
        save_settings(self.user_data_dir, self.settings)

    def _update_background_display(self):
        bg = self.settings.get("background_lab")
        if bg is None:
            self.bg_display.text = ar("الخلفية: لا يوجد - اضغط التقاط الخلفية")
        else:
            self.bg_display.text = ar("الخلفية: L:{:.1f} a:{:.1f} b:{:.1f}".format(*bg))

    def _analyze_frame(self, dt):
        cam = self.camera_widget
        if not isinstance(cam, Camera) or cam.texture is None:
            return
        try:
            tex = cam.texture
            pixels = tex.pixels
            tw, th = tex.size
            # ROI فى نص الصورة بحجم 25% من أصغر بُعد (نفس نسبة الرسم فى المعاينة)
            side = int(min(tw, th) * 0.25)
            x = int((tw - side) / 2)
            y = int((th - side) / 2)
            r, g, b = mean_rgb_from_pixels(pixels, tw, th, x, y, side, side, channels=4)
            self.latest_rgb = (r, g, b)
            self.latest_lab = rgb_to_lab((r, g, b))
            self.lab_display.text = ar("L: {:.1f}  a: {:.1f}  b: {:.1f}".format(*self.latest_lab))
            self._maybe_trigger_sort()
        except Exception as e:
            print("خطأ تحليل الإطار:", e)

    # ------------------------------------------------------------------
    # تبويب العينات
    # ------------------------------------------------------------------
    def _build_samples_tab(self):
        tab = TabbedPanelItem(text=ar("العينات"))
        root = BoxLayout(orientation="vertical", padding=8, spacing=6)

        add_btn = btn("➕ التقاط عينة جديدة", size_hint_y=None, height=48)
        add_btn.bind(on_release=lambda *_: self._start_capture_sample())
        root.add_widget(add_btn)

        self.samples_scroll = ScrollView()
        self.samples_grid = GridLayout(cols=1, size_hint_y=None, spacing=4)
        self.samples_grid.bind(minimum_height=self.samples_grid.setter("height"))
        self.samples_scroll.add_widget(self.samples_grid)
        root.add_widget(self.samples_scroll)

        tab.add_widget(root)
        self.tabs.add_widget(tab)
        self._refresh_samples()

    def _start_capture_sample(self):
        if self.latest_lab is None:
            self._log("شغّل الكاميرا ووجّهها على العينة أولاً")
            return
        popup = NameOutletPopup(on_confirm=self._save_sample)
        popup.open()

    def _save_sample(self, name, outlet):
        L, a, b = self.latest_lab
        self.settings["samples"].append({"name": name, "L": L, "a": a, "b": b, "outlet": outlet})
        save_settings(self.user_data_dir, self.settings)
        self._refresh_samples()
        self._log("تم حفظ عينة: {}".format(name))

    def _refresh_samples(self):
        self.samples_grid.clear_widgets()
        for i, s in enumerate(self.settings["samples"]):
            row = BoxLayout(size_hint_y=None, height=44, spacing=6)
            row.add_widget(lbl("{}  [مخرج {}]  L:{:.0f} a:{:.0f} b:{:.0f}".format(
                s["name"], s["outlet"] + 1, s["L"], s["a"], s["b"])))
            del_btn = btn("حذف", size_hint_x=0.25)
            del_btn.bind(on_release=lambda _b, idx=i: self._delete_sample(idx))
            row.add_widget(del_btn)
            self.samples_grid.add_widget(row)

    def _delete_sample(self, idx):
        del self.settings["samples"][idx]
        save_settings(self.user_data_dir, self.settings)
        self._refresh_samples()

    # ------------------------------------------------------------------
    # تبويب الفرز
    # ------------------------------------------------------------------
    def _build_sorting_tab(self):
        tab = TabbedPanelItem(text=ar("الفرز"))
        root = BoxLayout(orientation="vertical", padding=8, spacing=8)

        machine_row = BoxLayout(size_hint_y=None, height=52, spacing=6)
        self.machine_status_label = lbl("الماكينة: متوقفة", size_hint_x=0.5)
        machine_row.add_widget(self.machine_status_label)
        start_btn = btn("▶ تشغيل", background_color=(0.1, 0.55, 0.25, 1))
        start_btn.bind(on_release=lambda *_: self._start_machine())
        stop_btn = btn("■ إيقاف", background_color=(0.4, 0.4, 0.4, 1))
        stop_btn.bind(on_release=lambda *_: self._stop_machine())
        machine_row.add_widget(start_btn)
        machine_row.add_widget(stop_btn)
        root.add_widget(machine_row)

        grid = GridLayout(cols=2, size_hint_y=None, height=200, spacing=6)
        grid.add_widget(lbl("مخرج الألوان غير المعروفة (1-5):"))
        self.unknown_outlet_spinner = Spinner(
            text=str(self.settings["unknown_outlet"] + 1), values=[str(i) for i in range(1, 6)])
        grid.add_widget(self.unknown_outlet_spinner)

        grid.add_widget(lbl("مدة النبضة (ms):"))
        self.pulse_input = TextInput(text=str(self.settings["pulse_ms"]), multiline=False, input_filter="int")
        grid.add_widget(self.pulse_input)

        grid.add_widget(lbl("فترة تهدئة بين القطع (ms):"))
        self.cooldown_input = TextInput(text=str(self.settings["cooldown_ms"]), multiline=False, input_filter="int")
        grid.add_widget(self.cooldown_input)

        grid.add_widget(lbl("حد التطابق Delta E:"))
        self.tolerance_slider = Slider(min=1, max=50, value=self.settings["tolerance"])
        grid.add_widget(self.tolerance_slider)
        root.add_widget(grid)

        save_btn = btn("حفظ إعدادات الفرز", size_hint_y=None, height=44)
        save_btn.bind(on_release=lambda *_: self._save_sorting_settings())
        root.add_widget(save_btn)

        auto_row = BoxLayout(size_hint_y=None, height=44)
        self.sorting_active_checkbox = CheckBox()
        self.sorting_active_checkbox.bind(active=lambda _i, v: self._toggle_sorting(v))
        auto_row.add_widget(self.sorting_active_checkbox)
        auto_row.add_widget(lbl("تشغيل الفرز التلقائى"))
        root.add_widget(auto_row)

        root.add_widget(lbl("سجل الفرز:", size_hint_y=None, height=30))
        sort_log_scroll = ScrollView()
        self.sorting_log_label = Label(text="", size_hint_y=None, halign="right", valign="top")
        self.sorting_log_label.bind(texture_size=lambda i, s: setattr(i, "height", s[1]))
        sort_log_scroll.add_widget(self.sorting_log_label)
        root.add_widget(sort_log_scroll)

        tab.add_widget(root)
        self.tabs.add_widget(tab)

    def _start_machine(self):
        if not self.usb.is_connected:
            self._log("وصّل الأردوينو بكابل OTG وافتح تبويب USB الأول")
            return
        if self.settings.get("lighting_auto", True):
            self._cmd_set_relay(LIGHT_INDEX, True)
        if self.settings.get("vibrator_enabled", True):
            self._cmd_set_relay(VIBRATOR_INDEX, True)
        self.sorting_active = True
        self.sorting_active_checkbox.active = True
        self.machine_running = True
        self.machine_status_label.text = ar("الماكينة: تعمل")
        self._log("▶ تم تشغيل الماكينة")

    def _stop_machine(self):
        self.sorting_active = False
        self.sorting_active_checkbox.active = False
        self._cmd_set_relay(VIBRATOR_INDEX, False)
        self._cmd_set_relay(LIGHT_INDEX, False)
        self.machine_running = False
        self.machine_status_label.text = ar("الماكينة: متوقفة")
        self._log("■ تم إيقاف الماكينة")

    def _save_sorting_settings(self):
        self.settings["unknown_outlet"] = int(self.unknown_outlet_spinner.text) - 1
        try:
            self.settings["pulse_ms"] = int(self.pulse_input.text)
        except ValueError:
            pass
        try:
            self.settings["cooldown_ms"] = int(self.cooldown_input.text)
        except ValueError:
            pass
        self.settings["tolerance"] = self.tolerance_slider.value
        save_settings(self.user_data_dir, self.settings)
        self._log("تم حفظ إعدادات الفرز")

    def _toggle_sorting(self, active):
        self.sorting_active = active

    def _maybe_trigger_sort(self):
        if not self.sorting_active or self.latest_lab is None:
            return
        now = time.time() * 1000.0
        if now - self.last_trigger_ms < self.settings["cooldown_ms"]:
            return

        bg = self.settings.get("background_lab")
        if bg is not None:
            if delta_e76(self.latest_lab, tuple(bg)) < self.settings.get("background_threshold", 15.0):
                return  # لسه السير فاضى

        best, best_dist = None, None
        for s in self.settings["samples"]:
            d = delta_e76(self.latest_lab, (s["L"], s["a"], s["b"]))
            if best_dist is None or d < best_dist:
                best, best_dist = s, d

        tol = self.settings["tolerance"]
        if best is not None and best_dist <= tol:
            outlet, name = best["outlet"], best["name"]
        else:
            outlet, name = self.settings["unknown_outlet"], "غير معروف"

        self.last_trigger_ms = now
        self._cmd_pulse_relay(outlet, self.settings["pulse_ms"])
        msg = "{} -> فُتح مخرج {} ({})".format(time.strftime("%H:%M:%S"), outlet + 1, name)
        self._log(msg)
        self.sorting_log_label.text = ar(msg) + "\n" + self.sorting_log_label.text

    # ------------------------------------------------------------------
    # تبويب البلوتوث (Arduino)
    # ------------------------------------------------------------------
    def _build_usb_tab(self):
        tab = TabbedPanelItem(text=ar("USB / الأردوينو"))
        root = BoxLayout(orientation="vertical", padding=8, spacing=10)

        root.add_widget(lbl("وصّل كابل OTG بين الموبايل والأردوينو، وبعدين اضغط تحديث:"))

        self.usb_spinner = Spinner(text=ar("اضغط تحديث"), values=[])
        root.add_widget(self.usb_spinner)

        refresh_btn = btn("تحديث قائمة أجهزة USB")
        refresh_btn.bind(on_release=lambda *_: self._refresh_usb_devices())
        root.add_widget(refresh_btn)

        row = BoxLayout(size_hint_y=None, height=48, spacing=8)
        c = btn("اتصال")
        c.bind(on_release=lambda *_: self._connect_usb())
        d = btn("قطع الاتصال")
        d.bind(on_release=lambda *_: self._disconnect_usb())
        row.add_widget(c)
        row.add_widget(d)
        root.add_widget(row)

        self.usb_status_label = lbl("الحالة: غير متصل")
        root.add_widget(self.usb_status_label)

        note = lbl("لو ضغطت اتصال وطلع تنبيه إذن USB من أندرويد، وافق عليه ثم اضغط اتصال تانى",
                   size_hint_y=None, height=50, font_size=12)
        root.add_widget(note)

        tab.add_widget(root)
        self.tabs.add_widget(tab)
        self._usb_devices = []

    def _refresh_usb_devices(self):
        self._usb_devices = self.usb.list_devices()
        self.usb_spinner.values = [ar("{}".format(n)) for n, _dev in self._usb_devices]
        if self._usb_devices:
            self.usb_spinner.text = self.usb_spinner.values[0]

    def _connect_usb(self):
        if not self._usb_devices:
            self._log("حدّث القائمة واختر جهاز أولاً")
            return
        try:
            sel_index = self.usb_spinner.values.index(self.usb_spinner.text)
            device_name = self._usb_devices[sel_index][1]
        except (ValueError, IndexError):
            self._log("اختر جهاز من القائمة أولاً")
            return
        try:
            self.usb.connect(device_name)
            self.settings["usb_device_name"] = device_name
            save_settings(self.user_data_dir, self.settings)
            if self.usb.is_connected:
                self.usb_status_label.text = ar("الحالة: متصل ({})".format(device_name))
        except Exception as e:
            self._log("فشل الاتصال: {}".format(e))

    def _disconnect_usb(self):
        self.usb.disconnect()
        self.usb_status_label.text = ar("الحالة: غير متصل")

    # ------------------------------------------------------------------
    # تبويب الـ8 ريليهات (تسميات)
    # ------------------------------------------------------------------
    def _build_relays_tab(self):
        tab = TabbedPanelItem(text=ar("الريليهات"))
        root = BoxLayout(orientation="vertical", padding=8, spacing=6)
        grid = GridLayout(cols=2, size_hint_y=None, spacing=4)
        grid.bind(minimum_height=grid.setter("height"))

        self.relay_label_inputs = []
        for i in range(RELAY_COUNT):
            grid.add_widget(lbl("قناة {}:".format(i)))
            ti = TextInput(text=self.settings["relay_labels"][i], multiline=False)
            grid.add_widget(ti)
            self.relay_label_inputs.append(ti)

        scroll = ScrollView()
        scroll.add_widget(grid)
        root.add_widget(scroll)

        save_btn = btn("حفظ التسميات", size_hint_y=None, height=44)
        save_btn.bind(on_release=lambda *_: self._save_relay_labels())
        root.add_widget(save_btn)

        tab.add_widget(root)
        self.tabs.add_widget(tab)

    def _save_relay_labels(self):
        self.settings["relay_labels"] = [ti.text for ti in self.relay_label_inputs]
        save_settings(self.user_data_dir, self.settings)
        self._log("تم حفظ تسميات الريليهات")

    # ------------------------------------------------------------------
    # تبويب اختبار الريليهات
    # ------------------------------------------------------------------
    def _build_relay_test_tab(self):
        tab = TabbedPanelItem(text=ar("اختبار"))
        root = BoxLayout(orientation="vertical", padding=8, spacing=6)

        grid = GridLayout(cols=4, size_hint_y=None, spacing=4)
        grid.bind(minimum_height=grid.setter("height"))
        for i in range(RELAY_COUNT):
            grid.add_widget(lbl(self.settings["relay_labels"][i]))
            on_b = btn("تشغيل")
            on_b.bind(on_release=lambda _b, idx=i: self._cmd_set_relay(idx, True))
            off_b = btn("إيقاف")
            off_b.bind(on_release=lambda _b, idx=i: self._cmd_set_relay(idx, False))
            pulse_b = btn("نبضة")
            pulse_b.bind(on_release=lambda _b, idx=i: self._cmd_pulse_relay(idx, self.settings["pulse_ms"]))
            grid.add_widget(on_b)
            grid.add_widget(off_b)
            grid.add_widget(pulse_b)

        scroll = ScrollView()
        scroll.add_widget(grid)
        root.add_widget(scroll)

        self.relay_status_label = Label(text="", halign="right")
        root.add_widget(self.relay_status_label)

        tab.add_widget(root)
        self.tabs.add_widget(tab)
        self._refresh_relay_status()

    # ------------------------------------------------------------------
    # تبويب الإضاءة
    # ------------------------------------------------------------------
    def _build_light_tab(self):
        tab = TabbedPanelItem(text=ar("الإضاءة"))
        root = BoxLayout(orientation="vertical", padding=10, spacing=10)

        row = BoxLayout(size_hint_y=None, height=44)
        self.light_auto_checkbox = CheckBox(active=self.settings["lighting_auto"])
        self.light_auto_checkbox.bind(active=lambda _i, v: self._on_light_auto_toggle(v))
        row.add_widget(self.light_auto_checkbox)
        row.add_widget(lbl("تشغيل الإضاءة تلقائياً مع تشغيل الماكينة"))
        root.add_widget(row)

        btn_row = BoxLayout(size_hint_y=None, height=48, spacing=8)
        on_b = btn("تشغيل الإضاءة")
        on_b.bind(on_release=lambda *_: self._cmd_set_relay(LIGHT_INDEX, True))
        off_b = btn("إيقاف الإضاءة")
        off_b.bind(on_release=lambda *_: self._cmd_set_relay(LIGHT_INDEX, False))
        btn_row.add_widget(on_b)
        btn_row.add_widget(off_b)
        root.add_widget(btn_row)

        tab.add_widget(root)
        self.tabs.add_widget(tab)

    def _on_light_auto_toggle(self, value):
        self.settings["lighting_auto"] = value
        save_settings(self.user_data_dir, self.settings)

    # ------------------------------------------------------------------
    # تبويب الهزاز
    # ------------------------------------------------------------------
    def _build_vibrator_tab(self):
        tab = TabbedPanelItem(text=ar("الهزاز"))
        root = BoxLayout(orientation="vertical", padding=10, spacing=10)

        row = BoxLayout(size_hint_y=None, height=44)
        self.vibrator_checkbox = CheckBox(active=self.settings["vibrator_enabled"])
        self.vibrator_checkbox.bind(active=lambda _i, v: self._on_vibrator_toggle(v))
        row.add_widget(self.vibrator_checkbox)
        row.add_widget(lbl("تفعيل الهزاز أثناء تشغيل الفرز"))
        root.add_widget(row)

        btn_row = BoxLayout(size_hint_y=None, height=48, spacing=8)
        on_b = btn("تشغيل الهزاز")
        on_b.bind(on_release=lambda *_: self._cmd_set_relay(VIBRATOR_INDEX, True))
        off_b = btn("إيقاف الهزاز")
        off_b.bind(on_release=lambda *_: self._cmd_set_relay(VIBRATOR_INDEX, False))
        btn_row.add_widget(on_b)
        btn_row.add_widget(off_b)
        root.add_widget(btn_row)

        tab.add_widget(root)
        self.tabs.add_widget(tab)

    def _on_vibrator_toggle(self, value):
        self.settings["vibrator_enabled"] = value
        save_settings(self.user_data_dir, self.settings)

    # ------------------------------------------------------------------
    # تبويب AUX
    # ------------------------------------------------------------------
    def _build_aux_tab(self):
        tab = TabbedPanelItem(text=ar("AUX"))
        root = BoxLayout(orientation="vertical", padding=10, spacing=10)

        root.add_widget(lbl("تسمية المخرج:"))
        self.aux_label_input = TextInput(text=self.settings["aux_label"], multiline=False)
        root.add_widget(self.aux_label_input)
        save_b = btn("حفظ التسمية", size_hint_y=None, height=44)
        save_b.bind(on_release=lambda *_: self._save_aux_label())
        root.add_widget(save_b)

        btn_row = BoxLayout(size_hint_y=None, height=48, spacing=8)
        on_b = btn("تشغيل")
        on_b.bind(on_release=lambda *_: self._cmd_set_relay(AUX_INDEX, True))
        off_b = btn("إيقاف")
        off_b.bind(on_release=lambda *_: self._cmd_set_relay(AUX_INDEX, False))
        btn_row.add_widget(on_b)
        btn_row.add_widget(off_b)
        root.add_widget(btn_row)

        tab.add_widget(root)
        self.tabs.add_widget(tab)

    def _save_aux_label(self):
        self.settings["aux_label"] = self.aux_label_input.text
        save_settings(self.user_data_dir, self.settings)

    # ------------------------------------------------------------------
    def _emergency_stop_all(self):
        self.sorting_active = False
        if hasattr(self, "sorting_active_checkbox"):
            self.sorting_active_checkbox.active = False
        self.machine_running = False
        if hasattr(self, "machine_status_label"):
            self.machine_status_label.text = ar("الماكينة: متوقفة")
        self.usb.all_stop()
        self.relay_state = [False] * RELAY_COUNT
        self._refresh_relay_status()
        self._log("⛔ تم إيقاف كل الريليهات")

    def on_stop(self):
        try:
            self.usb.all_stop()
            self.usb.disconnect()
            save_settings(self.user_data_dir, self.settings)
        except Exception:
            pass


if __name__ == "__main__":
    SorterApp().run()
