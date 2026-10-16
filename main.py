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
from datetime import datetime

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.core.text import LabelBase
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
        err = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        for p in ["/storage/emulated/0/Documents/techvault_error.txt",
                  os.path.join(os.path.expanduser("~"), "techvault_error.txt")]:
            try:
                os.makedirs(os.path.dirname(p), exist_ok=True)
                with open(p, "w", encoding="utf-8") as f:
                    f.write(err)
                break
            except Exception:
                continue
    except Exception:
        pass


def _debug_log(msg):
    print(f"[TechVault] {msg}")
    try:
        with open("/storage/emulated/0/techvault_picker.log", "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().isoformat()}] {msg}\n")
    except Exception:
        try:
            with open("/sdcard/techvault_picker.log", "a", encoding="utf-8") as f:
                f.write(f"[{datetime.now().isoformat()}] {msg}\n")
        except Exception:
            pass


# ============ SSL ============
try:
    import certifi
    SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())
except Exception as e:
    _debug_log(f"SSL fallback: {e}")
    SSL_CONTEXT = ssl._create_unverified_context()

Window.clearcolor = (0.95, 0.97, 0.95, 1)

# ============ دعم العربية ============
try:
    import arabic_reshaper
    from bidi.algorithm import get_display
    HAS_BIDI = True
except ImportError:
    HAS_BIDI = False

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def _find_font():
    for name in ("arabic.ttf", "Cairo-Regular.ttf", "Amiri-Regular.ttf"):
        p = os.path.join(BASE_DIR, name)
        if os.path.exists(p):
            return p
    return None


FONT_PATH = _find_font()
_debug_log(f"BASE_DIR={BASE_DIR} FONT_PATH={FONT_PATH}")

if FONT_PATH:
    try:
        LabelBase.register(name="Roboto", fn_regular=FONT_PATH)
        _debug_log("Roboto replaced with Arabic font")
    except Exception as e:
        _debug_log(f"Roboto replace failed: {e}")


def _user_index_path():
    try:
        return os.path.join(App.get_running_app().user_data_dir, "index.html")
    except Exception:
        return os.path.join(BASE_DIR, "index.html")


def format_ar(text):
    if text is None:
        return ""
    s = str(text)
    if HAS_BIDI:
        try:
            if any("\u0600" <= c <= "\u06ff" for c in s):
                return get_display(arabic_reshaper.reshape(s))
        except Exception:
            return s
    return s


# ============ Android Permissions ============
def request_android_permissions():
    if _kivy_platform != "android":
        return
    try:
        from android.permissions import request_permissions, Permission
        request_permissions([Permission.READ_EXTERNAL_STORAGE,
                             Permission.WRITE_EXTERNAL_STORAGE])
    except Exception as e:
        _debug_log(f"permissions error: {e}")


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
        _debug_log(f"check all files error: {e}")
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
        _debug_log(f"open all files settings error: {e}")


# ============ URI → path ============
def _uri_to_path(uri):
    try:
        from jnius import autoclass
        Build = autoclass('android.os.Build')
        PythonActivity = autoclass('org.kivy.android.PythonActivity')
        context = PythonActivity.mActivity
        try:
            ContentResolver = context.getContentResolver()
            cursor = ContentResolver.query(uri, None, None, None, None)
            if cursor is not None:
                try:
                    data_idx = cursor.getColumnIndex("_data")
                    if data_idx >= 0 and cursor.moveToFirst():
                        path = cursor.getString(data_idx)
                        if path and os.path.exists(path):
                            return path
                finally:
                    cursor.close()
        except Exception as e:
            _debug_log(f"_data query error: {e}")

        if Build.VERSION.SDK_INT >= 19:
            try:
                DocumentsContract = autoclass('android.provider.DocumentsContract')
                if DocumentsContract.isDocumentUri(context, uri):
                    doc_id = DocumentsContract.getDocumentId(uri)
                    if ":" in doc_id:
                        _, rel_path = doc_id.split(":", 1)
                        candidate = "/storage/emulated/0/" + rel_path
                        if os.path.exists(candidate):
                            return candidate
            except Exception as e:
                _debug_log(f"DocumentsContract error: {e}")

        return _copy_uri_to_cache(uri)
    except Exception as e:
        _debug_log(f"uri_to_path error: {e}")
        return None


def _copy_uri_to_cache(uri):
    try:
        from jnius import autoclass
        PythonActivity = autoclass('org.kivy.android.PythonActivity')
        context = PythonActivity.mActivity
        ContentResolver = context.getContentResolver()

        name = "picked_file"
        try:
            cursor = ContentResolver.query(uri, None, None, None, None)
            if cursor is not None:
                try:
                    idx = cursor.getColumnIndex("_display_name")
                    if idx >= 0 and cursor.moveToFirst():
                        n = cursor.getString(idx)
                        if n:
                            name = n
                finally:
                    cursor.close()
        except Exception:
            pass

        cache_dir = context.getCacheDir().getAbsolutePath()
        dest = os.path.join(cache_dir, name)

        input_stream = ContentResolver.openInputStream(uri)
        if input_stream is None:
            return None

        FileOutputStream = autoclass('java.io.FileOutputStream')
        output_stream = FileOutputStream(dest)
        buf = bytearray(8192)
        while True:
            n = input_stream.read(buf)
            if n <= 0:
                break
            output_stream.write(buf, 0, n)
        output_stream.close()
        input_stream.close()
        _debug_log(f"Copied URI -> {dest}")
        return dest
    except Exception as e:
        _debug_log(f"copy to cache error: {e}")
        return None


# ============ كشف بيئة Intent ============
def _can_use_android_intent():
    if _kivy_platform != "android":
        return False
    try:
        from jnius import autoclass
        autoclass('org.kivy.android.PythonActivity')
        autoclass('org.kivy.android.PythonActivity$ActivityResultListener')
        return True
    except Exception as e:
        _debug_log(f"Intent unavailable: {e}")
        return False


# ============ منتقي Kivy العربي (Pydroid) ============
def _pick_files_kivy_fallback(on_result, mime_type="*/*", multiple=False):
    _debug_log(f"Kivy picker: mime={mime_type} multi={multiple}")

    start = None
    if _kivy_platform == "android":
        for cand in ("/storage/emulated/0/Download",
                     "/storage/emulated/0/Documents",
                     "/storage/emulated/0",
                     "/sdcard"):
            if os.path.exists(cand):
                start = cand
                break
    if not start:
        start = os.path.expanduser("~")

    filters = []
    if "html" in mime_type:
        filters = ["*.html", "*.htm", "*.HTML", "*.HTM"]
    elif "image" in mime_type:
        filters = ["*.png", "*.jpg", "*.jpeg",
                   "*.PNG", "*.JPG", "*.JPEG", "*.webp"]

    state = {"path": start, "selection": set()}

    root = BoxLayout(orientation="vertical", padding=dp(10), spacing=dp(8))

    # شريط علوي
    path_bar = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(6))
    btn_up = Button(
        text=format_ar("⬆ أعلى"), size_hint_x=None, width=dp(80),
        background_color=(0.08, 0.45, 0.75, 1),
        color=(1, 1, 1, 1), bold=True,
        font_name=FONT_PATH if FONT_PATH else "Roboto")
    path_lbl = Label(
        text="", color=(0.15, 0.15, 0.15, 1),
        font_size=sp(12), halign="right", valign="middle",
        size_hint_x=1,
        font_name=FONT_PATH if FONT_PATH else "Roboto")
    path_lbl.bind(width=lambda s, w: setattr(s, "text_size", (w, None)))
    path_bar.add_widget(btn_up)
    path_bar.add_widget(path_lbl)
    root.add_widget(path_bar)

    # قائمة الملفات
    scroll = ScrollView(bar_width=dp(3))
    files_box = BoxLayout(orientation="vertical", size_hint_y=None,
                          spacing=dp(2), padding=dp(2))
    files_box.bind(minimum_height=files_box.setter("height"))
    scroll.add_widget(files_box)
    root.add_widget(scroll)

    # أزرار
    bottom = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(8))
    btn_ok = Button(
        text=format_ar("تأكيد"), bold=True,
        background_color=(0.08, 0.45, 0.75, 1),
        color=(1, 1, 1, 1),
        font_name=FONT_PATH if FONT_PATH else "Roboto")
    btn_cancel = Button(
        text=format_ar("إلغاء"),
        background_color=(0.75, 0.22, 0.17, 1),
        color=(1, 1, 1, 1),
        font_name=FONT_PATH if FONT_PATH else "Roboto")
    bottom.add_widget(btn_ok)
    bottom.add_widget(btn_cancel)
    root.add_widget(bottom)

    info_lbl = Label(
        text="", color=(0.4, 0.4, 0.4, 1),
        size_hint_y=None, height=dp(20), font_size=sp(11),
        font_name=FONT_PATH if FONT_PATH else "Roboto")
    root.add_widget(info_lbl)

    popup = Popup(title="", content=root, size_hint=(0.95, 0.92),
                  separator_color=(0.08, 0.45, 0.75, 1))

    def _match_filter(name):
        if not filters:
            return True
        low = name.lower()
        for f in filters:
            pattern = f.lower().replace("*", "")
            if low.endswith(pattern):
                return True
        return False

    def _make_row(icon_text, display_name, raw_name, is_dir, full_path):
        is_selected = full_path in state["selection"]
        row = BoxLayout(
            orientation="horizontal", size_hint_y=None,
            height=dp(46), spacing=dp(8), padding=(dp(10), dp(4)))
        row.canvas.before.clear()
        with row.canvas.before:
            if is_dir:
                Color(0.92, 0.95, 1, 1)
            elif is_selected:
                Color(0.85, 0.93, 1, 1)
            else:
                Color(1, 1, 1, 1)
            bg = Rectangle(pos=row.pos, size=row.size)
            if is_selected and not is_dir:
                Color(0.08, 0.45, 0.75, 1)
                Rectangle(pos=row.pos, size=(dp(3), row.height))
        row.bind(
            pos=lambda i, v: setattr(bg, "pos", i.pos),
            size=lambda i, v: setattr(bg, "size", i.size))

        icon_lbl = Label(
            text=icon_text, size_hint_x=None, width=dp(36),
            font_size=sp(20), halign="center", valign="middle",
            font_name=FONT_PATH if FONT_PATH else "Roboto")
        row.add_widget(icon_lbl)

        display = format_ar(display_name) if display_name else ""
        if is_dir:
            color = (0.08, 0.30, 0.55, 1)
        elif is_selected:
            color = (0.08, 0.45, 0.75, 1)
        else:
            color = (0.15, 0.15, 0.15, 1)

        name_lbl = Label(
            text=display, color=color,
            font_size=sp(14), bold=is_dir,
            halign="right", valign="middle", size_hint_x=1,
            font_name=FONT_PATH if FONT_PATH else "Roboto",
            shorten=True, shorten_from="right")
        name_lbl.bind(width=lambda s, w: setattr(s, "text_size", (w, None)))
        row.add_widget(name_lbl)

        if is_dir:
            row.add_widget(Label(
                text=format_ar("◀"), color=(0.4, 0.4, 0.4, 1),
                size_hint_x=None, width=dp(24), font_size=sp(14),
                font_name=FONT_PATH if FONT_PATH else "Roboto"))
        else:
            check_lbl = Label(
                text="●" if is_selected else "○",
                color=(0.08, 0.45, 0.75, 1) if is_selected else (0.7, 0.7, 0.7, 1),
                size_hint_x=None, width=dp(28),
                font_size=sp(16), halign="center", valign="middle",
                font_name=FONT_PATH if FONT_PATH else "Roboto")
            row.add_widget(check_lbl)

        def on_touch_down(touch):
            if not row.collide_point(*touch.pos):
                return False
            if is_dir:
                state["path"] = full_path
                state["selection"] = set()
                refresh_list()
            else:
                if multiple:
                    if full_path in state["selection"]:
                        state["selection"].discard(full_path)
                    else:
                        state["selection"].add(full_path)
                    refresh_list()
                else:
                    state["selection"] = {full_path}
                    refresh_list()
            return True

        row.on_touch_down = on_touch_down
        return row

    def refresh_list():
        files_box.clear_widgets()
        current = state["path"]
        path_lbl.text = format_ar(current)

        try:
            entries = os.listdir(current)
        except PermissionError:
            files_box.add_widget(Label(
                text=format_ar("صلاحية مرفوضة"),
                color=(0.7, 0.2, 0.2, 1), size_hint_y=None, height=dp(60),
                font_name=FONT_PATH if FONT_PATH else "Roboto"))
            return
        except Exception as e:
            files_box.add_widget(Label(
                text=format_ar(f"خطأ: {str(e)[:40]}"),
                color=(0.7, 0.2, 0.2, 1), size_hint_y=None, height=dp(60),
                font_name=FONT_PATH if FONT_PATH else "Roboto"))
            return

        dirs, files = [], []
        for name in sorted(entries, key=lambda s: s.lower()):
            if name.startswith("."):
                continue
            full = os.path.join(current, name)
            try:
                if os.path.isdir(full):
                    dirs.append((name, full))
                else:
                    if _match_filter(name):
                        files.append((name, full))
            except Exception:
                continue

        parent = os.path.dirname(current.rstrip("/")) or "/"
        if parent != current:
            files_box.add_widget(_make_row("📁", ".. (أعلى)", "..", True, parent))

        for name, full in dirs:
            files_box.add_widget(_make_row("📁", name, name, True, full))

        for name, full in files:
            files_box.add_widget(_make_row("📄", name, name, False, full))

        if not dirs and not files:
            files_box.add_widget(Label(
                text=format_ar("لا توجد ملفات مطابقة"),
                color=(0.5, 0.5, 0.5, 1), size_hint_y=None, height=dp(60),
                font_name=FONT_PATH if FONT_PATH else "Roboto"))

        n = len(state["selection"])
        if n == 0:
            info_lbl.text = format_ar("اختر ملفاً")
        elif n == 1:
            info_lbl.text = format_ar(
                f"محدد: {os.path.basename(list(state['selection'])[0])}")
        else:
            info_lbl.text = format_ar(f"{n} ملفات محددة")

    def _up(btn):
        current = state["path"].rstrip("/")
        parent = os.path.dirname(current) or "/"
        if parent != current:
            state["path"] = parent
            state["selection"] = set()
            refresh_list()

    btn_up.bind(on_press=_up)

    def _ok(btn):
        paths = list(state["selection"])
        popup.dismiss()
        on_result(paths)

    def _cancel(btn):
        popup.dismiss()
        on_result([])

    btn_ok.bind(on_press=_ok)
    btn_cancel.bind(on_press=_cancel)

    refresh_list()
    popup.open()


# ============ منتقي موحّد ============
_PICKER_BOUND = {"cb": None}
_PICKER_LOCK = {"active": False, "ts": 0}


def pick_files(on_result, mime_type="*/*", multiple=False):
    """منتقي موحّد: ACTION_OPEN_DOCUMENT في APK، Kivy في Pydroid/Desktop."""
    import time as _tm
    now = _tm.time()

    if _PICKER_LOCK["active"] and (now - _PICKER_LOCK["ts"]) < 2.0:
        _debug_log("Picker already active, ignoring")
        return
    _PICKER_LOCK["active"] = True
    _PICKER_LOCK["ts"] = now

    def _release():
        _PICKER_LOCK["active"] = False

    def _safe_result(paths):
        _release()
        try:
            on_result(paths)
        except Exception as e:
            _debug_log(f"on_result error: {e}")

    _debug_log(f"=== pick_files START mime={mime_type} multi={multiple} ===")

    if _kivy_platform != "android":
        _pick_files_kivy_fallback(_safe_result, mime_type, multiple)
        return

    if not _can_use_android_intent():
        _debug_log("Pydroid mode → Kivy picker")
        _pick_files_kivy_fallback(_safe_result, mime_type, multiple)
        return

    try:
        from jnius import autoclass
        from android import activity as android_activity
        Intent = autoclass('android.content.Intent')
        PythonActivity = autoclass('org.kivy.android.PythonActivity')
    except Exception as e:
        _debug_log(f"imports failed: {e}")
        _pick_files_kivy_fallback(_safe_result, mime_type, multiple)
        return

    REQUEST_CODE = 0x4B01

    old_cb = _PICKER_BOUND.get("cb")
    if old_cb is not None:
        try:
            android_activity.unbind(on_activity_result=old_cb)
        except Exception:
            pass
        _PICKER_BOUND["cb"] = None

    try:
        # ACTION_OPEN_DOCUMENT يفتح مدير الملفات (ليس معرض صور)
        intent = Intent(Intent.ACTION_OPEN_DOCUMENT)
        intent.addCategory(Intent.CATEGORY_OPENABLE)
        intent.setType("*/*")
        intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
        intent.addFlags(Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION)
        if multiple:
            intent.putExtra(Intent.EXTRA_ALLOW_MULTIPLE, True)
        _debug_log("Intent ACTION_OPEN_DOCUMENT built")
    except Exception as e:
        _debug_log(f"Intent build failed: {e}")
        _pick_files_kivy_fallback(_safe_result, mime_type, multiple)
        return

    _called = {"done": False}

    def _on_activity_result(req_code, result_code, data):
        _debug_log(f"on_activity_result req={req_code} result={result_code}")
        if req_code != REQUEST_CODE:
            return False
        if _called["done"]:
            return True
        _called["done"] = True

        try:
            android_activity.unbind(on_activity_result=_on_activity_result)
            _PICKER_BOUND["cb"] = None
        except Exception:
            pass

        if result_code != -1 or data is None:
            _debug_log("Cancelled")
            Clock.schedule_once(lambda dt: _safe_result([]), 0)
            return True

        paths = []
        try:
            clip = data.getClipData()
            if clip is not None:
                for i in range(clip.getItemCount()):
                    p = _uri_to_path(clip.getItemAt(i).getUri())
                    if p:
                        paths.append(p)
            else:
                u = data.getData()
                if u is not None:
                    p = _uri_to_path(u)
                    if p:
                        paths.append(p)
        except Exception as e:
            _debug_log(f"parse error: {e}")

        # فلترة حسب النوع
        if "image" in mime_type:
            filtered = [p for p in paths
                        if os.path.splitext(p)[1].lower() in
                        (".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp")]
            paths = filtered if filtered else paths

        _debug_log(f"Returning {len(paths)} paths")
        Clock.schedule_once(lambda dt: _safe_result(paths), 0)
        return True

    try:
        android_activity.bind(on_activity_result=_on_activity_result)
        _PICKER_BOUND["cb"] = _on_activity_result
        _debug_log("Callback bound")
    except Exception as e:
        _debug_log(f"bind FAILED: {e}")
        _pick_files_kivy_fallback(_safe_result, mime_type, multiple)
        return

    try:
        from jnius import PythonJavaClass, java_method

        class _LaunchRunnable(PythonJavaClass):
            __javainterfaces__ = ['java/lang/Runnable']
            __javacontext__ = 'app'

            def __init__(self, intent_obj, code):
                super().__init__()
                self._intent = intent_obj
                self._code = code

            @java_method('()V')
            def run(self):
                try:
                    PythonActivity.mActivity.startActivityForResult(
                        self._intent, self._code)
                    _debug_log("startActivity dispatched")
                except Exception as e:
                    _debug_log(f"startActivity FAILED: {e}")
                    Clock.schedule_once(lambda dt: _safe_result([]), 0)

        runnable = _LaunchRunnable(intent, REQUEST_CODE)
        PythonActivity.mActivity.runOnUiThread(runnable)
    except Exception as e:
        _debug_log(f"UI thread failed: {e}")
        try:
            PythonActivity.mActivity.startActivityForResult(intent, REQUEST_CODE)
        except Exception as e2:
            _debug_log(f"Direct start failed: {e2}")
            _pick_files_kivy_fallback(_safe_result, mime_type, multiple)


# ============ الترجمة (4 محاولات) ============
def _split_text_for_translation(text, max_len=800):
    if len(text) <= max_len:
        return [text]
    chunks, current = [], ""
    for para in text.split("\n"):
        if len(current) + len(para) + 1 <= max_len:
            current = current + "\n" + para if current else para
        else:
            if current:
                chunks.append(current)
            if len(para) > max_len:
                sentences = re.split(r'(?<=[.!؟?])\s+', para)
                sub = ""
                for s in sentences:
                    if len(sub) + len(s) + 1 <= max_len:
                        sub = sub + " " + s if sub else s
                    else:
                        if sub:
                            chunks.append(sub)
                        sub = s
                if sub:
                    chunks.append(sub)
                current = ""
            else:
                current = para
    if current:
        chunks.append(current)
    return chunks


def _translate_chunk(text, target_lang, source_lang="ar"):
    if not text.strip():
        return ""

    # محاولة 1: Google Translate
    try:
        url = ("https://translate.googleapis.com/translate_a/single"
               f"?client=gtx&sl={source_lang}&tl={target_lang}&dt=t&q="
               + urllib.parse.quote(text))
        req = urllib.request.Request(url, headers={
            "User-Agent": ("Mozilla/5.0 (Linux; Android 13; SM-G991B) "
                           "AppleWebKit/537.36 (KHTML, like Gecko) "
                           "Chrome/120.0.0.0 Mobile Safari/537.36"),
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.9,ar;q=0.8",
            "Referer": "https://translate.google.com/",
        })
        with urllib.request.urlopen(req, timeout=12, context=SSL_CONTEXT) as r:
            raw = r.read().decode("utf-8", errors="ignore")
        data = json.loads(raw)
        if data and isinstance(data, list) and data[0]:
            parts = []
            for seg in data[0]:
                if seg and isinstance(seg, list) and seg[0]:
                    parts.append(seg[0])
            result = "".join(parts).strip()
            if result and result.lower() != text.lower():
                _debug_log(f"✓ Google OK: {len(text)}→{len(result)}")
                return result
    except Exception as e:
        _debug_log(f"✗ Google failed: {e}")

    # محاولة 2: MyMemory
    try:
        url = (f"https://api.mymemory.translated.net/get"
               f"?q={urllib.parse.quote(text[:500])}&langpair={source_lang}|{target_lang}")
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Linux; Android 13)"})
        with urllib.request.urlopen(req, timeout=12, context=SSL_CONTEXT) as r:
            raw = r.read().decode("utf-8", errors="ignore")
        data = json.loads(raw)
        if str(data.get("responseStatus")) == "200":
            result = data.get("responseData", {}).get("translatedText", "").strip()
            if result and result.lower() != text.lower():
                _debug_log("✓ MyMemory OK")
                return result
    except Exception as e:
        _debug_log(f"✗ MyMemory failed: {e}")

    # محاولة 3: Lingva
    try:
        encoded = urllib.parse.quote(text)
        url = f"https://lingva.ml/api/v1/{source_lang}/{target_lang}/{encoded}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=12, context=SSL_CONTEXT) as r:
            data = json.loads(r.read().decode("utf-8"))
        result = (data.get("translation") or "").strip()
        if result and result.lower() != text.lower():
            _debug_log("✓ Lingva OK")
            return result
    except Exception as e:
        _debug_log(f"✗ Lingva failed: {e}")

    # محاولة 4: LibreTranslate
    try:
        post_data = json.dumps({
            "q": text, "source": source_lang,
            "target": target_lang, "format": "text"
        }).encode("utf-8")
        req = urllib.request.Request(
            "https://libretranslate.com/translate",
            data=post_data,
            headers={"Content-Type": "application/json",
                     "User-Agent": "Mozilla/5.0"},
            method="POST")
        with urllib.request.urlopen(req, timeout=12, context=SSL_CONTEXT) as r:
            data = json.loads(r.read().decode("utf-8"))
        result = (data.get("translatedText") or "").strip()
        if result and result.lower() != text.lower():
            _debug_log("✓ LibreTranslate OK")
            return result
    except Exception as e:
        _debug_log(f"✗ LibreTranslate failed: {e}")

    return ""


def translate_text(text, target_lang):
    if not text or not text.strip():
        return ""
    chunks = _split_text_for_translation(text, max_len=800)
    results = []
    for chunk in chunks:
        if not chunk.strip():
            continue
        r = _translate_chunk(chunk, target_lang)
        if r:
            results.append(r)
        else:
            results.append("")
    return "\n".join(results).strip()


# ===================== 0. Splash =====================
class SplashScreen(Screen):
    def __init__(self, **kwargs):
        super(SplashScreen, self).__init__(**kwargs)
        layout = BoxLayout(orientation="vertical", padding=dp(30), spacing=dp(15))
        logo_path = os.path.join(BASE_DIR, "logo.png")
        if os.path.exists(logo_path):
            layout.add_widget(Image(source=logo_path, allow_stretch=True,
                                    keep_ratio=True, size_hint=(1, 1)))
        else:
            layout.add_widget(Label(
                text="TechVault DZ", font_size=sp(30), bold=True,
                color=(0.05, 0.58, 0.38, 1),
                font_name=FONT_PATH if FONT_PATH else "Roboto"))
        layout.add_widget(Label(
            text=format_ar("الخزنة الجزائرية للبرمجيات"),
            font_size=sp(14), color=(0.3, 0.3, 0.3, 1),
            size_hint_y=None, height=dp(30),
            font_name=FONT_PATH if FONT_PATH else "Roboto"))
        self.add_widget(layout)


# ===================== 1. Login =====================
class LoginScreen(Screen):
    def __init__(self, **kwargs):
        super(LoginScreen, self).__init__(**kwargs)
        layout = BoxLayout(orientation="vertical", padding=dp(20), spacing=dp(12),
                           size_hint=(0.9, None), height=dp(380),
                           pos_hint={"center_x": 0.5, "center_y": 0.5})
        logo_path = os.path.join(BASE_DIR, "logo.png")
        if os.path.exists(logo_path):
            layout.add_widget(Image(source=logo_path, size_hint_y=None,
                                    height=dp(110), allow_stretch=True))
        layout.add_widget(Label(
            text=format_ar("TechVault DZ - قفل الخزنة"),
            font_size=sp(18), bold=True, color=(0.05, 0.58, 0.38, 1),
            size_hint_y=None, height=dp(30),
            font_name=FONT_PATH if FONT_PATH else "Roboto"))
        layout.add_widget(Label(
            text=format_ar("أدخل كلمة المرور:"),
            font_size=sp(13), color=(0.3, 0.3, 0.3, 1),
            size_hint_y=None, height=dp(25),
            font_name=FONT_PATH if FONT_PATH else "Roboto"))
        self.pass_input = TextInput(password=True, multiline=False,
                                    font_size=sp(16), size_hint_y=None,
                                    height=dp(42),
                                    font_name=FONT_PATH if FONT_PATH else "Roboto")
        layout.add_widget(self.pass_input)
        btn_login = Button(
            text=format_ar("فتح الخزنة"), size_hint_y=None, height=dp(48),
            background_color=(0.05, 0.58, 0.38, 1),
            color=(1, 1, 1, 1), font_size=sp(15), bold=True,
            font_name=FONT_PATH if FONT_PATH else "Roboto")
        btn_login.bind(on_press=self.check_password)
        layout.add_widget(btn_login)
        self.error_label = Label(text="", color=(0.7, 0.2, 0.2, 1),
                                 size_hint_y=None, height=dp(25),
                                 font_name=FONT_PATH if FONT_PATH else "Roboto")
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
        layout = BoxLayout(orientation="vertical", padding=dp(20), spacing=dp(15),
                           size_hint=(0.9, None), height=dp(420),
                           pos_hint={"center_x": 0.5, "center_y": 0.5})
        logo_path = os.path.join(BASE_DIR, "logo.png")
        if os.path.exists(logo_path):
            layout.add_widget(Image(source=logo_path, size_hint_y=None,
                                    height=dp(120), allow_stretch=True,
                                    keep_ratio=True))
        btn_vault = Button(
            text=format_ar("Open Vault (إدارة المنتجات)"),
            size_hint_y=None, height=dp(50),
            background_color=(0.05, 0.58, 0.38, 1),
            color=(1, 1, 1, 1), font_size=sp(14), bold=True,
            font_name=FONT_PATH if FONT_PATH else "Roboto")
        btn_vault.bind(on_press=lambda x: setattr(self.manager, "current", "products"))
        btn_logs = Button(
            text=format_ar("View Secure Logs (سجلات الأمان)"),
            size_hint_y=None, height=dp(50),
            background_color=(0.7, 0.2, 0.2, 1),
            color=(1, 1, 1, 1), font_size=sp(14), bold=True,
            font_name=FONT_PATH if FONT_PATH else "Roboto")
        btn_logs.bind(on_press=lambda x: setattr(self.manager, "current", "logs"))
        btn_settings = Button(
            text=format_ar("Account Settings (الإعدادات)"),
            size_hint_y=None, height=dp(50),
            background_color=(0.15, 0.35, 0.55, 1),
            color=(1, 1, 1, 1), font_size=sp(14), bold=True,
            font_name=FONT_PATH if FONT_PATH else "Roboto")
        btn_settings.bind(on_press=lambda x: setattr(self.manager, "current", "settings"))
        btn_lock = Button(
            text=format_ar("قفل التطبيق"),
            size_hint_y=None, height=dp(50),
            background_color=(0.25, 0.25, 0.25, 1),
            color=(1, 1, 1, 1), font_size=sp(14), bold=True,
            font_name=FONT_PATH if FONT_PATH else "Roboto")
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
        self.current_screenshots = []

        user_html = _user_index_path()
        self.html_path = user_html if os.path.exists(user_html) else self.bundled_html_path

        root = BoxLayout(orientation="vertical", padding=dp(10), spacing=dp(8))

        top_bar = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(4))
        btn_back = Button(text=format_ar("رئيسية"), size_hint_x=0.20,
                          background_color=(0.25, 0.25, 0.25, 1),
                          color=(1, 1, 1, 1), font_size=sp(12),
                          font_name=FONT_PATH if FONT_PATH else "Roboto")
        btn_back.bind(on_press=lambda x: setattr(self.manager, "current", "home"))
        btn_reload = Button(text=format_ar("إعادة تحميل"), size_hint_x=0.26,
                            background_color=(0.15, 0.35, 0.55, 1),
                            color=(1, 1, 1, 1), font_size=sp(12),
                            font_name=FONT_PATH if FONT_PATH else "Roboto")
        btn_reload.bind(on_press=self.load_html)
        btn_open = Button(text=format_ar("فتح ملف"), size_hint_x=0.26,
                          background_color=(0.8, 0.5, 0.1, 1),
                          color=(1, 1, 1, 1), font_size=sp(12), bold=True,
                          font_name=FONT_PATH if FONT_PATH else "Roboto")
        btn_open.bind(on_press=lambda x: self.open_html_chooser_popup())
        btn_from_gh = Button(text=format_ar("من GitHub"), size_hint_x=0.28,
                             background_color=(0.1, 0.1, 0.1, 1),
                             color=(1, 1, 1, 1), font_size=sp(12), bold=True,
                             font_name=FONT_PATH if FONT_PATH else "Roboto")
        btn_from_gh.bind(on_press=lambda x: self.download_html_from_github())
        top_bar.add_widget(btn_back)
        top_bar.add_widget(btn_reload)
        top_bar.add_widget(btn_open)
        top_bar.add_widget(btn_from_gh)
        root.add_widget(top_bar)

        action_bar = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(4))
        btn_add = Button(text=format_ar("إضافة منتج"), size_hint_x=0.35,
                         background_color=(0.05, 0.58, 0.38, 1),
                         color=(1, 1, 1, 1), font_size=sp(13), bold=True,
                         font_name=FONT_PATH if FONT_PATH else "Roboto")
        btn_add.bind(on_press=lambda x: self.open_product_form())
        btn_save = Button(text=format_ar("حفظ ورفع إلى GitHub"), size_hint_x=0.65,
                          background_color=(0.7, 0.2, 0.2, 1),
                          color=(1, 1, 1, 1), font_size=sp(13), bold=True,
                          font_name=FONT_PATH if FONT_PATH else "Roboto")
        btn_save.bind(on_press=self.save_and_push)
        action_bar.add_widget(btn_add)
        action_bar.add_widget(btn_save)
        root.add_widget(action_bar)

        self.status_label = Label(
            text=format_ar("إدارة منتجات TechVault DZ"),
            size_hint_y=None, height=dp(28), color=(0.2, 0.2, 0.2, 1),
            font_size=sp(12), font_name=FONT_PATH if FONT_PATH else "Roboto")
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
        depth, in_str, esc, i = 0, None, False, start
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
                if c in ("'", '"'):
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
        out, i, n = [], 0, len(js_str)
        in_str, esc = None, False
        while i < n:
            c = js_str[i]
            if in_str:
                if esc:
                    out.append(c); esc = False
                elif c == "\\":
                    out.append(c); esc = True
                elif c == in_str:
                    out.append('"'); in_str = None
                elif c == '"':
                    out.append('\\"')
                else:
                    out.append(c)
                i += 1
                continue
            if c in ("'", '"'):
                in_str = c; out.append('"')
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
            json_str = self.js_to_json(content[start:end])
            self.products = json.loads(json_str)
            self.status_label.text = format_ar(f"تم تحميل {len(self.products)} منتج بنجاح.")
            self.refresh_products_list()
        except json.JSONDecodeError as e:
            self.status_label.text = format_ar(f"خطأ JSON: {str(e)[:40]}")
            self.products = []
            self.refresh_products_list()
        except Exception as e:
            self.status_label.text = format_ar(f"خطأ: {str(e)[:40]}")
            _debug_log(f"load_html error: {e}")

    def refresh_products_list(self):
        try:
            self.products_layout.clear_widgets()
            if not self.products:
                lbl = Label(text=format_ar("لا توجد منتجات بعد\nاضغط 'إضافة منتج' للبدء"),
                            color=(0.5, 0.5, 0.5, 1), font_size=sp(14),
                            halign="center", valign="middle",
                            size_hint_y=None, height=dp(80),
                            font_name=FONT_PATH if FONT_PATH else "Roboto")
                lbl.bind(width=lambda s, w: setattr(s, "text_size", (w, None)))
                self.products_layout.add_widget(lbl)
                return

            for i, p in enumerate(self.products):
                name_ar = p.get("name", {}).get("ar", "بدون اسم")
                name_fr = p.get("name", {}).get("fr", "")
                cat = p.get("category", "desktop").upper()
                version = p.get("version", "v1.0.0")
                size_mb = p.get("size", "—")
                rating = p.get("rating", 0)
                n_shots = len(p.get("screenshots", []))
                accent = (0.05, 0.58, 0.38, 1) if cat == "ANDROID" else (0.15, 0.35, 0.55, 1)

                card = BoxLayout(orientation="horizontal", size_hint_y=None,
                                 height=dp(120), padding=dp(10), spacing=dp(10))
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

                card.add_widget(Label(text="[b]●[/b]", markup=True, color=accent,
                                      font_size=sp(20), size_hint_x=None, width=dp(30),
                                      halign="center", valign="middle"))

                info_box = BoxLayout(orientation="vertical", spacing=dp(4))
                title_lbl = Label(text=format_ar(name_ar), color=(0.1, 0.1, 0.1, 1),
                                  font_size=sp(14), bold=True,
                                  halign="right", valign="top",
                                  size_hint_y=None, height=dp(46),
                                  font_name=FONT_PATH if FONT_PATH else "Roboto")
                title_lbl.bind(width=lambda s, w: setattr(s, "text_size", (w, None)))
                info_box.add_widget(title_lbl)

                if name_fr:
                    sub = Label(text=str(name_fr), color=(0.5, 0.5, 0.5, 1),
                                font_size=sp(11), halign="right", valign="middle",
                                size_hint_y=None, height=dp(18),
                                font_name=FONT_PATH if FONT_PATH else "Roboto")
                    sub.bind(width=lambda s, w: setattr(s, "text_size", (w, None)))
                    info_box.add_widget(sub)

                shots_part = f"  •  📷 {n_shots}" if n_shots > 0 else ""
                details = Label(text=f"{version}  •  {size_mb}  •  {rating} / 5{shots_part}",
                                color=(0.4, 0.4, 0.4, 1), font_size=sp(11),
                                halign="right", valign="middle",
                                size_hint_y=None, height=dp(18),
                                font_name=FONT_PATH if FONT_PATH else "Roboto")
                details.bind(width=lambda s, w: setattr(s, "text_size", (w, None)))
                info_box.add_widget(details)
                card.add_widget(info_box)

                card.add_widget(Label(text=cat, color=accent, font_size=sp(11),
                                      bold=True, halign="center", valign="middle",
                                      size_hint_x=None, width=dp(80),
                                      font_name=FONT_PATH if FONT_PATH else "Roboto"))

                def make_clickable(c, idx):
                    def on_touch_down(touch):
                        if c.collide_point(*touch.pos):
                            try:
                                self.open_product_options(idx)
                            except Exception as e:
                                _debug_log(f"open options error: {e}")
                            return True
                        return False
                    return on_touch_down

                card.on_touch_down = make_clickable(card, i)
                self.products_layout.add_widget(card)
        except Exception as e:
            _debug_log(f"refresh_products_list error: {e}\n{traceback.format_exc()}")

    def open_product_options(self, idx):
        if not (0 <= idx < len(self.products)):
            return
        p = self.products[idx]
        name_ar = p.get("name", {}).get("ar", "بدون اسم")
        cat = p.get("category", "desktop").upper()
        version = p.get("version", "v1.0.0")
        size_mb = p.get("size", "—")
        n_shots = len(p.get("screenshots", []))

        content = BoxLayout(orientation="vertical", padding=dp(18), spacing=dp(14))
        with content.canvas.before:
            Color(1, 1, 1, 1)
            self.bg_options = Rectangle(size=content.size, pos=content.pos)
        content.bind(size=lambda s, w: setattr(self.bg_options, "size", s.size),
                     pos=lambda s, w: setattr(self.bg_options, "pos", s.pos))

        title_lbl = Label(text=format_ar(name_ar), font_size=sp(17), bold=True,
                          color=(0.1, 0.1, 0.1, 1), halign="center", valign="middle",
                          size_hint_y=None, height=dp(40),
                          font_name=FONT_PATH if FONT_PATH else "Roboto")
        title_lbl.bind(width=lambda s, w: setattr(s, "text_size", (w, None)))
        content.add_widget(title_lbl)

        content.add_widget(Label(
            text=format_ar(f"{cat}  •  {version}  •  {size_mb}  •  📷 {n_shots}"),
            font_size=sp(12), color=(0.5, 0.5, 0.5, 1),
            halign="center", valign="middle", size_hint_y=None, height=dp(24),
            font_name=FONT_PATH if FONT_PATH else "Roboto"))

        popup = Popup(title="", content=content, size_hint=(0.85, 0.5),
                      separator_color=(0.15, 0.35, 0.55, 1),
                      background_color=(0, 0, 0, 0.5))

        btn_edit = Button(text=format_ar("تعديل المنتج"), size_hint_y=None, height=dp(52),
                          background_color=(0.15, 0.35, 0.55, 1),
                          color=(1, 1, 1, 1), font_size=sp(15), bold=True,
                          font_name=FONT_PATH if FONT_PATH else "Roboto")

        def do_edit(btn):
            popup.dismiss()
            Clock.schedule_once(lambda dt: self.open_product_form(idx=idx), 0.3)

        btn_edit.bind(on_press=do_edit)
        content.add_widget(btn_edit)

        btn_del = Button(text=format_ar("حذف المنتج"), size_hint_y=None, height=dp(52),
                         background_color=(0.7, 0.2, 0.2, 1),
                         color=(1, 1, 1, 1), font_size=sp(15), bold=True,
                         font_name=FONT_PATH if FONT_PATH else "Roboto")

        def do_delete(btn):
            popup.dismiss()
            Clock.schedule_once(lambda dt: self.confirm_delete_product(idx), 0.3)

        btn_del.bind(on_press=do_delete)
        content.add_widget(btn_del)

        btn_close = Button(text=format_ar("إغلاق"), size_hint_y=None, height=dp(48),
                           background_color=(0.5, 0.5, 0.5, 1),
                           color=(1, 1, 1, 1), font_size=sp(14),
                           font_name=FONT_PATH if FONT_PATH else "Roboto")
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
        content.bind(size=lambda s, w: setattr(self.bg_del, "size", s.size),
                     pos=lambda s, w: setattr(self.bg_del, "pos", s.pos))

        content.add_widget(Label(text=format_ar("تأكيد الحذف"), font_size=sp(17),
                                 bold=True, color=(0.7, 0.2, 0.2, 1),
                                 halign="center", valign="middle",
                                 size_hint_y=None, height=dp(36),
                                 font_name=FONT_PATH if FONT_PATH else "Roboto"))

        msg = Label(text=format_ar(f"هل أنت متأكد من حذف:\n\n« {name_ar} »\n\nلا يمكن التراجع."),
                    font_size=sp(13), halign="center", valign="middle",
                    color=(0.2, 0.2, 0.2, 1), size_hint_y=None, height=dp(110),
                    font_name=FONT_PATH if FONT_PATH else "Roboto")
        msg.bind(width=lambda s, w: setattr(s, "text_size", (w, None)))
        content.add_widget(msg)

        popup = Popup(title="", content=content, size_hint=(0.85, 0.45),
                      separator_color=(0.7, 0.2, 0.2, 1),
                      background_color=(0, 0, 0, 0.5))
        btn_box = BoxLayout(size_hint_y=None, height=dp(50), spacing=dp(10))

        def do_delete(btn):
            popup.dismiss()
            del self.products[idx]
            self.refresh_products_list()
            self.status_label.text = format_ar("تم الحذف. اضغط 'حفظ ورفع إلى GitHub' في الأعلى.")

        btn_yes = Button(text=format_ar("نعم، احذف"),
                         background_color=(0.7, 0.2, 0.2, 1),
                         color=(1, 1, 1, 1), font_size=sp(14), bold=True,
                         font_name=FONT_PATH if FONT_PATH else "Roboto")
        btn_yes.bind(on_press=do_delete)
        btn_no = Button(text=format_ar("إلغاء"),
                        background_color=(0.5, 0.5, 0.5, 1),
                        color=(1, 1, 1, 1), font_size=sp(14),
                        font_name=FONT_PATH if FONT_PATH else "Roboto")
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
            _debug_log(f"save local copy error: {e}")
            return False

    def _show_all_files_dialog(self):
        content = BoxLayout(orientation="vertical", padding=dp(15), spacing=dp(10))
        with content.canvas.before:
            Color(0.96, 0.98, 0.96, 1)
            self.bg_perm = Rectangle(size=content.size, pos=content.pos)
        content.bind(size=lambda s, w: setattr(self.bg_perm, "size", s.size),
                     pos=lambda s, w: setattr(self.bg_perm, "pos", s.pos))
        content.add_widget(Label(text=format_ar("صلاحية مطلوبة"), font_size=sp(16),
                                 bold=True, color=(0.7, 0.2, 0.2, 1),
                                 size_hint_y=None, height=dp(35),
                                 font_name=FONT_PATH if FONT_PATH else "Roboto"))
        msg = Label(text=format_ar(
            "لتتمكن من فتح ملفات HTML من هاتفك،\n"
            "يجب تفعيل صلاحية 'الوصول لجميع الملفات'\n"
            "في إعدادات التطبيق.\n\n"
            "اضغط 'فتح الإعدادات' ثم اختر\n"
            "'السماح بالوصول لجميع الملفات'."),
            font_size=sp(12), halign="center", valign="middle",
            color=(0.15, 0.15, 0.15, 1),
            font_name=FONT_PATH if FONT_PATH else "Roboto")
        msg.bind(width=lambda s, w: setattr(s, "text_size", (w, None)))
        content.add_widget(msg)

        popup = Popup(title="", content=content, size_hint=(0.9, 0.55),
                      separator_color=(0.7, 0.2, 0.2, 1))
        btn_box = BoxLayout(size_hint_y=None, height=dp(50), spacing=dp(10))
        btn_open = Button(text=format_ar("فتح الإعدادات"),
                          background_color=(0.05, 0.58, 0.38, 1),
                          color=(1, 1, 1, 1), bold=True,
                          font_name=FONT_PATH if FONT_PATH else "Roboto")

        def open_settings(btn):
            popup.dismiss()
            open_all_files_settings()

        btn_open.bind(on_press=open_settings)
        btn_cancel = Button(text=format_ar("لاحقاً"),
                            background_color=(0.25, 0.25, 0.25, 1),
                            color=(1, 1, 1, 1),
                            font_name=FONT_PATH if FONT_PATH else "Roboto")
        btn_cancel.bind(on_press=popup.dismiss)
        btn_box.add_widget(btn_open)
        btn_box.add_widget(btn_cancel)
        content.add_widget(btn_box)
        popup.open()

    # منتقي HTML — يقبل أي ملف
    def open_html_chooser_popup(self):
        self.status_label.text = format_ar("جاري فتح منتقي الملفات...")

        def on_picked(paths):
            def ui_update(dt):
                if not paths:
                    self.status_label.text = format_ar("تم الإلغاء.")
                    return
                path = paths[0]
                _debug_log(f"HTML picked: {path}")
                ext = os.path.splitext(path)[1].lower()
                if ext not in (".html", ".htm", ".txt", ""):
                    self.status_label.text = format_ar(
                        f"الملف ليس HTML ({ext})")
                    return
                if self._save_local_copy(path):
                    self.status_label.text = format_ar(
                        f"تم فتح: {os.path.basename(path)}")
                    self.load_html(None)
                else:
                    self.status_label.text = format_ar("فشل نسخ الملف المختار.")
            Clock.schedule_once(ui_update, 0)

        # */* لأن text/html يفشل على أندرويد 11+
        pick_files(on_picked, mime_type="*/*", multiple=False)

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
                _debug_log(f"download html error: {e}")

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

    # استعراض صورة
    def open_file_chooser_popup(self, text_input_field):
        self.status_label.text = format_ar("جاري فتح منتقي الصور...")

        def on_picked(paths):
            def ui_update(dt):
                if paths:
                    path = paths[0]
                    filename = os.path.basename(path)
                    text_input_field.text = filename
                    self.full_image_paths[filename] = path
                    self.status_label.text = format_ar(f"تم اختيار: {filename}")
                else:
                    self.status_label.text = format_ar("لم يتم اختيار صورة.")
            Clock.schedule_once(ui_update, 0)

        pick_files(on_picked, mime_type="image/*", multiple=False)

    # لقطات الشاشة
    def open_screenshots_chooser(self, on_done):
        self.status_label.text = format_ar("جاري فتح منتقي الصور المتعدد...")

        def on_picked(paths):
            def ui_update(dt):
                added = 0
                for path in paths:
                    filename = os.path.basename(path)
                    if filename not in self.current_screenshots:
                        self.current_screenshots.append(filename)
                        added += 1
                    self.full_image_paths[filename] = path
                self.status_label.text = format_ar(f"تمت إضافة {added} صورة.")
                on_done()
            Clock.schedule_once(ui_update, 0)

        pick_files(on_picked, mime_type="image/*", multiple=True)

    def open_product_form(self, idx=None):
        is_edit = idx is not None
        p = (self.products[idx] if is_edit else {
            "id": len(self.products) + 1, "category": "desktop",
            "icon": "fa-solid fa-code", "color": "from-blue-500 to-indigo-600",
            "image": "", "download_url": "", "screenshots": [],
            "name": {"ar": "", "fr": "", "en": ""},
            "desc": {"ar": "", "fr": "", "en": ""},
            "version": "v1.0.0", "size": "20 MB", "rating": 4.8})

        self.current_screenshots = list(p.get("screenshots", []))

        content = BoxLayout(orientation="vertical", padding=dp(15), spacing=dp(10))
        with content.canvas.before:
            Color(0.96, 0.98, 0.96, 1)
            self.bg_rect1 = Rectangle(size=content.size, pos=content.pos)
        content.bind(size=lambda s, w: setattr(self.bg_rect1, "size", s.size),
                     pos=lambda s, w: setattr(self.bg_rect1, "pos", s.pos))
        content.add_widget(Label(text=format_ar("إدارة المنتجات"), font_size=sp(16),
                                 bold=True, color=(0.05, 0.58, 0.38, 1),
                                 size_hint_y=None, height=dp(35),
                                 font_name=FONT_PATH if FONT_PATH else "Roboto"))
        btn_translate = Button(text=format_ar("ترجمة آلية سريعة"),
                               size_hint_y=None, height=dp(42),
                               background_color=(0.15, 0.35, 0.55, 1),
                               color=(1, 1, 1, 1),
                               font_name=FONT_PATH if FONT_PATH else "Roboto")
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
            form_layout.add_widget(Label(
                text=format_ar(label_text), color=(0.15, 0.15, 0.15, 1),
                size_hint_y=None, height=dp(25), halign="right",
                font_name=FONT_PATH if FONT_PATH else "Roboto"))

            if key == "category":
                spinner = Spinner(
                    text=val if val in ("desktop", "android") else "desktop",
                    values=("desktop", "android"), size_hint_y=None, height=dp(40),
                    background_color=(0.15, 0.35, 0.55, 1), color=(1, 1, 1, 1))
                self.inputs[key] = spinner
                form_layout.add_widget(spinner)
                continue

            if key == "image":
                img_layout = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(5))
                ti_img = TextInput(text=str(val), multiline=False, size_hint_x=0.70,
                                   font_name=FONT_PATH if FONT_PATH else "Roboto")
                self.inputs[key] = ti_img
                btn_browse = Button(text=format_ar("استعراض"), size_hint_x=0.30,
                                    background_color=(0.15, 0.35, 0.55, 1),
                                    color=(1, 1, 1, 1),
                                    font_name=FONT_PATH if FONT_PATH else "Roboto")
                btn_browse.bind(on_press=lambda x, field=ti_img: self.open_file_chooser_popup(field))
                img_layout.add_widget(ti_img)
                img_layout.add_widget(btn_browse)
                form_layout.add_widget(img_layout)
                continue

            if key in ("desc_ar", "desc_fr", "desc_en"):
                ti = TextInput(text=str(val), multiline=True, size_hint_y=None,
                               height=dp(120),
                               font_name=FONT_PATH if FONT_PATH else "Roboto")
            else:
                ti = TextInput(text=str(val), multiline=False, size_hint_y=None,
                               height=dp(40),
                               font_name=FONT_PATH if FONT_PATH else "Roboto")
            self.inputs[key] = ti
            form_layout.add_widget(ti)

        form_layout.add_widget(Label(
            text=format_ar("لقطات الشاشة (Screenshots)"),
            color=(0.15, 0.15, 0.15, 1), size_hint_y=None,
            height=dp(28), halign="right",
            font_name=FONT_PATH if FONT_PATH else "Roboto"))

        self.screenshots_box = BoxLayout(orientation="vertical",
                                         size_hint_y=None, spacing=dp(4))
        self.screenshots_box.bind(minimum_height=self.screenshots_box.setter("height"))
        form_layout.add_widget(self.screenshots_box)

        def refresh_screenshots():
            self.screenshots_box.clear_widgets()
            if not self.current_screenshots:
                self.screenshots_box.add_widget(Label(
                    text=format_ar("لا توجد لقطات بعد"),
                    color=(0.6, 0.6, 0.6, 1), size_hint_y=None, height=dp(30),
                    font_name=FONT_PATH if FONT_PATH else "Roboto"))
                return
            for name in list(self.current_screenshots):
                row = BoxLayout(size_hint_y=None, height=dp(36), spacing=dp(6))
                lbl_name = Label(text=name, color=(0.2, 0.2, 0.2, 1),
                                 halign="left", valign="middle", size_hint_x=0.78,
                                 font_name=FONT_PATH if FONT_PATH else "Roboto")
                lbl_name.bind(width=lambda s, w: setattr(s, "text_size", (w, None)))
                row.add_widget(lbl_name)

                def make_del(n):
                    def _del(btn):
                        if n in self.current_screenshots:
                            self.current_screenshots.remove(n)
                        refresh_screenshots()
                    return _del

                del_btn = Button(text="✕", size_hint_x=0.22,
                                 background_color=(0.7, 0.2, 0.2, 1),
                                 color=(1, 1, 1, 1),
                                 font_name=FONT_PATH if FONT_PATH else "Roboto")
                del_btn.bind(on_press=make_del(name))
                row.add_widget(del_btn)
                self.screenshots_box.add_widget(row)

        btn_add_ss = Button(text=format_ar("+ إضافة لقطات شاشة"),
                            size_hint_y=None, height=dp(42),
                            background_color=(0.15, 0.35, 0.55, 1),
                            color=(1, 1, 1, 1), bold=True,
                            font_name=FONT_PATH if FONT_PATH else "Roboto")
        btn_add_ss.bind(on_press=lambda x: self.open_screenshots_chooser(refresh_screenshots))
        form_layout.add_widget(btn_add_ss)
        refresh_screenshots()

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
                    ok = False
                    if tr_name_fr:
                        self.inputs["name_fr"].text = tr_name_fr
                        ok = True
                    if tr_name_en:
                        self.inputs["name_en"].text = tr_name_en
                        ok = True
                    if tr_desc_fr:
                        self.inputs["desc_fr"].text = tr_desc_fr
                        ok = True
                    if tr_desc_en:
                        self.inputs["desc_en"].text = tr_desc_en
                        ok = True

                    self.status_label.text = format_ar(
                        "✓ تمت الترجمة بنجاح!" if ok
                        else "✗ فشلت الترجمة — تحقق من الإنترنت")
                    btn_translate.disabled = False

                Clock.schedule_once(update_ui, 0)

            threading.Thread(target=background_task, daemon=True).start()

        btn_translate.bind(on_press=run_translation)
        scroll.add_widget(form_layout)
        content.add_widget(btn_translate)
        content.add_widget(scroll)

        btn_box = BoxLayout(size_hint_y=None, height=dp(45), spacing=dp(10))
        btn_save_p = Button(text=format_ar("حفظ المنتج"),
                            background_color=(0.05, 0.58, 0.38, 1),
                            color=(1, 1, 1, 1),
                            font_name=FONT_PATH if FONT_PATH else "Roboto")
        btn_cancel = Button(text=format_ar("إلغاء"),
                            background_color=(0.7, 0.2, 0.2, 1),
                            color=(1, 1, 1, 1),
                            font_name=FONT_PATH if FONT_PATH else "Roboto")

        popup = Popup(title="", content=content, size_hint=(0.95, 0.95),
                      separator_color=(0.05, 0.58, 0.38, 1))

        def save_action(instance):
            try:
                new_p = {
                    "id": p.get("id", len(self.products) + 1),
                    "category": self.inputs["category"].text.strip(),
                    "icon": self.inputs["icon"].text.strip(),
                    "color": self.inputs["color"].text.strip(),
                    "image": os.path.basename(self.inputs["image"].text.strip()),
                    "download_url": self.inputs["download_url"].text.strip(),
                    "screenshots": list(self.current_screenshots),
                    "name": {
                        "ar": self.inputs["name_ar"].text.strip(),
                        "fr": self.inputs["name_fr"].text.strip(),
                        "en": self.inputs["name_en"].text.strip()},
                    "desc": {
                        "ar": self.inputs["desc_ar"].text.strip(),
                        "fr": self.inputs["desc_fr"].text.strip(),
                        "en": self.inputs["desc_en"].text.strip()},
                    "version": self.inputs["version"].text.strip(),
                    "size": self.inputs["size"].text.strip(),
                    "rating": float(self.inputs["rating"].text.strip() or 0),
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
            new_content = self._replace_products_array(content, self.json_to_js(self.products))
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
        self.push_to_github(cfg["user"], cfg["repo"], cfg["token"],
                            lambda msg: setattr(self.status_label, "text", format_ar(msg)))

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
                        local = self.full_image_paths.get(img_name, "")
                        if not local or not os.path.exists(local):
                            cand = os.path.join(BASE_DIR, img_name)
                            if os.path.exists(cand):
                                local = cand
                            else:
                                sd = os.path.join("/sdcard/Download", img_name)
                                if os.path.exists(sd):
                                    local = sd
                        if local and os.path.exists(local) and (img_name, local) not in files:
                            files.append((img_name, local))

                    for ss_name in p.get("screenshots", []):
                        if not ss_name or ss_name.startswith("http"):
                            continue
                        ss_path = self.full_image_paths.get(ss_name, "")
                        if not ss_path or not os.path.exists(ss_path):
                            cand = os.path.join(BASE_DIR, ss_name)
                            if os.path.exists(cand):
                                ss_path = cand
                            else:
                                sd = os.path.join("/sdcard/Download", ss_name)
                                if os.path.exists(sd):
                                    ss_path = sd
                        if ss_path and os.path.exists(ss_path) and (ss_name, ss_path) not in files:
                            files.append((ss_name, ss_path))

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
                        encoded = base64.b64encode(f.read()).decode("utf-8")
                    payload = {"message": f"Update {name} via TechVault DZ Dashboard",
                               "content": encoded, "branch": "main"}
                    if sha:
                        payload["sha"] = sha
                    req_put = urllib.request.Request(
                        api_url, data=json.dumps(payload).encode("utf-8"),
                        headers=headers, method="PUT")
                    try:
                        with urllib.request.urlopen(req_put, context=SSL_CONTEXT):
                            pass
                    except urllib.error.HTTPError as e:
                        err_body = e.read().decode("utf-8")
                        raise Exception(f"فشل رفع {name} ({e.code}): {err_body[:80]}")

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
        content.bind(size=lambda s, w: setattr(self.bg_rect2, "size", s.size),
                     pos=lambda s, w: setattr(self.bg_rect2, "pos", s.pos))
        content.add_widget(Label(text=format_ar("مزامنة GitHub"), font_size=sp(16),
                                 bold=True, color=(0.05, 0.58, 0.38, 1),
                                 size_hint_y=None, height=dp(35),
                                 font_name=FONT_PATH if FONT_PATH else "Roboto"))
        content.add_widget(Label(text=format_ar("اسم المالك (Owner):"),
                                 color=(0.15, 0.15, 0.15, 1), size_hint_y=None,
                                 height=dp(25),
                                 font_name=FONT_PATH if FONT_PATH else "Roboto"))
        ti_user = TextInput(text=saved_cfg.get("user", ""), multiline=False,
                            size_hint_y=None, height=dp(40),
                            font_name=FONT_PATH if FONT_PATH else "Roboto")
        content.add_widget(ti_user)
        content.add_widget(Label(text=format_ar("اسم المستودع (Repo):"),
                                 color=(0.15, 0.15, 0.15, 1), size_hint_y=None,
                                 height=dp(25),
                                 font_name=FONT_PATH if FONT_PATH else "Roboto"))
        ti_repo = TextInput(text=saved_cfg.get("repo", ""), multiline=False,
                            size_hint_y=None, height=dp(40),
                            font_name=FONT_PATH if FONT_PATH else "Roboto")
        content.add_widget(ti_repo)
        content.add_widget(Label(text=format_ar("رمز الوصول (Token):"),
                                 color=(0.15, 0.15, 0.15, 1), size_hint_y=None,
                                 height=dp(25),
                                 font_name=FONT_PATH if FONT_PATH else "Roboto"))
        ti_token = TextInput(text=saved_cfg.get("token", ""), password=True,
                             multiline=False, size_hint_y=None, height=dp(40),
                             font_name=FONT_PATH if FONT_PATH else "Roboto")
        content.add_widget(ti_token)
        lbl_status = Label(text="", color=(0.05, 0.58, 0.38, 1),
                           size_hint_y=None, height=dp(25),
                           font_name=FONT_PATH if FONT_PATH else "Roboto")
        content.add_widget(lbl_status)

        popup = Popup(title="", content=content, size_hint=(0.9, 0.75),
                      separator_color=(0.05, 0.58, 0.38, 1))
        btn_box = BoxLayout(size_hint_y=None, height=dp(45), spacing=dp(10))
        btn_push = Button(text=format_ar("حفظ البيانات"),
                          background_color=(0.05, 0.58, 0.38, 1),
                          color=(1, 1, 1, 1),
                          font_name=FONT_PATH if FONT_PATH else "Roboto")
        btn_cancel = Button(text=format_ar("إلغاء"),
                            background_color=(0.7, 0.2, 0.2, 1),
                            color=(1, 1, 1, 1),
                            font_name=FONT_PATH if FONT_PATH else "Roboto")

        def save_action(btn):
            user = ti_user.text.strip()
            repo = ti_repo.text.strip()
            token = ti_token.text.strip()
            if not user or not repo or not token:
                lbl_status.text = format_ar("الرجاء ملء جميع الحقول!")
                return
            self.store_gh_config(user, repo, token)
            lbl_status.text = format_ar("تم حفظ البيانات بنجاح!")
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
        layout = BoxLayout(orientation="vertical", padding=dp(15),
                           spacing=dp(12), size_hint_y=None)
        layout.bind(minimum_height=layout.setter("height"))
        logo_path = os.path.join(BASE_DIR, "logo.png")
        if os.path.exists(logo_path):
            layout.add_widget(Image(source=logo_path, size_hint_y=None,
                                    height=dp(90), allow_stretch=True))
        layout.add_widget(Label(text=format_ar("سجلات الأمان"),
                                font_size=sp(16), bold=True,
                                color=(0.7, 0.2, 0.2, 1), size_hint_y=None,
                                height=dp(30),
                                font_name=FONT_PATH if FONT_PATH else "Roboto"))
        for log in ["2026-06-06 12:00:22 - Admin Login [DZ]",
                    "2026-06-06 12:10:05 - index.html updated",
                    "2026-06-06 12:15:30 - Product added (Desktop)"]:
            layout.add_widget(Label(text=log, size_hint_y=None, height=dp(30),
                                    color=(0.3, 0.3, 0.3, 1),
                                    font_name=FONT_PATH if FONT_PATH else "Roboto"))
        btn_back = Button(text=format_ar("العودة للرئيسية"),
                          size_hint_y=None, height=dp(45),
                          background_color=(0.25, 0.25, 0.25, 1),
                          color=(1, 1, 1, 1),
                          font_name=FONT_PATH if FONT_PATH else "Roboto")
        btn_back.bind(on_press=lambda x: setattr(self.manager, "current", "home"))
        layout.add_widget(btn_back)
        scroll.add_widget(layout)
        self.add_widget(scroll)


# ===================== 5. Settings =====================
class SettingsScreen(Screen):
    def __init__(self, **kwargs):
        super(SettingsScreen, self).__init__(**kwargs)
        scroll = ScrollView()
        layout = BoxLayout(orientation="vertical", padding=dp(15),
                           spacing=dp(12), size_hint_y=None)
        layout.bind(minimum_height=layout.setter("height"))
        logo_path = os.path.join(BASE_DIR, "logo.png")
        if os.path.exists(logo_path):
            layout.add_widget(Image(source=logo_path, size_hint_y=None,
                                    height=dp(90), allow_stretch=True))
        layout.add_widget(Label(text=format_ar("إعدادات الحساب"),
                                font_size=sp(16), bold=True,
                                color=(0.15, 0.35, 0.55, 1),
                                size_hint_y=None, height=dp(30),
                                font_name=FONT_PATH if FONT_PATH else "Roboto"))
        layout.add_widget(Label(text=format_ar("إصدار التطبيق: v2.6.0"),
                                size_hint_y=None, height=dp(25),
                                color=(0.2, 0.2, 0.2, 1),
                                font_name=FONT_PATH if FONT_PATH else "Roboto"))
        btn_change_pass = Button(text=format_ar("تغيير كلمة المرور"),
                                 size_hint_y=None, height=dp(45),
                                 background_color=(0.8, 0.5, 0.1, 1),
                                 color=(1, 1, 1, 1), font_size=sp(14),
                                 bold=True,
                                 font_name=FONT_PATH if FONT_PATH else "Roboto")
        btn_change_pass.bind(on_press=self.open_change_password_popup)
        layout.add_widget(btn_change_pass)
        btn_gh = Button(text=format_ar("بيانات GitHub"),
                        size_hint_y=None, height=dp(45),
                        background_color=(0.1, 0.1, 0.1, 1),
                        color=(1, 1, 1, 1), font_size=sp(14), bold=True,
                        font_name=FONT_PATH if FONT_PATH else "Roboto")
        btn_gh.bind(on_press=lambda x: self.manager.get_screen("products").open_github_popup(None))
        layout.add_widget(btn_gh)
        btn_reset = Button(text=format_ar("إعادة تعيين index.html"),
                           size_hint_y=None, height=dp(45),
                           background_color=(0.5, 0.2, 0.5, 1),
                           color=(1, 1, 1, 1), font_size=sp(14), bold=True,
                           font_name=FONT_PATH if FONT_PATH else "Roboto")
        btn_reset.bind(on_press=lambda x: self.manager.get_screen("products").reset_to_bundled_html())
        layout.add_widget(btn_reset)
        self.msg_label = Label(text="", color=(0.05, 0.58, 0.38, 1),
                               size_hint_y=None, height=dp(25),
                               font_name=FONT_PATH if FONT_PATH else "Roboto")
        layout.add_widget(self.msg_label)
        btn_back = Button(text=format_ar("العودة للرئيسية"),
                          size_hint_y=None, height=dp(45),
                          background_color=(0.25, 0.25, 0.25, 1),
                          color=(1, 1, 1, 1),
                          font_name=FONT_PATH if FONT_PATH else "Roboto")
        btn_back.bind(on_press=lambda x: setattr(self.manager, "current", "home"))
        layout.add_widget(btn_back)
        scroll.add_widget(layout)
        self.add_widget(scroll)

    def open_change_password_popup(self, instance):
        content = BoxLayout(orientation="vertical", padding=dp(15), spacing=dp(10))
        with content.canvas.before:
            Color(0.96, 0.98, 0.96, 1)
            self.bg_rect3 = Rectangle(size=content.size, pos=content.pos)
        content.bind(size=lambda s, w: setattr(self.bg_rect3, "size", s.size),
                     pos=lambda s, w: setattr(self.bg_rect3, "pos", s.pos))
        content.add_widget(Label(text=format_ar("تغيير كلمة المرور"),
                                 font_size=sp(16), bold=True,
                                 color=(0.05, 0.58, 0.38, 1),
                                 size_hint_y=None, height=dp(35),
                                 font_name=FONT_PATH if FONT_PATH else "Roboto"))
        content.add_widget(Label(text=format_ar("كلمة المرور الحالية:"),
                                 color=(0.15, 0.15, 0.15, 1),
                                 size_hint_y=None, height=dp(25),
                                 font_name=FONT_PATH if FONT_PATH else "Roboto"))
        old_pass = TextInput(password=True, multiline=False, size_hint_y=None,
                             height=dp(40),
                             font_name=FONT_PATH if FONT_PATH else "Roboto")
        content.add_widget(old_pass)
        content.add_widget(Label(text=format_ar("كلمة المرور الجديدة:"),
                                 color=(0.15, 0.15, 0.15, 1),
                                 size_hint_y=None, height=dp(25),
                                 font_name=FONT_PATH if FONT_PATH else "Roboto"))
        new_pass = TextInput(password=True, multiline=False, size_hint_y=None,
                             height=dp(40),
                             font_name=FONT_PATH if FONT_PATH else "Roboto")
        content.add_widget(new_pass)
        popup = Popup(title="", content=content, size_hint=(0.85, 0.5),
                      separator_color=(0.05, 0.58, 0.38, 1))
        btn_box = BoxLayout(size_hint_y=None, height=dp(45), spacing=dp(10))
        btn_save = Button(text=format_ar("حفظ"),
                          background_color=(0.05, 0.58, 0.38, 1),
                          color=(1, 1, 1, 1),
                          font_name=FONT_PATH if FONT_PATH else "Roboto")
        btn_cancel = Button(text=format_ar("إلغاء"),
                            background_color=(0.7, 0.2, 0.2, 1),
                            color=(1, 1, 1, 1),
                            font_name=FONT_PATH if FONT_PATH else "Roboto")

        def save_new_password(btn):
            app_instance = App.get_running_app()
            if old_pass.text.strip() == app_instance.vault_password:
                if new_pass.text.strip():
                    app_instance.vault_password = new_pass.text.strip()
                    self.msg_label.text = format_ar("تم تغيير كلمة المرور!")
                    popup.dismiss()
                else:
                    self.msg_label.text = format_ar("كلمة المرور الجديدة فارغة!")
            else:
                self.msg_label.text = format_ar("كلمة المرور الحالية خاطئة!")

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
        content.bind(size=lambda s, w: setattr(self.bg_chk, "size", s.size),
                     pos=lambda s, w: setattr(self.bg_chk, "pos", s.pos))
        content.add_widget(Label(text=format_ar("تفعيل صلاحية الملفات"),
                                 font_size=sp(16), bold=True,
                                 color=(0.7, 0.2, 0.2, 1),
                                 size_hint_y=None, height=dp(35),
                                 font_name=FONT_PATH if FONT_PATH else "Roboto"))
        msg = Label(text=format_ar(
            "لفتح ملفات HTML من هاتفك،\n"
            "يحتاج التطبيق إلى صلاحية\n"
            "'الوصول لجميع الملفات'."),
            font_size=sp(12), halign="center",
            color=(0.15, 0.15, 0.15, 1),
            font_name=FONT_PATH if FONT_PATH else "Roboto")
        msg.bind(width=lambda s, w: setattr(s, "text_size", (w, None)))
        content.add_widget(msg)
        popup = Popup(title="", content=content, size_hint=(0.9, 0.45),
                      separator_color=(0.7, 0.2, 0.2, 1))
        btn_box = BoxLayout(size_hint_y=None, height=dp(50), spacing=dp(10))
        btn_open = Button(text=format_ar("فتح الإعدادات"),
                          background_color=(0.05, 0.58, 0.38, 1),
                          color=(1, 1, 1, 1), bold=True,
                          font_name=FONT_PATH if FONT_PATH else "Roboto")

        def open_settings(btn):
            popup.dismiss()
            open_all_files_settings()

        btn_open.bind(on_press=open_settings)
        btn_cancel = Button(text=format_ar("لاحقاً"),
                            background_color=(0.25, 0.25, 0.25, 1),
                            color=(1, 1, 1, 1),
                            font_name=FONT_PATH if FONT_PATH else "Roboto")
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