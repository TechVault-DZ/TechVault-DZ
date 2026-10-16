import base64
import json
import os
import re
import ssl
import threading
import traceback
import urllib.error
import urllib.parse
import urllib.request

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.uix.spinner import Spinner
from kivy.graphics import Color, Rectangle
from kivy.metrics import dp, sp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.gridlayout import GridLayout
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.screenmanager import Screen, ScreenManager
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.uix.filechooser import FileChooserIconView
from kivy.utils import platform as _kivy_platform


# ============ التقاط أخطاء البدء ============
def _log_startup_error(exc):
    try:
        paths = [
            "/storage/emulated/0/Documents/techvault_error.txt",
            os.path.join(os.path.expanduser("~"), "techvault_error.txt"),
        ]
        err = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        for p in paths:
            try:
                os.makedirs(os.path.dirname(p), exist_ok=True)
                with open(p, "w", encoding="utf-8") as f:
                    f.write(err)
                print(f"[TechVault] Error logged to: {p}")
                break
            except Exception:
                continue
    except Exception:
        pass


# ============ إصلاح SSL ============
try:
    import certifi
    SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())
    print("[TechVault] SSL: certifi loaded OK")
except Exception as e:
    print(f"[TechVault] SSL fallback: {e}")
    SSL_CONTEXT = ssl._create_unverified_context()

Window.clearcolor = (0.95, 0.97, 0.95, 1)

# ============ دعم العربية ============
try:
    import arabic_reshaper
    from bidi.algorithm import get_display
    HAS_BIDI = True
except ImportError:
    HAS_BIDI = False

# ============ مسار الخط ============
BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def _find_font():
    for name in ("arabic.ttf", "Cairo-Regular.ttf", "Amiri-Regular.ttf"):
        p = os.path.join(BASE_DIR, name)
        if os.path.exists(p):
            return p
    return None


FONT_PATH = _find_font()
print(f"[TechVault] BASE_DIR = {BASE_DIR}")
print(f"[TechVault] FONT_PATH = {FONT_PATH}")


def _user_index_path():
    try:
        data_dir = App.get_running_app().user_data_dir
    except Exception:
        data_dir = BASE_DIR
    return os.path.join(data_dir, "index.html")


def format_ar(text):
    if text is None:
        return ""
    text_str = str(text)
    if HAS_BIDI:
        try:
            if any("\u0600" <= c <= "\u06ff" for c in text_str):
                reshaped = arabic_reshaper.reshape(text_str)
                return get_display(reshaped)
        except Exception:
            return text_str
    return text_str


# ============ Android Permissions ============
def request_android_permissions():
    if _kivy_platform != "android":
        return
    try:
        from android.permissions import request_permissions, Permission
        request_permissions([
            Permission.READ_EXTERNAL_STORAGE,
            Permission.WRITE_EXTERNAL_STORAGE,
        ])
    except Exception as e:
        print(f"[TechVault] permissions error: {e}")


def has_manage_external_storage():
    if _kivy_platform != "android":
        return True
    try:
        from jnius import autoclass
        Build = autoclass('android.os.Build')
        if Build.VERSION.SDK_INT < 30:
            return True
        Environment = autoclass('android.os.Environment')
        return Environment.isExternalStorageManager()
    except Exception as e:
        print(f"[TechVault] check all files error: {e}")
        return True


def open_all_files_settings():
    if _kivy_platform != "android":
        return
    try:
        from jnius import autoclass
        Build = autoclass('android.os.Build')
        if Build.VERSION.SDK_INT < 30:
            return
        PythonActivity = autoclass('org.kivy.android.PythonActivity')
        Intent = autoclass('android.content.Intent')
        Uri = autoclass('android.net.Uri')
        Settings = autoclass('android.provider.Settings')
        pkg = PythonActivity.mActivity.getPackageName()
        intent = Intent(Settings.ACTION_MANAGE_APP_ALL_FILES_ACCESS_PERMISSION)
        intent.setData(Uri.parse("package:" + pkg))
        PythonActivity.mActivity.startActivity(intent)
    except Exception as e:
        print(f"[TechVault] open all files settings error: {e}")


# ============ ترجمة ============
def translate_text(text, target_lang):
    if not text or not text.strip():
        return ""
    try:
        url = (
            "https://translate.googleapis.com/translate_a/single"
            f"?client=gtx&sl=ar&tl={target_lang}&dt=t"
            f"&q={urllib.parse.quote(text)}"
        )
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Linux; Android 10)",
                "Accept": "application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=6, context=SSL_CONTEXT) as r:
            data = json.loads(r.read().decode("utf-8"))
        if data and isinstance(data, list) and data[0]:
            parts = []
            for seg in data[0]:
                if seg and isinstance(seg, list) and seg[0]:
                    parts.append(seg[0])
            result = "".join(parts).strip()
            if result:
                return result
    except Exception as e:
        print(f"[TechVault] Google failed: {e}")

    try:
        url = (
            f"https://api.mymemory.translated.net/get"
            f"?q={urllib.parse.quote(text)}&langpair=ar|{target_lang}"
        )
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=6, context=SSL_CONTEXT) as r:
            data = json.loads(r.read().decode("utf-8"))
        status = data.get("responseStatus")
        if str(status) == "200":
            result = data.get("responseData", {}).get("translatedText", "").strip()
            if result:
                return result
    except Exception as e:
        print(f"[TechVault] MyMemory failed: {e}")
    return ""


# ===================== 0. Splash =====================
class SplashScreen(Screen):
    def __init__(self, **kwargs):
        super(SplashScreen, self).__init__(**kwargs)
        layout = BoxLayout(orientation="vertical", padding=dp(30), spacing=dp(15))
        logo_path = os.path.join(BASE_DIR, "logo.png")
        if os.path.exists(logo_path):
            layout.add_widget(Image(
                source=logo_path, allow_stretch=True, keep_ratio=True, size_hint=(1, 1)
            ))
        else:
            layout.add_widget(Label(
                text="TechVault DZ", font_size=sp(30), bold=True,
                color=(0.05, 0.58, 0.38, 1),
                font_name=FONT_PATH if FONT_PATH else "Roboto",
            ))
        layout.add_widget(Label(
            text=format_ar("الخزنة الجزائرية للبرمجيات"),
            font_size=sp(14), color=(0.3, 0.3, 0.3, 1),
            size_hint_y=None, height=dp(30),
            font_name=FONT_PATH if FONT_PATH else "Roboto",
        ))
        self.add_widget(layout)


# ===================== 1. Login =====================
class LoginScreen(Screen):
    def __init__(self, **kwargs):
        super(LoginScreen, self).__init__(**kwargs)
        layout = BoxLayout(
            orientation="vertical", padding=dp(20), spacing=dp(12),
            size_hint=(0.9, None), height=dp(380),
            pos_hint={"center_x": 0.5, "center_y": 0.5},
        )
        logo_path = os.path.join(BASE_DIR, "logo.png")
        if os.path.exists(logo_path):
            layout.add_widget(Image(source=logo_path, size_hint_y=None, height=dp(110), allow_stretch=True))
        layout.add_widget(Label(
            text=format_ar("TechVault DZ - قفل الخزنة"),
            font_size=sp(18), bold=True, color=(0.05, 0.58, 0.38, 1),
            size_hint_y=None, height=dp(30),
            font_name=FONT_PATH if FONT_PATH else "Roboto",
        ))
        layout.add_widget(Label(
            text=format_ar("أدخل كلمة المرور:"),
            font_size=sp(13), color=(0.3, 0.3, 0.3, 1),
            size_hint_y=None, height=dp(25),
            font_name=FONT_PATH if FONT_PATH else "Roboto",
        ))
        self.pass_input = TextInput(
            password=True, multiline=False, font_size=sp(16),
            size_hint_y=None, height=dp(42),
            font_name=FONT_PATH if FONT_PATH else "Roboto",
        )
        layout.add_widget(self.pass_input)
        btn_login = Button(
            text=format_ar("فتح الخزنة"),
            size_hint_y=None, height=dp(48),
            background_color=(0.05, 0.58, 0.38, 1),
            color=(1, 1, 1, 1), font_size=sp(15), bold=True,
            font_name=FONT_PATH if FONT_PATH else "Roboto",
        )
        btn_login.bind(on_press=self.check_password)
        layout.add_widget(btn_login)
        self.error_label = Label(
            text="", color=(0.7, 0.2, 0.2, 1),
            size_hint_y=None, height=dp(25),
            font_name=FONT_PATH if FONT_PATH else "Roboto",
        )
        layout.add_widget(self.error_label)
        self.add_widget(layout)

    def check_password(self, instance):
        app_instance = App.get_running_app()
        if self.pass_input.text.strip() == app_instance.vault_password:
            self.pass_input.text = ""
            self.error_label.text = ""
            self.manager.current = "home"
        else:
            self.error_label.text = format_ar("كلمة المرور غير صحيحة!")


# ===================== 2. Home =====================
class HomeScreen(Screen):
    def __init__(self, **kwargs):
        super(HomeScreen, self).__init__(**kwargs)
        layout = BoxLayout(
            orientation="vertical", padding=dp(20), spacing=dp(15),
            size_hint=(0.9, None), height=dp(420),
            pos_hint={"center_x": 0.5, "center_y": 0.5},
        )
        logo_path = os.path.join(BASE_DIR, "logo.png")
        if os.path.exists(logo_path):
            layout.add_widget(Image(
                source=logo_path, size_hint_y=None, height=dp(120),
                allow_stretch=True, keep_ratio=True,
            ))
        btn_vault = Button(
            text=format_ar("Open Vault (إدارة المنتجات)"),
            size_hint_y=None, height=dp(50),
            background_color=(0.05, 0.58, 0.38, 1),
            color=(1, 1, 1, 1), font_size=sp(14), bold=True,
            font_name=FONT_PATH if FONT_PATH else "Roboto",
        )
        btn_vault.bind(on_press=lambda x: setattr(self.manager, "current", "products"))
        btn_logs = Button(
            text=format_ar("View Secure Logs (سجلات الأمان)"),
            size_hint_y=None, height=dp(50),
            background_color=(0.7, 0.2, 0.2, 1),
            color=(1, 1, 1, 1), font_size=sp(14), bold=True,
            font_name=FONT_PATH if FONT_PATH else "Roboto",
        )
        btn_logs.bind(on_press=lambda x: setattr(self.manager, "current", "logs"))
        btn_settings = Button(
            text=format_ar("Account Settings (الإعدادات)"),
            size_hint_y=None, height=dp(50),
            background_color=(0.15, 0.35, 0.55, 1),
            color=(1, 1, 1, 1), font_size=sp(14), bold=True,
            font_name=FONT_PATH if FONT_PATH else "Roboto",
        )
        btn_settings.bind(on_press=lambda x: setattr(self.manager, "current", "settings"))
        btn_lock = Button(
            text=format_ar("قفل التطبيق"),
            size_hint_y=None, height=dp(50),
            background_color=(0.25, 0.25, 0.25, 1),
            color=(1, 1, 1, 1), font_size=sp(14), bold=True,
            font_name=FONT_PATH if FONT_PATH else "Roboto",
        )
        btn_lock.bind(on_press=lambda x: setattr(self.manager, "current", "login"))
        layout.add_widget(btn_vault)
        layout.add_widget(btn_logs)
        layout.add_widget(btn_settings)
        layout.add_widget(btn_lock)
        self.add_widget(layout)


# ===================== 3. Products =====================
class ProductsScreen(Screen):
    def __init__(self, **kwargs):
        super(ProductsScreen, self).__init__(**kwargs)
        self.products = []
        self.bundled_html_path = os.path.join(BASE_DIR, "index.html")
        self.full_image_paths = {}

        user_html = _user_index_path()
        if os.path.exists(user_html):
            self.html_path = user_html
        else:
            self.html_path = self.bundled_html_path

        root = BoxLayout(orientation="vertical", padding=dp(10), spacing=dp(8))

        top_bar = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(4))
        btn_back = Button(
            text=format_ar("رئيسية"), size_hint_x=0.20,
            background_color=(0.25, 0.25, 0.25, 1), color=(1, 1, 1, 1),
            font_size=sp(12), font_name=FONT_PATH if FONT_PATH else "Roboto",
        )
        btn_back.bind(on_press=lambda x: setattr(self.manager, "current", "home"))
        btn_reload = Button(
            text=format_ar("إعادة تحميل"), size_hint_x=0.26,
            background_color=(0.15, 0.35, 0.55, 1), color=(1, 1, 1, 1),
            font_size=sp(12), font_name=FONT_PATH if FONT_PATH else "Roboto",
        )
        btn_reload.bind(on_press=self.load_html)
        btn_open = Button(
            text=format_ar("فتح ملف"), size_hint_x=0.26,
            background_color=(0.8, 0.5, 0.1, 1), color=(1, 1, 1, 1),
            font_size=sp(12), bold=True, font_name=FONT_PATH if FONT_PATH else "Roboto",
        )
        btn_open.bind(on_press=lambda x: self.open_html_chooser_popup())
        btn_from_gh = Button(
            text=format_ar("من GitHub"), size_hint_x=0.28,
            background_color=(0.1, 0.1, 0.1, 1), color=(1, 1, 1, 1),
            font_size=sp(12), bold=True, font_name=FONT_PATH if FONT_PATH else "Roboto",
        )
        btn_from_gh.bind(on_press=lambda x: self.download_html_from_github())
        top_bar.add_widget(btn_back)
        top_bar.add_widget(btn_reload)
        top_bar.add_widget(btn_open)
        top_bar.add_widget(btn_from_gh)
        root.add_widget(top_bar)

        action_bar = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(4))
        btn_add = Button(
            text=format_ar("إضافة منتج"), size_hint_x=0.35,
            background_color=(0.05, 0.58, 0.38, 1), color=(1, 1, 1, 1),
            font_size=sp(13), bold=True, font_name=FONT_PATH if FONT_PATH else "Roboto",
        )
        btn_add.bind(on_press=lambda x: self.open_product_form())
        btn_save = Button(
            text=format_ar("حفظ ورفع إلى GitHub"), size_hint_x=0.65,
            background_color=(0.7, 0.2, 0.2, 1), color=(1, 1, 1, 1),
            font_size=sp(13), bold=True, font_name=FONT_PATH if FONT_PATH else "Roboto",
        )
        btn_save.bind(on_press=self.save_and_push)
        action_bar.add_widget(btn_add)
        action_bar.add_widget(btn_save)
        root.add_widget(action_bar)

        self.status_label = Label(
            text=format_ar("إدارة منتجات TechVault DZ"),
            size_hint_y=None, height=dp(28), color=(0.2, 0.2, 0.2, 1),
            font_size=sp(12), font_name=FONT_PATH if FONT_PATH else "Roboto",
        )
        root.add_widget(self.status_label)

        self.scroll = ScrollView()
        self.products_layout = GridLayout(cols=1, spacing=dp(8), size_hint_y=None)
        self.products_layout.bind(minimum_height=self.products_layout.setter("height"))
        self.scroll.add_widget(self.products_layout)
        root.add_widget(self.scroll)

        self.add_widget(root)

        if os.path.exists(self.html_path):
            self.load_html(None)

    def _find_products_array(self, content):
        m = re.search(r"const\s+products\s*=\s*", content)
        if not m:
            return None
        start = m.end()
        while start < len(content) and content[start] in " \t\r\n":
            start += 1
        if start >= len(content) or content[start] != "[":
            return None
        depth = 0
        in_str = None
        esc = False
        i = start
        while i < len(content):
            c = content[i]
            if in_str:
                if esc:
                    esc = False
                elif c == "\\":
                    esc = True
                elif c == in_str:
                    in_str = None
            else:
                if c == "'" or c == '"':
                    in_str = c
                elif c in "[{":
                    depth += 1
                elif c in "]}":
                    depth -= 1
                    if depth == 0 and c == "]":
                        return (start, i + 1)
            i += 1
        return None

    def _replace_products_array(self, content, new_json_str):
        pos = self._find_products_array(content)
        if pos is None:
            return None
        start, end = pos
        return content[:start] + new_json_str + content[end:]

    def js_to_json(self, js_str):
        out = []
        i = 0
        n = len(js_str)
        in_str = None
        esc = False
        while i < n:
            c = js_str[i]
            if in_str:
                if esc:
                    out.append(c)
                    esc = False
                elif c == "\\":
                    out.append(c)
                    esc = True
                elif c == in_str:
                    out.append('"')
                    in_str = None
                elif c == '"':
                    out.append('\\"')
                else:
                    out.append(c)
                i += 1
                continue
            if c == "'" or c == '"':
                in_str = c
                out.append('"')
            elif c == ",":
                j = i + 1
                while j < n and js_str[j] in " \t\r\n":
                    j += 1
                if j < n and js_str[j] in "]}":
                    pass
                else:
                    out.append(",")
            elif c == "/" and i + 1 < n and js_str[i + 1] == "/":
                j = js_str.find("\n", i)
                if j == -1:
                    break
                i = j
                continue
            elif c == "/" and i + 1 < n and js_str[i + 1] == "*":
                j = js_str.find("*/", i + 2)
                if j == -1:
                    break
                i = j + 1
                continue
            else:
                out.append(c)
            i += 1
        result = "".join(out)
        result = re.sub(r"([{,]\s*)([a-zA-Z_$][a-zA-Z0-9_$]*)\s*:", r'\1"\2":', result)
        return result

    def json_to_js(self, py_list):
        return json.dumps(py_list, ensure_ascii=False, indent=4)

    def load_html(self, instance):
        if not os.path.exists(self.html_path):
            self.status_label.text = format_ar("خطأ: index.html غير موجود!")
            return
        try:
            with open(self.html_path, "r", encoding="utf-8") as f:
                content = f.read()
            pos = self._find_products_array(content)
            if pos is None:
                self.status_label.text = format_ar("لم أجد 'const products = [...]' في index.html")
                self.products = []
                self.refresh_products_list()
                return
            start, end = pos
            js_arr = content[start:end]
            json_str = self.js_to_json(js_arr)
            self.products = json.loads(json_str)
            self.status_label.text = format_ar(f"تم تحميل {len(self.products)} منتج بنجاح.")
            self.refresh_products_list()
        except json.JSONDecodeError as e:
            self.status_label.text = format_ar(f"خطأ JSON: {str(e)[:40]}")
            self.products = []
            self.refresh_products_list()
        except Exception as e:
            self.status_label.text = format_ar(f"خطأ: {str(e)[:40]}")
            print(f"[TechVault] load_html error: {e}")

    # ⭐⭐⭐ قائمة المنتجات (مع التصحيح) ⭐⭐⭐
    def refresh_products_list(self):
        try:
            self.products_layout.clear_widgets()

            if not self.products:
                empty_lbl = Label(
                    text=format_ar("لا توجد منتجات بعد\nاضغط 'إضافة منتج' للبدء"),
                    color=(0.5, 0.5, 0.5, 1),
                    font_size=sp(14),
                    halign="center",
                    valign="middle",
                    size_hint_y=None,
                    height=dp(80),
                    font_name=FONT_PATH if FONT_PATH else "Roboto",
                )
                empty_lbl.bind(width=lambda s, w: setattr(s, "text_size", (w, None)))
                self.products_layout.add_widget(empty_lbl)
                return

            for i, p in enumerate(self.products):
                name_ar = p.get("name", {}).get("ar", "بدون اسم")
                name_fr = p.get("name", {}).get("fr", "")
                cat = p.get("category", "desktop").upper()
                version = p.get("version", "v1.0.0")
                size_mb = p.get("size", "—")
                rating = p.get("rating", 0)

                if cat == "ANDROID":
                    accent = (0.05, 0.58, 0.38, 1)
                else:
                    accent = (0.15, 0.35, 0.55, 1)

                card = BoxLayout(
                    orientation="horizontal",
                    size_hint_y=None,
                    height=dp(120),
                    padding=dp(10),
                    spacing=dp(10),
                )

                with card.canvas.before:
                    Color(1, 1, 1, 1)
                    bg_rect = Rectangle(pos=card.pos, size=card.size)
                    Color(accent[0], accent[1], accent[2], 0.9)
                    border_rect = Rectangle(pos=card.pos, size=(dp(4), card.height))

                def _update_graphics(inst, *args):
                    try:
                        bg_rect.pos = inst.pos
                        bg_rect.size = inst.size
                        border_rect.pos = inst.pos
                        border_rect.size = (dp(4), inst.height)
                    except Exception:
                        pass

                card.bind(pos=_update_graphics, size=_update_graphics)

                icon_lbl = Label(
                    text="[b]●[/b]", markup=True, color=accent,
                    font_size=sp(20), size_hint_x=None, width=dp(30),
                    halign="center", valign="middle",
                )
                card.add_widget(icon_lbl)

                info_box = BoxLayout(orientation="vertical", spacing=dp(4))

                title_lbl = Label(
                    text=format_ar(name_ar),
                    color=(0.1, 0.1, 0.1, 1),
                    font_size=sp(14), bold=True,
                    halign="right", valign="top",
                    size_hint_y=None, height=dp(46),
                    font_name=FONT_PATH if FONT_PATH else "Roboto",
                )
                title_lbl.bind(width=lambda s, w: setattr(s, "text_size", (w, None)))
                info_box.add_widget(title_lbl)

                if name_fr:
                    subtitle_lbl = Label(
                        text=str(name_fr),
                        color=(0.5, 0.5, 0.5, 1),
                        font_size=sp(11),
                        halign="right", valign="middle",
                        size_hint_y=None, height=dp(18),
                        font_name=FONT_PATH if FONT_PATH else "Roboto",
                    )
                    subtitle_lbl.bind(width=lambda s, w: setattr(s, "text_size", (w, None)))
                    info_box.add_widget(subtitle_lbl)

                details_lbl = Label(
                    text=f"{version}  •  {size_mb}  •  {rating} / 5",
                    color=(0.4, 0.4, 0.4, 1),
                    font_size=sp(11),
                    halign="right", valign="middle",
                    size_hint_y=None, height=dp(18),
                    font_name=FONT_PATH if FONT_PATH else "Roboto",
                )
                details_lbl.bind(width=lambda s, w: setattr(s, "text_size", (w, None)))
                info_box.add_widget(details_lbl)

                card.add_widget(info_box)

                cat_lbl = Label(
                    text=cat, color=accent,
                    font_size=sp(11), bold=True,
                    halign="center", valign="middle",
                    size_hint_x=None, width=dp(80),
                    font_name=FONT_PATH if FONT_PATH else "Roboto",
                )
                card.add_widget(cat_lbl)

                def make_clickable(c, idx):
                    def on_touch_down(touch):
                        if c.collide_point(*touch.pos):
                            try:
                                self.open_product_options(idx)
                            except Exception as e:
                                print(f"[TechVault] open options error: {e}")
                            return True
                        return False
                    return on_touch_down

                card.on_touch_down = make_clickable(card, i)
                self.products_layout.add_widget(card)

        except Exception as e:
            print(f"[TechVault] refresh_products_list error: {e}")
            traceback.print_exc()

    def open_product_options(self, idx):
        if not (0 <= idx < len(self.products)):
            return
        p = self.products[idx]
        name_ar = p.get("name", {}).get("ar", "بدون اسم")
        cat = p.get("category", "desktop").upper()
        version = p.get("version", "v1.0.0")
        size_mb = p.get("size", "—")

        content = BoxLayout(orientation="vertical", padding=dp(18), spacing=dp(14))
        with content.canvas.before:
            Color(1, 1, 1, 1)
            self.bg_options = Rectangle(size=content.size, pos=content.pos)
        content.bind(
            size=lambda s, w: setattr(self.bg_options, "size", s.size),
            pos=lambda s, w: setattr(self.bg_options, "pos", s.pos),
        )

        title_lbl = Label(
            text=format_ar(name_ar), font_size=sp(17), bold=True,
            color=(0.1, 0.1, 0.1, 1),
            halign="center", valign="middle",
            size_hint_y=None, height=dp(40),
            font_name=FONT_PATH if FONT_PATH else "Roboto",
        )
        title_lbl.bind(width=lambda s, w: setattr(s, "text_size", (w, None)))
        content.add_widget(title_lbl)

        info_lbl = Label(
            text=format_ar(f"{cat}  •  {version}  •  {size_mb}"),
            font_size=sp(12), color=(0.5, 0.5, 0.5, 1),
            halign="center", valign="middle",
            size_hint_y=None, height=dp(24),
            font_name=FONT_PATH if FONT_PATH else "Roboto",
        )
        content.add_widget(info_lbl)

        popup = Popup(
            title="", content=content,
            size_hint=(0.85, 0.5),
            separator_color=(0.15, 0.35, 0.55, 1),
            background_color=(0, 0, 0, 0.5),
        )

        btn_edit = Button(
            text=format_ar("تعديل المنتج"),
            size_hint_y=None, height=dp(52),
            background_color=(0.15, 0.35, 0.55, 1),
            color=(1, 1, 1, 1), font_size=sp(15), bold=True,
            font_name=FONT_PATH if FONT_PATH else "Roboto",
        )

        def do_edit(btn):
            popup.dismiss()
            Clock.schedule_once(lambda dt: self.open_product_form(idx=idx), 0.3)

        btn_edit.bind(on_press=do_edit)
        content.add_widget(btn_edit)

        btn_del = Button(
            text=format_ar("حذف المنتج"),
            size_hint_y=None, height=dp(52),
            background_color=(0.7, 0.2, 0.2, 1),
            color=(1, 1, 1, 1), font_size=sp(15), bold=True,
            font_name=FONT_PATH if FONT_PATH else "Roboto",
        )

        def do_delete(btn):
            popup.dismiss()
            Clock.schedule_once(lambda dt: self.confirm_delete_product(idx), 0.3)

        btn_del.bind(on_press=do_delete)
        content.add_widget(btn_del)

        btn_close = Button(
            text=format_ar("إغلاق"),
            size_hint_y=None, height=dp(48),
            background_color=(0.5, 0.5, 0.5, 1),
            color=(1, 1, 1, 1), font_size=sp(14),
            font_name=FONT_PATH if FONT_PATH else "Roboto",
        )
        btn_close.bind(on_press=lambda x: popup.dismiss())
        content.add_widget(btn_close)

        popup.open()

    def confirm_delete_product(self, idx):
        if not (0 <= idx < len(self.products)):
            return
        p = self.products[idx]
        name_ar = p.get("name", {}).get("ar", "بدون اسم")

        content = BoxLayout(orientation="vertical", padding=dp(18), spacing=dp(14))
        with content.canvas.before:
            Color(1, 1, 1, 1)
            self.bg_del = Rectangle(size=content.size, pos=content.pos)
        content.bind(
            size=lambda s, w: setattr(self.bg_del, "size", s.size),
            pos=lambda s, w: setattr(self.bg_del, "pos", s.pos),
        )

        content.add_widget(Label(
            text=format_ar("تأكيد الحذف"),
            font_size=sp(17), bold=True, color=(0.7, 0.2, 0.2, 1),
            halign="center", valign="middle",
            size_hint_y=None, height=dp(36),
            font_name=FONT_PATH if FONT_PATH else "Roboto",
        ))

        msg = Label(
            text=format_ar(f"هل أنت متأكد من حذف:\n\n« {name_ar} »\n\nلا يمكن التراجع عن هذه العملية."),
            font_size=sp(13), halign="center", valign="middle",
            color=(0.2, 0.2, 0.2, 1),
            size_hint_y=None, height=dp(110),
            font_name=FONT_PATH if FONT_PATH else "Roboto",
        )
        msg.bind(width=lambda s, w: setattr(s, "text_size", (w, None)))
        content.add_widget(msg)

        popup = Popup(
            title="", content=content,
            size_hint=(0.85, 0.45),
            separator_color=(0.7, 0.2, 0.2, 1),
            background_color=(0, 0, 0, 0.5),
        )

        btn_box = BoxLayout(size_hint_y=None, height=dp(50), spacing=dp(10))

        def do_delete(btn):
            popup.dismiss()
            del self.products[idx]
            self.refresh_products_list()
            self.status_label.text = format_ar("تم الحذف. اضغط 'حفظ ورفع إلى GitHub' في الأعلى.")

        btn_yes = Button(
            text=format_ar("نعم، احذف"),
            background_color=(0.7, 0.2, 0.2, 1),
            color=(1, 1, 1, 1), font_size=sp(14), bold=True,
            font_name=FONT_PATH if FONT_PATH else "Roboto",
        )
        btn_yes.bind(on_press=do_delete)
        btn_no = Button(
            text=format_ar("إلغاء"),
            background_color=(0.5, 0.5, 0.5, 1),
            color=(1, 1, 1, 1), font_size=sp(14),
            font_name=FONT_PATH if FONT_PATH else "Roboto",
        )
        btn_no.bind(on_press=lambda x: popup.dismiss())
        btn_box.add_widget(btn_yes)
        btn_box.add_widget(btn_no)
        content.add_widget(btn_box)

        popup.open()

    def _save_local_copy(self, src_path):
        try:
            dst = _user_index_path()
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            with open(src_path, "r", encoding="utf-8") as f:
                data = f.read()
            with open(dst, "w", encoding="utf-8") as f:
                f.write(data)
            self.html_path = dst
            return True
        except Exception as e:
            print(f"[TechVault] save local copy error: {e}")
            return False

    def _show_all_files_dialog(self):
        content = BoxLayout(orientation="vertical", padding=dp(15), spacing=dp(10))
        with content.canvas.before:
            Color(0.96, 0.98, 0.96, 1)
            self.bg_perm = Rectangle(size=content.size, pos=content.pos)
        content.bind(
            size=lambda s, w: setattr(self.bg_perm, "size", s.size),
            pos=lambda s, w: setattr(self.bg_perm, "pos", s.pos),
        )
        content.add_widget(Label(
            text=format_ar("صلاحية مطلوبة"),
            font_size=sp(16), bold=True, color=(0.7, 0.2, 0.2, 1),
            size_hint_y=None, height=dp(35),
            font_name=FONT_PATH if FONT_PATH else "Roboto",
        ))
        msg = Label(
            text=format_ar(
                "لتتمكن من فتح ملفات HTML من هاتفك،\n"
                "يجب تفعيل صلاحية 'الوصول لجميع الملفات'\n"
                "في إعدادات التطبيق.\n\n"
                "اضغط 'فتح الإعدادات' ثم اختر\n"
                "'السماح بالوصول لجميع الملفات'."
            ),
            font_size=sp(12), halign="center", valign="middle",
            color=(0.15, 0.15, 0.15, 1),
            font_name=FONT_PATH if FONT_PATH else "Roboto",
        )
        msg.bind(width=lambda s, w: setattr(s, "text_size", (w, None)))
        content.add_widget(msg)

        popup = Popup(
            title="", content=content,
            size_hint=(0.9, 0.55),
            separator_color=(0.7, 0.2, 0.2, 1),
        )

        btn_box = BoxLayout(size_hint_y=None, height=dp(50), spacing=dp(10))
        btn_open = Button(
            text=format_ar("فتح الإعدادات"),
            background_color=(0.05, 0.58, 0.38, 1),
            color=(1, 1, 1, 1), bold=True,
            font_name=FONT_PATH if FONT_PATH else "Roboto",
        )

        def open_settings(btn):
            popup.dismiss()
            open_all_files_settings()

        btn_open.bind(on_press=open_settings)
        btn_cancel = Button(
            text=format_ar("لاحقاً"),
            background_color=(0.25, 0.25, 0.25, 1),
            color=(1, 1, 1, 1),
            font_name=FONT_PATH if FONT_PATH else "Roboto",
        )
        btn_cancel.bind(on_press=popup.dismiss)
        btn_box.add_widget(btn_open)
        btn_box.add_widget(btn_cancel)
        content.add_widget(btn_box)
        popup.open()

    def open_html_chooser_popup(self):
        if not has_manage_external_storage():
            self._show_all_files_dialog()
            return
        content = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(10))
        with content.canvas.before:
            Color(0.12, 0.15, 0.13, 1)
            self.bg_html_chooser = Rectangle(size=content.size, pos=content.pos)
        content.bind(
            size=lambda s, w: setattr(self.bg_html_chooser, "size", s.size),
            pos=lambda s, w: setattr(self.bg_html_chooser, "pos", s.pos),
        )
        initial_path = "/storage/emulated/0"
        if not os.path.exists(initial_path):
            initial_path = "/sdcard"
        if not os.path.exists(initial_path):
            initial_path = os.path.expanduser("~")
        file_chooser = FileChooserIconView(
            filters=["*.html", "*.htm"], path=initial_path, size_hint=(1, 1)
        )
        content.add_widget(file_chooser)
        btn_layout = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(10))
        btn_select = Button(
            text=format_ar("فتح هذا الملف"),
            background_color=(0.05, 0.58, 0.38, 1),
            color=(1, 1, 1, 1), bold=True,
            font_name=FONT_PATH if FONT_PATH else "Roboto",
        )
        btn_cancel = Button(
            text=format_ar("إلغاء"),
            background_color=(0.7, 0.2, 0.2, 1),
            color=(1, 1, 1, 1), bold=True,
            font_name=FONT_PATH if FONT_PATH else "Roboto",
        )
        popup = Popup(
            title=format_ar("اختر ملف index.html"),
            title_font=FONT_PATH if FONT_PATH else "Roboto",
            title_size=sp(15), title_align="center",
            content=content, size_hint=(0.94, 0.92),
            separator_color=(0.8, 0.5, 0.1, 1),
        )

        def on_select(instance):
            if file_chooser.selection:
                chosen = file_chooser.selection[0]
                if self._save_local_copy(chosen):
                    self.status_label.text = format_ar(f"تم فتح: {os.path.basename(chosen)}")
                    self.load_html(None)
                else:
                    self.status_label.text = format_ar("فشل نسخ الملف المختار.")
            popup.dismiss()

        btn_select.bind(on_press=on_select)
        btn_cancel.bind(on_press=popup.dismiss)
        btn_layout.add_widget(btn_select)
        btn_layout.add_widget(btn_cancel)
        content.add_widget(btn_layout)
        popup.open()

    def download_html_from_github(self):
        cfg = self.load_gh_config()
        user = cfg.get("user", "").strip()
        repo = cfg.get("repo", "").strip()
        if not user or not repo:
            self.status_label.text = format_ar("حدّد بيانات GitHub أولاً من الإعدادات.")
            return
        self.status_label.text = format_ar("جاري جلب index.html من GitHub...")

        def bg():
            try:
                raw_url = f"https://raw.githubusercontent.com/{user}/{repo}/main/index.html"
                req = urllib.request.Request(raw_url, headers={"User-Agent": "TechVault-DZ-App"})
                with urllib.request.urlopen(req, timeout=10, context=SSL_CONTEXT) as r:
                    data = r.read().decode("utf-8")
                dst = _user_index_path()
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                with open(dst, "w", encoding="utf-8") as f:
                    f.write(data)

                def done(dt):
                    self.html_path = dst
                    self.load_html(None)
                    self.status_label.text = format_ar("تم جلب index.html من GitHub بنجاح!")

                Clock.schedule_once(done, 0)
            except Exception as e:
                print(f"[TechVault] download html error: {e}")

                def failed(dt):
                    self.status_label.text = format_ar(f"فشل الجلب: {str(e)[:40]}")

                Clock.schedule_once(failed, 0)

        threading.Thread(target=bg, daemon=True).start()

    def reset_to_bundled_html(self):
        try:
            user_html = _user_index_path()
            if os.path.exists(user_html):
                os.remove(user_html)
            self.html_path = self.bundled_html_path
            self.load_html(None)
            self.status_label.text = format_ar("تم الرجوع للنسخة الأصلية.")
        except Exception as e:
            self.status_label.text = format_ar(f"خطأ: {str(e)[:30]}")

    def open_file_chooser_popup(self, text_input_field):
        if not has_manage_external_storage():
            self._show_all_files_dialog()
            return
        content = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(10))
        with content.canvas.before:
            Color(0.12, 0.15, 0.13, 1)
            self.bg_chooser = Rectangle(size=content.size, pos=content.pos)
        content.bind(
            size=lambda s, w: setattr(self.bg_chooser, "size", s.size),
            pos=lambda s, w: setattr(self.bg_chooser, "pos", s.pos),
        )
        initial_path = "/storage/emulated/0"
        if not os.path.exists(initial_path):
            initial_path = "/sdcard"
        if not os.path.exists(initial_path):
            initial_path = os.path.expanduser("~")
        file_chooser = FileChooserIconView(
            filters=["*.png", "*.jpg", "*.jpeg"], path=initial_path, size_hint=(1, 1)
        )
        content.add_widget(file_chooser)
        btn_layout = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(10))
        btn_select = Button(
            text=format_ar("اختيار هذه الصورة"),
            background_color=(0.05, 0.58, 0.38, 1),
            color=(1, 1, 1, 1), bold=True,
            font_name=FONT_PATH if FONT_PATH else "Roboto",
        )
        btn_cancel = Button(
            text=format_ar("إلغاء"),
            background_color=(0.7, 0.2, 0.2, 1),
            color=(1, 1, 1, 1), bold=True,
            font_name=FONT_PATH if FONT_PATH else "Roboto",
        )
        popup = Popup(
            title=format_ar("اختر صورة المنتج"),
            title_font=FONT_PATH if FONT_PATH else "Roboto",
            title_size=sp(16), title_align="center",
            content=content, size_hint=(0.94, 0.92),
            separator_color=(0.05, 0.58, 0.38, 1),
        )

        def on_select(instance):
            if file_chooser.selection:
                full_path = file_chooser.selection[0]
                filename = os.path.basename(full_path)
                text_input_field.text = filename
                self.full_image_paths[filename] = full_path
            popup.dismiss()

        btn_select.bind(on_press=on_select)
        btn_cancel.bind(on_press=popup.dismiss)
        btn_layout.add_widget(btn_select)
        btn_layout.add_widget(btn_cancel)
        content.add_widget(btn_layout)
        popup.open()

    def open_product_form(self, idx=None):
        is_edit = idx is not None
        p = (
            self.products[idx]
            if is_edit
            else {
                "id": len(self.products) + 1,
                "category": "desktop",
                "icon": "fa-solid fa-code",
                "color": "from-blue-500 to-indigo-600",
                "image": "",
                "download_url": "",
                "name": {"ar": "", "fr": "", "en": ""},
                "desc": {"ar": "", "fr": "", "en": ""},
                "version": "v1.0.0",
                "size": "20 MB",
                "rating": 4.8,
            }
        )

        content = BoxLayout(orientation="vertical", padding=dp(15), spacing=dp(10))
        with content.canvas.before:
            Color(0.96, 0.98, 0.96, 1)
            self.bg_rect1 = Rectangle(size=content.size, pos=content.pos)
        content.bind(
            size=lambda s, w: setattr(self.bg_rect1, "size", s.size),
            pos=lambda s, w: setattr(self.bg_rect1, "pos", s.pos),
        )
        content.add_widget(Label(
            text=format_ar("إدارة المنتجات"),
            font_size=sp(16), bold=True, color=(0.05, 0.58, 0.38, 1),
            size_hint_y=None, height=dp(35),
            font_name=FONT_PATH if FONT_PATH else "Roboto",
        ))
        btn_translate = Button(
            text=format_ar("ترجمة آلية سريعة"),
            size_hint_y=None, height=dp(42),
            background_color=(0.15, 0.35, 0.55, 1),
            color=(1, 1, 1, 1),
            font_name=FONT_PATH if FONT_PATH else "Roboto",
        )
        scroll = ScrollView()
        form_layout = GridLayout(cols=1, spacing=dp(8), size_hint_y=None)
        form_layout.bind(minimum_height=form_layout.setter("height"))

        self.inputs = {}
        fields = [
            ("category", "النوع", p.get("category", "")),
            ("icon", "أيقونة FontAwesome", p.get("icon", "")),
            ("color", "لون Tailwind", p.get("color", "")),
            ("image", "رابط أو مسار الصورة", p.get("image", "")),
            ("download_url", "رابط التحميل (Download URL)", p.get("download_url", "")),
            ("name_ar", "الاسم (عربي)", p.get("name", {}).get("ar", "")),
            ("name_fr", "الاسم (فرنسي)", p.get("name", {}).get("fr", "")),
            ("name_en", "الاسم (إنجليزي)", p.get("name", {}).get("en", "")),
            ("desc_ar", "الوصف (عربي)", p.get("desc", {}).get("ar", "")),
            ("desc_fr", "الوصف (فرنسي)", p.get("desc", {}).get("fr", "")),
            ("desc_en", "الوصف (إنجليزي)", p.get("desc", {}).get("en", "")),
            ("version", "رقم الإصدار", p.get("version", "")),
            ("size", "الحجم", p.get("size", "")),
            ("rating", "التقييم (للزوار)", str(p.get("rating", 4.8))),
        ]

        for key, label_text, val in fields:
            lbl = Label(
                text=format_ar(label_text), color=(0.15, 0.15, 0.15, 1),
                size_hint_y=None, height=dp(25), halign="right",
                font_name=FONT_PATH if FONT_PATH else "Roboto",
            )
            form_layout.add_widget(lbl)

            if key == "category":
                spinner = Spinner(
                    text=val if val in ("desktop", "android") else "desktop",
                    values=("desktop", "android"),
                    size_hint_y=None, height=dp(40),
                    background_color=(0.15, 0.35, 0.55, 1),
                    color=(1, 1, 1, 1),
                )
                self.inputs[key] = spinner
                form_layout.add_widget(spinner)
                continue

            if key == "image":
                img_layout = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(5))
                ti_img = TextInput(
                    text=str(val), multiline=False, size_hint_x=0.70,
                    font_name=FONT_PATH if FONT_PATH else "Roboto",
                )
                self.inputs[key] = ti_img
                btn_browse = Button(
                    text=format_ar("استعراض"), size_hint_x=0.30,
                    background_color=(0.15, 0.35, 0.55, 1),
                    color=(1, 1, 1, 1),
                    font_name=FONT_PATH if FONT_PATH else "Roboto",
                )
                btn_browse.bind(on_press=lambda x, field=ti_img: self.open_file_chooser_popup(field))
                img_layout.add_widget(ti_img)
                img_layout.add_widget(btn_browse)
                form_layout.add_widget(img_layout)
                continue

            ti = TextInput(
                text=str(val), multiline=False,
                size_hint_y=None, height=dp(40),
                font_name=FONT_PATH if FONT_PATH else "Roboto",
            )
            self.inputs[key] = ti
            form_layout.add_widget(ti)

        def run_translation(instance):
            ar_n = self.inputs["name_ar"].text.strip()
            ar_d = self.inputs["desc_ar"].text.strip()
            if not ar_n and not ar_d:
                self.status_label.text = format_ar("أدخل النص بالعربية أولاً للترجمة.")
                return
            btn_translate.disabled = True
            self.status_label.text = format_ar("جاري الترجمة...")

            def background_task():
                tr_name_fr = translate_text(ar_n, "fr") if ar_n else ""
                tr_name_en = translate_text(ar_n, "en") if ar_n else ""
                tr_desc_fr = translate_text(ar_d, "fr") if ar_d else ""
                tr_desc_en = translate_text(ar_d, "en") if ar_d else ""

                def update_ui(dt):
                    if tr_name_fr:
                        self.inputs["name_fr"].text = tr_name_fr
                    if tr_name_en:
                        self.inputs["name_en"].text = tr_name_en
                    if tr_desc_fr:
                        self.inputs["desc_fr"].text = tr_desc_fr
                    if tr_desc_en:
                        self.inputs["desc_en"].text = tr_desc_en
                    got_any = any([tr_name_fr, tr_name_en, tr_desc_fr, tr_desc_en])
                    if got_any:
                        self.status_label.text = format_ar("تمت الترجمة الآلية بنجاح!")
                    else:
                        self.status_label.text = format_ar("فشلت الترجمة. تحقق من الإنترنت.")
                    btn_translate.disabled = False

                Clock.schedule_once(update_ui, 0)

            threading.Thread(target=background_task, daemon=True).start()

        btn_translate.bind(on_press=run_translation)
        scroll.add_widget(form_layout)
        content.add_widget(btn_translate)
        content.add_widget(scroll)

        btn_box = BoxLayout(size_hint_y=None, height=dp(45), spacing=dp(10))
        btn_save_p = Button(
            text=format_ar("حفظ المنتج"),
            background_color=(0.05, 0.58, 0.38, 1),
            color=(1, 1, 1, 1),
            font_name=FONT_PATH if FONT_PATH else "Roboto",
        )
        btn_cancel = Button(
            text=format_ar("إلغاء"),
            background_color=(0.7, 0.2, 0.2, 1),
            color=(1, 1, 1, 1),
            font_name=FONT_PATH if FONT_PATH else "Roboto",
        )

        popup = Popup(
            title="", content=content,
            size_hint=(0.95, 0.95),
            separator_color=(0.05, 0.58, 0.38, 1),
        )

        def save_action(instance):
            try:
                new_p = {
                    "id": p.get("id", len(self.products) + 1),
                    "category": self.inputs["category"].text.strip(),
                    "icon": self.inputs["icon"].text.strip(),
                    "color": self.inputs["color"].text.strip(),
                    "image": os.path.basename(self.inputs["image"].text.strip()),
                    "download_url": self.inputs["download_url"].text.strip(),
                    "name": {
                        "ar": self.inputs["name_ar"].text.strip(),
                        "fr": self.inputs["name_fr"].text.strip(),
                        "en": self.inputs["name_en"].text.strip(),
                    },
                    "desc": {
                        "ar": self.inputs["desc_ar"].text.strip(),
                        "fr": self.inputs["desc_fr"].text.strip(),
                        "en": self.inputs["desc_en"].text.strip(),
                    },
                    "version": self.inputs["version"].text.strip(),
                    "size": self.inputs["size"].text.strip(),
                    "rating": float(self.inputs["rating"].text.strip()),
                }
                if is_edit:
                    self.products[idx] = new_p
                else:
                    self.products.append(new_p)
                self.refresh_products_list()
                self.status_label.text = format_ar("تم التحديث. اضغط 'حفظ' في الأعلى.")
                popup.dismiss()
            except Exception as e:
                self.status_label.text = format_ar(f"خطأ في الحفظ: {str(e)[:25]}")

        btn_save_p.bind(on_press=save_action)
        btn_cancel.bind(on_press=popup.dismiss)
        btn_box.add_widget(btn_save_p)
        btn_box.add_widget(btn_cancel)
        content.add_widget(btn_box)
        popup.open()

    def save_html(self, instance):
        try:
            with open(self.html_path, "r", encoding="utf-8") as f:
                content = f.read()
            new_json = self.json_to_js(self.products)
            new_content = self._replace_products_array(content, new_json)
            if new_content is None:
                self.status_label.text = format_ar("لم أجد مصفوفة المنتجات في index.html")
                return
            with open(self.html_path, "w", encoding="utf-8") as f:
                f.write(new_content)
            self.status_label.text = format_ar("تم حفظ index.html بنجاح!")
        except Exception as e:
            self.status_label.text = format_ar(f"خطأ حفظ: {str(e)[:40]}")

    def _gh_config_path(self):
        return os.path.join(App.get_running_app().user_data_dir, "github_config.json")

    def load_gh_config(self):
        try:
            with open(self._gh_config_path(), "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def store_gh_config(self, user, repo, token):
        try:
            os.makedirs(os.path.dirname(self._gh_config_path()), exist_ok=True)
            with open(self._gh_config_path(), "w", encoding="utf-8") as f:
                json.dump({"user": user, "repo": repo, "token": token}, f)
        except Exception:
            pass

    def save_and_push(self, instance):
        cfg = self.load_gh_config()
        if not (cfg.get("user") and cfg.get("repo") and cfg.get("token")):
            self.open_github_popup(None, then_push=True)
            return
        self.save_html(None)
        self.status_label.text = format_ar("جاري الرفع إلى GitHub...")
        self.push_to_github(
            cfg["user"], cfg["repo"], cfg["token"],
            lambda msg: setattr(self.status_label, "text", format_ar(msg)),
        )

    def push_to_github(self, user, repo, token, status_cb):
        def set_status(msg):
            Clock.schedule_once(lambda dt: status_cb(msg), 0)

        def background_push():
            try:
                headers = {
                    "Authorization": f"token {token}",
                    "Accept": "application/vnd.github.v3+json",
                    "User-Agent": "TechVault-DZ-App",
                }
                files = [("index.html", self.html_path)]
                logo_path = os.path.join(BASE_DIR, "logo.png")
                if os.path.exists(logo_path):
                    files.append(("logo.png", logo_path))

                for p in self.products:
                    img_name = p.get("image", "")
                    if img_name and not img_name.startswith("http"):
                        local_img_path = self.full_image_paths.get(img_name, "")
                        if not local_img_path or not os.path.exists(local_img_path):
                            candidate = os.path.join(BASE_DIR, img_name)
                            if os.path.exists(candidate):
                                local_img_path = candidate
                            else:
                                sd_path = os.path.join("/sdcard/Download", img_name)
                                if os.path.exists(sd_path):
                                    local_img_path = sd_path
                        if (local_img_path and os.path.exists(local_img_path)
                                and (img_name, local_img_path) not in files):
                            files.append((img_name, local_img_path))

                for name, path in files:
                    api_url = f"https://api.github.com/repos/{user}/{repo}/contents/{name}"
                    sha = ""
                    try:
                        req_get = urllib.request.Request(api_url, headers=headers)
                        with urllib.request.urlopen(req_get, context=SSL_CONTEXT) as resp:
                            sha = json.loads(resp.read().decode("utf-8")).get("sha", "")
                    except Exception:
                        pass
                    with open(path, "rb") as f:
                        file_bytes = f.read()
                    encoded = base64.b64encode(file_bytes).decode("utf-8")
                    payload = {
                        "message": f"Update {name} via TechVault DZ Dashboard",
                        "content": encoded,
                        "branch": "main",
                    }
                    if sha:
                        payload["sha"] = sha
                    req_put = urllib.request.Request(
                        api_url,
                        data=json.dumps(payload).encode("utf-8"),
                        headers=headers, method="PUT",
                    )
                    try:
                        with urllib.request.urlopen(req_put, context=SSL_CONTEXT) as resp:
                            pass
                    except urllib.error.HTTPError as e:
                        error_body = e.read().decode("utf-8")
                        raise Exception(f"فشل رفع {name} ({e.code}): {error_body[:80]}")

                set_status("تم الحفظ ورفع الملفات والصور إلى GitHub بنجاح!")
            except Exception as e:
                set_status(f"خطأ أثناء الرفع: {str(e)[:80]}")

        threading.Thread(target=background_push, daemon=True).start()

    def open_github_popup(self, instance, then_push=False):
        saved_cfg = self.load_gh_config()
        content = BoxLayout(orientation="vertical", padding=dp(15), spacing=dp(10))
        with content.canvas.before:
            Color(0.96, 0.98, 0.96, 1)
            self.bg_rect2 = Rectangle(size=content.size, pos=content.pos)
        content.bind(
            size=lambda s, w: setattr(self.bg_rect2, "size", s.size),
            pos=lambda s, w: setattr(self.bg_rect2, "pos", s.pos),
        )
        content.add_widget(Label(
            text=format_ar("مزامنة GitHub"),
            font_size=sp(16), bold=True, color=(0.05, 0.58, 0.38, 1),
            size_hint_y=None, height=dp(35),
            font_name=FONT_PATH if FONT_PATH else "Roboto",
        ))
        content.add_widget(Label(
            text=format_ar("اسم المالك أو المنظمة (Owner):"),
            color=(0.15, 0.15, 0.15, 1),
            size_hint_y=None, height=dp(25),
            font_name=FONT_PATH if FONT_PATH else "Roboto",
        ))
        ti_user = TextInput(
            text=saved_cfg.get("user", ""), multiline=False,
            size_hint_y=None, height=dp(40),
            font_name=FONT_PATH if FONT_PATH else "Roboto",
        )
        content.add_widget(ti_user)
        content.add_widget(Label(
            text=format_ar("اسم المستودع (Repository Name):"),
            color=(0.15, 0.15, 0.15, 1),
            size_hint_y=None, height=dp(25),
            font_name=FONT_PATH if FONT_PATH else "Roboto",
        ))
        ti_repo = TextInput(
            text=saved_cfg.get("repo", ""), multiline=False,
            size_hint_y=None, height=dp(40),
            font_name=FONT_PATH if FONT_PATH else "Roboto",
        )
        content.add_widget(ti_repo)
        content.add_widget(Label(
            text=format_ar("رمز الوصول (Personal Access Token):"),
            color=(0.15, 0.15, 0.15, 1),
            size_hint_y=None, height=dp(25),
            font_name=FONT_PATH if FONT_PATH else "Roboto",
        ))
        ti_token = TextInput(
            text=saved_cfg.get("token", ""), password=True, multiline=False,
            size_hint_y=None, height=dp(40),
            font_name=FONT_PATH if FONT_PATH else "Roboto",
        )
        content.add_widget(ti_token)
        lbl_git_status = Label(
            text="", color=(0.05, 0.58, 0.38, 1),
            size_hint_y=None, height=dp(25),
            font_name=FONT_PATH if FONT_PATH else "Roboto",
        )
        content.add_widget(lbl_git_status)

        popup = Popup(
            title="", content=content,
            size_hint=(0.9, 0.75),
            separator_color=(0.05, 0.58, 0.38, 1),
        )

        btn_box = BoxLayout(size_hint_y=None, height=dp(45), spacing=dp(10))
        btn_push = Button(
            text=format_ar("حفظ البيانات"),
            background_color=(0.05, 0.58, 0.38, 1),
            color=(1, 1, 1, 1),
            font_name=FONT_PATH if FONT_PATH else "Roboto",
        )
        btn_cancel = Button(
            text=format_ar("إلغاء"),
            background_color=(0.7, 0.2, 0.2, 1),
            color=(1, 1, 1, 1),
            font_name=FONT_PATH if FONT_PATH else "Roboto",
        )

        def save_action(btn):
            user = ti_user.text.strip()
            repo = ti_repo.text.strip()
            token = ti_token.text.strip()
            if not user or not repo or not token:
                lbl_git_status.text = format_ar("الرجاء ملء جميع الحقول المطلوبة!")
                return
            self.store_gh_config(user, repo, token)
            lbl_git_status.text = format_ar("تم حفظ البيانات بنجاح!")
            popup.dismiss()

        btn_push.bind(on_press=save_action)
        btn_cancel.bind(on_press=popup.dismiss)
        btn_box.add_widget(btn_push)
        btn_box.add_widget(btn_cancel)
        content.add_widget(btn_box)
        popup.open()


# ===================== 4. Logs =====================
class LogsScreen(Screen):
    def __init__(self, **kwargs):
        super(LogsScreen, self).__init__(**kwargs)
        scroll = ScrollView()
        layout = BoxLayout(
            orientation="vertical", padding=dp(15), spacing=dp(12), size_hint_y=None
        )
        layout.bind(minimum_height=layout.setter("height"))
        logo_path = os.path.join(BASE_DIR, "logo.png")
        if os.path.exists(logo_path):
            layout.add_widget(Image(source=logo_path, size_hint_y=None, height=dp(90), allow_stretch=True))
        layout.add_widget(Label(
            text=format_ar("سجلات الأمان والاتصال (Secure Logs)"),
            font_size=sp(16), bold=True, color=(0.7, 0.2, 0.2, 1),
            size_hint_y=None, height=dp(30),
            font_name=FONT_PATH if FONT_PATH else "Roboto",
        ))
        for log in [
            "2026-06-06 12:00:22 - Admin Login Successful [DZ]",
            "2026-06-06 12:10:05 - index.html updated successfully",
            "2026-06-06 12:15:30 - Product added to vault (Desktop)",
        ]:
            layout.add_widget(Label(
                text=log, size_hint_y=None, height=dp(30),
                color=(0.3, 0.3, 0.3, 1),
                font_name=FONT_PATH if FONT_PATH else "Roboto",
            ))
        btn_back = Button(
            text=format_ar("العودة للرئيسية"),
            size_hint_y=None, height=dp(45),
            background_color=(0.25, 0.25, 0.25, 1),
            color=(1, 1, 1, 1),
            font_name=FONT_PATH if FONT_PATH else "Roboto",
        )
        btn_back.bind(on_press=lambda x: setattr(self.manager, "current", "home"))
        layout.add_widget(btn_back)
        scroll.add_widget(layout)
        self.add_widget(scroll)


# ===================== 5. Settings =====================
class SettingsScreen(Screen):
    def __init__(self, **kwargs):
        super(SettingsScreen, self).__init__(**kwargs)
        scroll = ScrollView()
        layout = BoxLayout(
            orientation="vertical", padding=dp(15), spacing=dp(12), size_hint_y=None
        )
        layout.bind(minimum_height=layout.setter("height"))
        logo_path = os.path.join(BASE_DIR, "logo.png")
        if os.path.exists(logo_path):
            layout.add_widget(Image(source=logo_path, size_hint_y=None, height=dp(90), allow_stretch=True))
        layout.add_widget(Label(
            text=format_ar("إعدادات الحساب والنظام (Account Settings)"),
            font_size=sp(16), bold=True, color=(0.15, 0.35, 0.55, 1),
            size_hint_y=None, height=dp(30),
            font_name=FONT_PATH if FONT_PATH else "Roboto",
        ))
        layout.add_widget(Label(
            text=format_ar("إصدار التطبيق: v2.1.0 (TechVault DZ)"),
            size_hint_y=None, height=dp(25), color=(0.2, 0.2, 0.2, 1),
            font_name=FONT_PATH if FONT_PATH else "Roboto",
        ))
        layout.add_widget(Label(
            text=format_ar("حالة الاتصال: متصل بالخزنة المحلية"),
            size_hint_y=None, height=dp(25), color=(0.2, 0.2, 0.2, 1),
            font_name=FONT_PATH if FONT_PATH else "Roboto",
        ))
        btn_change_pass = Button(
            text=format_ar("تغيير كلمة المرور (Change Password)"),
            size_hint_y=None, height=dp(45),
            background_color=(0.8, 0.5, 0.1, 1),
            color=(1, 1, 1, 1), font_size=sp(14), bold=True,
            font_name=FONT_PATH if FONT_PATH else "Roboto",
        )
        btn_change_pass.bind(on_press=self.open_change_password_popup)
        layout.add_widget(btn_change_pass)
        btn_gh_settings = Button(
            text=format_ar("بيانات GitHub (تغيير)"),
            size_hint_y=None, height=dp(45),
            background_color=(0.1, 0.1, 0.1, 1),
            color=(1, 1, 1, 1), font_size=sp(14), bold=True,
            font_name=FONT_PATH if FONT_PATH else "Roboto",
        )
        btn_gh_settings.bind(on_press=lambda x: self.manager.get_screen("products").open_github_popup(None))
        layout.add_widget(btn_gh_settings)
        btn_reset_html = Button(
            text=format_ar("إعادة تعيين index.html للأصل"),
            size_hint_y=None, height=dp(45),
            background_color=(0.5, 0.2, 0.5, 1),
            color=(1, 1, 1, 1), font_size=sp(14), bold=True,
            font_name=FONT_PATH if FONT_PATH else "Roboto",
        )
        btn_reset_html.bind(on_press=lambda x: self.manager.get_screen("products").reset_to_bundled_html())
        layout.add_widget(btn_reset_html)
        self.msg_label = Label(
            text="", color=(0.05, 0.58, 0.38, 1),
            size_hint_y=None, height=dp(25),
            font_name=FONT_PATH if FONT_PATH else "Roboto",
        )
        layout.add_widget(self.msg_label)
        btn_back = Button(
            text=format_ar("العودة للرئيسية"),
            size_hint_y=None, height=dp(45),
            background_color=(0.25, 0.25, 0.25, 1),
            color=(1, 1, 1, 1),
            font_name=FONT_PATH if FONT_PATH else "Roboto",
        )
        btn_back.bind(on_press=lambda x: setattr(self.manager, "current", "home"))
        layout.add_widget(btn_back)
        scroll.add_widget(layout)
        self.add_widget(scroll)

    def open_change_password_popup(self, instance):
        content = BoxLayout(orientation="vertical", padding=dp(15), spacing=dp(10))
        with content.canvas.before:
            Color(0.96, 0.98, 0.96, 1)
            self.bg_rect3 = Rectangle(size=content.size, pos=content.pos)
        content.bind(
            size=lambda s, w: setattr(self.bg_rect3, "size", s.size),
            pos=lambda s, w: setattr(self.bg_rect3, "pos", s.pos),
        )
        content.add_widget(Label(
            text=format_ar("تغيير كلمة المرور"),
            font_size=sp(16), bold=True, color=(0.05, 0.58, 0.38, 1),
            size_hint_y=None, height=dp(35),
            font_name=FONT_PATH if FONT_PATH else "Roboto",
        ))
        content.add_widget(Label(
            text=format_ar("كلمة المرور الحالية:"),
            color=(0.15, 0.15, 0.15, 1),
            size_hint_y=None, height=dp(25),
            font_name=FONT_PATH if FONT_PATH else "Roboto",
        ))
        old_pass = TextInput(
            password=True, multiline=False,
            size_hint_y=None, height=dp(40),
            font_name=FONT_PATH if FONT_PATH else "Roboto",
        )
        content.add_widget(old_pass)
        content.add_widget(Label(
            text=format_ar("كلمة المرور الجديدة:"),
            color=(0.15, 0.15, 0.15, 1),
            size_hint_y=None, height=dp(25),
            font_name=FONT_PATH if FONT_PATH else "Roboto",
        ))
        new_pass = TextInput(
            password=True, multiline=False,
            size_hint_y=None, height=dp(40),
            font_name=FONT_PATH if FONT_PATH else "Roboto",
        )
        content.add_widget(new_pass)
        popup = Popup(
            title="", content=content,
            size_hint=(0.85, 0.5),
            separator_color=(0.05, 0.58, 0.38, 1),
        )
        btn_box = BoxLayout(size_hint_y=None, height=dp(45), spacing=dp(10))
        btn_save = Button(
            text=format_ar("حفظ"),
            background_color=(0.05, 0.58, 0.38, 1),
            color=(1, 1, 1, 1),
            font_name=FONT_PATH if FONT_PATH else "Roboto",
        )
        btn_cancel = Button(
            text=format_ar("إلغاء"),
            background_color=(0.7, 0.2, 0.2, 1),
            color=(1, 1, 1, 1),
            font_name=FONT_PATH if FONT_PATH else "Roboto",
        )

        def save_new_password(btn):
            app_instance = App.get_running_app()
            if old_pass.text.strip() == app_instance.vault_password:
                if new_pass.text.strip():
                    app_instance.vault_password = new_pass.text.strip()
                    self.msg_label.text = format_ar("تم تغيير كلمة المرور بنجاح!")
                    popup.dismiss()
                else:
                    self.msg_label.text = format_ar("كلمة المرور الجديدة لا يمكن أن تكون فارغة!")
            else:
                self.msg_label.text = format_ar("كلمة المرور الحالية غير صحيحة!")

        btn_save.bind(on_press=save_new_password)
        btn_cancel.bind(on_press=popup.dismiss)
        btn_box.add_widget(btn_save)
        btn_box.add_widget(btn_cancel)
        content.add_widget(btn_box)
        popup.open()


# ===================== App =====================
class TechVaultApp(App):
    vault_password = "1234"

    def build(self):
        self.title = "TechVault DZ Dashboard"
        if _kivy_platform == "android":
            request_android_permissions()
        sm = ScreenManager()
        sm.add_widget(SplashScreen(name="splash"))
        sm.add_widget(LoginScreen(name="login"))
        sm.add_widget(HomeScreen(name="home"))
        sm.add_widget(ProductsScreen(name="products"))
        sm.add_widget(LogsScreen(name="logs"))
        sm.add_widget(SettingsScreen(name="settings"))
        Window.bind(on_keyboard=self._on_keyboard)
        if _kivy_platform == "android":
            Clock.schedule_once(lambda dt: self._check_all_files_once(), 3.0)
        Clock.schedule_once(lambda dt: setattr(sm, "current", "login"), 2.5)
        return sm

    def _check_all_files_once(self):
        if has_manage_external_storage():
            return
        content = BoxLayout(orientation="vertical", padding=dp(15), spacing=dp(10))
        with content.canvas.before:
            Color(0.96, 0.98, 0.96, 1)
            self.bg_chk = Rectangle(size=content.size, pos=content.pos)
        content.bind(
            size=lambda s, w: setattr(self.bg_chk, "size", s.size),
            pos=lambda s, w: setattr(self.bg_chk, "pos", s.pos),
        )
        content.add_widget(Label(
            text=format_ar("تفعيل صلاحية الملفات"),
            font_size=sp(16), bold=True, color=(0.7, 0.2, 0.2, 1),
            size_hint_y=None, height=dp(35),
            font_name=FONT_PATH if FONT_PATH else "Roboto",
        ))
        msg = Label(
            text=format_ar(
                "لفتح ملفات HTML من هاتفك،\n"
                "يحتاج التطبيق إلى صلاحية\n"
                "'الوصول لجميع الملفات'."
            ),
            font_size=sp(12), halign="center",
            color=(0.15, 0.15, 0.15, 1),
            font_name=FONT_PATH if FONT_PATH else "Roboto",
        )
        msg.bind(width=lambda s, w: setattr(s, "text_size", (w, None)))
        content.add_widget(msg)
        popup = Popup(
            title="", content=content,
            size_hint=(0.9, 0.45),
            separator_color=(0.7, 0.2, 0.2, 1),
        )
        btn_box = BoxLayout(size_hint_y=None, height=dp(50), spacing=dp(10))
        btn_open = Button(
            text=format_ar("فتح الإعدادات"),
            background_color=(0.05, 0.58, 0.38, 1),
            color=(1, 1, 1, 1), bold=True,
            font_name=FONT_PATH if FONT_PATH else "Roboto",
        )

        def open_settings(btn):
            popup.dismiss()
            open_all_files_settings()

        btn_open.bind(on_press=open_settings)
        btn_cancel = Button(
            text=format_ar("لاحقاً"),
            background_color=(0.25, 0.25, 0.25, 1),
            color=(1, 1, 1, 1),
            font_name=FONT_PATH if FONT_PATH else "Roboto",
        )
        btn_cancel.bind(on_press=popup.dismiss)
        btn_box.add_widget(btn_open)
        btn_box.add_widget(btn_cancel)
        content.add_widget(btn_box)
        popup.open()

    def _on_keyboard(self, window, key, *args):
        if key == 27:
            sm = self.root
            if sm and sm.current not in ["home", "login", "splash"]:
                sm.current = "home"
                return True
        return False


if __name__ == "__main__":
    try:
        TechVaultApp().run()
    except Exception as e:
        _log_startup_error(e)
        raise