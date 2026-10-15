import base64
import json
import os
import re
import threading
import urllib.parse
import urllib.request
import webbrowser
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

# تعيين خلفية فاتحة موحدة للتطبيق
Window.clearcolor = (0.95, 0.97, 0.95, 1)

# استيراد أدوات إصلاح الحروف العربية
try:
  import arabic_reshaper
  from bidi.algorithm import get_display

  HAS_BIDI = True
except ImportError:
  HAS_BIDI = False

FONT_PATH = "arabic.ttf" if os.path.exists("arabic.ttf") else None


def format_ar(text):
  if text is None:
    return ""
  text_str = str(text)
  if HAS_BIDI:
    try:
      if any("\u0600" <= c <= "\u06ff" for c in text_str):
        reshaped = arabic_reshaper.reshape(text_str)
        return get_display(reshaped)
    except:
      return text_str
  return text_str


def translate_text(text, target_lang):
  if not text or not text.strip():
    return ""
  try:
    url = f"https://api.mymemory.translated.net/get?q={urllib.parse.quote(text)}&langpair=ar|{target_lang}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=3) as response:
      data = json.loads(response.read().decode("utf-8"))
      if data.get("responseStatus") == 200:
        return data["responseData"]["translatedText"]
  except Exception:
    pass
  return ""


# 1. شاشة تسجيل الدخول بكلمة السر
class LoginScreen(Screen):

  def __init__(self, **kwargs):
    super(LoginScreen, self).__init__(**kwargs)
    layout = BoxLayout(
        orientation="vertical",
        padding=dp(20),
        spacing=dp(12),
        size_hint=(0.9, None),
        height=dp(380),
        pos_hint={"center_x": 0.5, "center_y": 0.5},
    )

    base_dir = os.path.dirname(os.path.abspath(__file__))
    logo_path = os.path.join(base_dir, "logo.png")

    if os.path.exists(logo_path):
      layout.add_widget(
          Image(
              source=logo_path,
              size_hint_y=None,
              height=dp(110),
              allow_stretch=True,
          )
      )

    layout.add_widget(
        Label(
            text=format_ar("TechVault DZ - قفل الخزنة"),
            font_size=sp(18),
            bold=True,
            color=(0.05, 0.58, 0.38, 1),
            size_hint_y=None,
            height=dp(30),
            font_name=FONT_PATH if FONT_PATH else "Roboto",
        )
    )

    layout.add_widget(
        Label(
            text=format_ar("أدخل كلمة المرور:"),
            font_size=sp(13),
            color=(0.3, 0.3, 0.3, 1),
            size_hint_y=None,
            height=dp(25),
            font_name=FONT_PATH if FONT_PATH else "Roboto",
        )
    )

    self.pass_input = TextInput(
        password=True,
        multiline=False,
        font_size=sp(16),
        size_hint_y=None,
        height=dp(42),
        font_name=FONT_PATH if FONT_PATH else "Roboto",
    )
    layout.add_widget(self.pass_input)

    btn_login = Button(
        text=format_ar("فتح الخزنة"),
        size_hint_y=None,
        height=dp(48),
        background_color=(0.05, 0.58, 0.38, 1),
        color=(1, 1, 1, 1),
        font_size=sp(15),
        bold=True,
        font_name=FONT_PATH if FONT_PATH else "Roboto",
    )
    btn_login.bind(on_press=self.check_password)
    layout.add_widget(btn_login)

    self.error_label = Label(
        text="",
        color=(0.7, 0.2, 0.2, 1),
        size_hint_y=None,
        height=dp(25),
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


# 2. الشاشة الرئيسية
class HomeScreen(Screen):

  def __init__(self, **kwargs):
    super(HomeScreen, self).__init__(**kwargs)
    layout = BoxLayout(
        orientation="vertical",
        padding=dp(20),
        spacing=dp(15),
        size_hint=(0.9, None),
        height=dp(420),
        pos_hint={"center_x": 0.5, "center_y": 0.5},
    )

    base_dir = os.path.dirname(os.path.abspath(__file__))
    logo_path = os.path.join(base_dir, "logo.png")

    if os.path.exists(logo_path):
      layout.add_widget(
          Image(
              source=logo_path,
              size_hint_y=None,
              height=dp(120),
              allow_stretch=True,
              keep_ratio=True,
          )
      )

    btn_vault = Button(
        text=format_ar("Open Vault (إدارة المنتجات)"),
        size_hint_y=None,
        height=dp(50),
        background_color=(0.05, 0.58, 0.38, 1),
        color=(1, 1, 1, 1),
        font_size=sp(14),
        bold=True,
        font_name=FONT_PATH if FONT_PATH else "Roboto",
    )
    btn_vault.bind(on_press=lambda x: setattr(self.manager, "current", "products"))

    btn_logs = Button(
        text=format_ar("View Secure Logs (سجلات الأمان)"),
        size_hint_y=None,
        height=dp(50),
        background_color=(0.7, 0.2, 0.2, 1),
        color=(1, 1, 1, 1),
        font_size=sp(14),
        bold=True,
        font_name=FONT_PATH if FONT_PATH else "Roboto",
    )
    btn_logs.bind(on_press=lambda x: setattr(self.manager, "current", "logs"))

    btn_settings = Button(
        text=format_ar("Account Settings (الإعدادات)"),
        size_hint_y=None,
        height=dp(50),
        background_color=(0.15, 0.35, 0.55, 1),
        color=(1, 1, 1, 1),
        font_size=sp(14),
        bold=True,
        font_name=FONT_PATH if FONT_PATH else "Roboto",
    )
    btn_settings.bind(
        on_press=lambda x: setattr(self.manager, "current", "settings")
    )

    btn_lock = Button(
        text=format_ar("قفل التطبيق"),
        size_hint_y=None,
        height=dp(50),
        background_color=(0.25, 0.25, 0.25, 1),
        color=(1, 1, 1, 1),
        font_size=sp(14),
        bold=True,
        font_name=FONT_PATH if FONT_PATH else "Roboto",
    )
    btn_lock.bind(on_press=lambda x: setattr(self.manager, "current", "login"))

    layout.add_widget(btn_vault)
    layout.add_widget(btn_logs)
    layout.add_widget(btn_settings)
    layout.add_widget(btn_lock)

    self.add_widget(layout)


# 3. شاشة إدارة المنتجات
class ProductsScreen(Screen):

  def __init__(self, **kwargs):
    super(ProductsScreen, self).__init__(**kwargs)
    self.products = []
    base_dir = os.path.dirname(os.path.abspath(__file__))
    self.html_path = os.path.join(base_dir, "index.html")

    root = BoxLayout(orientation="vertical", padding=dp(10), spacing=dp(10))

    top_bar = BoxLayout(size_hint_y=None, height=dp(50), spacing=dp(4))

    btn_back = Button(
        text=format_ar("الرئيسية"),
        size_hint_x=0.2,
        background_color=(0.25, 0.25, 0.25, 1),
        color=(1, 1, 1, 1),
        font_name=FONT_PATH if FONT_PATH else "Roboto",
    )
    btn_back.bind(
        on_press=lambda x: setattr(self.manager, "current", "home")
    )

    btn_load = Button(
        text=format_ar("تحميل"),
        size_hint_x=0.2,
        background_color=(0.15, 0.35, 0.55, 1),
        color=(1, 1, 1, 1),
        font_name=FONT_PATH if FONT_PATH else "Roboto",
    )
    btn_load.bind(on_press=self.load_html)

    btn_add = Button(
        text=format_ar("إضافة"),
        size_hint_x=0.2,
        background_color=(0.05, 0.58, 0.38, 1),
        color=(1, 1, 1, 1),
        font_name=FONT_PATH if FONT_PATH else "Roboto",
    )
    btn_add.bind(on_press=lambda x: self.open_product_form())

    # زر واحد: حفظ index.html ثم رفعه إلى GitHub
    btn_save = Button(
        text=format_ar("حفظ ورفع"),
        size_hint_x=0.4,
        background_color=(0.7, 0.2, 0.2, 1),
        color=(1, 1, 1, 1),
        font_name=FONT_PATH if FONT_PATH else "Roboto",
    )
    btn_save.bind(on_press=self.save_and_push)

    top_bar.add_widget(btn_back)
    top_bar.add_widget(btn_load)
    top_bar.add_widget(btn_add)
    top_bar.add_widget(btn_save)
    root.add_widget(top_bar)

    self.status_label = Label(
        text=format_ar("إدارة منتجات TechVault DZ"),
        size_hint_y=None,
        height=dp(30),
        color=(0.2, 0.2, 0.2, 1),
        font_name=FONT_PATH if FONT_PATH else "Roboto",
    )
    root.add_widget(self.status_label)

    self.scroll = ScrollView()
    self.products_layout = GridLayout(cols=1, spacing=dp(8), size_hint_y=None)
    self.products_layout.bind(
        minimum_height=self.products_layout.setter("height")
    )
    self.scroll.add_widget(self.products_layout)
    root.add_widget(self.scroll)

    self.add_widget(root)

    if os.path.exists(self.html_path):
      self.load_html(None)

  def load_html(self, instance):
    if not os.path.exists(self.html_path):
      self.status_label.text = format_ar("خطأ: index.html غير موجود!")
      return
    try:
      with open(self.html_path, "r", encoding="utf-8") as f:
        content = f.read()
      match = re.search(r"const products = (\[.*?\]);", content, re.DOTALL)
      if match:
        self.products = json.loads(self.js_to_json(match.group(1)))
        self.status_label.text = format_ar(
            f"تم تحميل {len(self.products)} منتج بنجاح."
        )
        self.refresh_products_list()
      else:
        self.status_label.text = format_ar("خطأ في قراءة بيانات المنتجات.")
    except Exception as e:
      self.status_label.text = format_ar(f"خطأ: {str(e)[:30]}")

  def js_to_json(self, js_str):
    s = js_str
    s = re.sub(r"([{,]\s*)([a-zA-Z_][a-zA-Z0-9_]*)\s*:", r'\1"\2":', s)
    return s.replace("'", '"')

  def json_to_js(self, py_list):
    return json.dumps(py_list, ensure_ascii=False, indent=4)

  def refresh_products_list(self):
    self.products_layout.clear_widgets()
    for i, p in enumerate(self.products):
      item_layout = BoxLayout(
          orientation="horizontal",
          size_hint_y=None,
          height=dp(70),
          spacing=dp(5),
      )
      name_ar = p.get("name", {}).get("ar", "بدون اسم")
      cat = p.get("category", "desktop")
      lbl = Label(
          text=format_ar(f"{i+1}. {name_ar} [{cat.upper()}]"),
          size_hint_x=0.6,
          color=(0.1, 0.1, 0.1, 1),
          font_name=FONT_PATH if FONT_PATH else "Roboto",
      )

      btn_edit = Button(
          text=format_ar("تعديل"),
          size_hint_x=0.2,
          background_color=(0.15, 0.35, 0.55, 1),
          color=(1, 1, 1, 1),
          font_name=FONT_PATH if FONT_PATH else "Roboto",
      )
      btn_edit.bind(on_press=lambda x, idx=i: self.open_product_form(idx=idx))

      btn_del = Button(
          text=format_ar("حذف"),
          size_hint_x=0.2,
          background_color=(0.7, 0.2, 0.2, 1),
          color=(1, 1, 1, 1),
          font_name=FONT_PATH if FONT_PATH else "Roboto",
      )
      btn_del.bind(on_press=lambda x, idx=i: self.delete_product(idx))

      item_layout.add_widget(lbl)
      item_layout.add_widget(btn_edit)
      item_layout.add_widget(btn_del)
      self.products_layout.add_widget(item_layout)

  def delete_product(self, idx):
    if 0 <= idx < len(self.products):
      del self.products[idx]
      self.refresh_products_list()
      self.status_label.text = format_ar("تم الحذف. اضغط 'حفظ' في الأعلى.")

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
            "name": {"ar": "", "fr": "", "en": ""},
            "desc": {"ar": "", "fr": "", "en": ""},
            "version": "v1.0.0",
            "size": "20 MB",
            "rating": 4.8,
        }
    )

    content = BoxLayout(
        orientation="vertical", padding=dp(15), spacing=dp(10)
    )
    with content.canvas.before:
      Color(0.96, 0.98, 0.96, 1)
      self.bg_rect1 = Rectangle(size=content.size, pos=content.pos)
    content.bind(
        size=lambda s, w: setattr(self.bg_rect1, "size", s.size),
        pos=lambda s, w: setattr(self.bg_rect1, "pos", s.pos),
    )

    header_lbl = Label(
        text=format_ar("إدارة المنتجات"),
        font_size=sp(16),
        bold=True,
        color=(0.05, 0.58, 0.38, 1),
        size_hint_y=None,
        height=dp(35),
        font_name=FONT_PATH if FONT_PATH else "Roboto",
    )
    content.add_widget(header_lbl)

    btn_translate = Button(
        text=format_ar("🌐 ترجمة آلية سريعة"),
        size_hint_y=None,
        height=dp(42),
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
        ("name_ar", "الاسم (عربي)", p.get("name", {}).get("ar", "")),
        ("name_fr", "الاسم (فرنسي)", p.get("name", {}).get("fr", "")),
        ("name_en", "الاسم (إنجليزي)", p.get("name", {}).get("en", "")),
        ("desc_ar", "الوصف (عربي)", p.get("desc", {}).get("ar", "")),
        ("desc_fr", "الوصف (فرنسي)", p.get("desc", {}).get("fr", "")),
        ("desc_en", "الوصف (إنجليزي)", p.get("desc", {}).get("en", "")),
        ("version", "رقم الإصدار", p.get("version", "")),
        ("size", "الحجم", p.get("size", "")),
        ("rating", "التقييم", str(p.get("rating", 4.8))),
    ]

    for key, label_text, val in fields:
      lbl = Label(
          text=format_ar(label_text),
          color=(0.15, 0.15, 0.15, 1),
          size_hint_y=None,
          height=dp(25),
          halign="right",
          font_name=FONT_PATH if FONT_PATH else "Roboto",
      )
      lbl.bind(
          size=lambda s, w: setattr(s, "text_size", (s.width, s.height))
      )
      form_layout.add_widget(lbl)

      if key == "category":
        spinner = Spinner(
            text=val if val in ("desktop", "android") else "desktop",
            values=("desktop", "android"),
            size_hint_y=None,
            height=dp(40),
            background_color=(0.15, 0.35, 0.55, 1),
            color=(1, 1, 1, 1),
        )
        self.inputs[key] = spinner
        form_layout.add_widget(spinner)
        continue

      ti = TextInput(
          text=str(val),
          multiline=False,
          size_hint_y=None,
          height=dp(40),
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
      self.status_label.text = format_ar("جاري الترجمة الآلية في الخلفية...")

      def background_task():
        tr_name_fr = translate_text(ar_n, "fr") if ar_n else ""
        tr_name_en = translate_text(ar_n, "en") if ar_n else ""
        tr_desc_fr = translate_text(ar_d, "fr") if ar_d else ""
        tr_desc_en = translate_text(ar_d, "en") if ar_d else ""

        if tr_name_fr:
          self.inputs["name_fr"].text = tr_name_fr
        if tr_name_en:
          self.inputs["name_en"].text = tr_name_en
        if tr_desc_fr:
          self.inputs["desc_fr"].text = tr_desc_fr
        if tr_desc_en:
          self.inputs["desc_en"].text = tr_desc_en
        self.status_label.text = format_ar("تمت الترجمة الآلية بنجاح!")

      threading.Thread(target=background_task).start()

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
        title="",
        content=content,
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
            "image": self.inputs["image"].text.strip(),
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
        self.status_label.text = format_ar(f"خطأ: {str(e)[:25]}")

    btn_save_p.bind(on_press=save_action)
    btn_cancel.bind(on_press=popup.dismiss)
    btn_box.add_widget(btn_save_p)
    btn_box.add_widget(btn_cancel)
    content.add_widget(btn_box)
    popup.open()

  def save_html(self, instance):
    if not os.path.exists(self.html_path):
      return
    try:
      with open(self.html_path, "r", encoding="utf-8") as f:
        content = f.read()
      new_block = f"const products = {self.json_to_js(self.products)};"
      new_content = re.sub(
          r"const products = \[.*?\];", new_block, content, flags=re.DOTALL
      )
      with open(self.html_path, "w", encoding="utf-8") as f:
        f.write(new_content)
      self.status_label.text = format_ar("تم حفظ index.html بنجاح!")
    except Exception as e:
      self.status_label.text = format_ar(f"خطأ حفظ: {str(e)[:30]}")

  # ---------- حفظ إعدادات GitHub ----------
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
    """حفظ index.html ثم رفعه؛ إن لم تكن البيانات محفوظة تُطلب أول مرة."""
    cfg = self.load_gh_config()
    if not (cfg.get("user") and cfg.get("repo") and cfg.get("token")):
      self.open_github_popup(None, then_push=True)
      return
    self.save_html(None)
    self.status_label.text = format_ar("جاري الرفع إلى GitHub...")
    self.push_to_github(
        cfg["user"],
        cfg["repo"],
        cfg["token"],
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
        logo_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "logo.png"
        )
        if os.path.exists(logo_path):
          files.append(("logo.png", logo_path))

        for name, path in files:
          api_url = f"https://api.github.com/repos/{user}/{repo}/contents/{name}"
          sha = ""
          try:
            req_get = urllib.request.Request(api_url, headers=headers)
            with urllib.request.urlopen(req_get) as resp:
              sha = json.loads(resp.read().decode("utf-8")).get("sha", "")
          except Exception:
            pass
          with open(path, "rb") as f:
            encoded = base64.b64encode(f.read()).decode("utf-8")
          payload = {
              "message": f"Update {name} via TechVault DZ Dashboard",
              "content": encoded,
          }
          if sha:
            payload["sha"] = sha
          req_put = urllib.request.Request(
              api_url,
              data=json.dumps(payload).encode("utf-8"),
              headers=headers,
              method="PUT",
          )
          with urllib.request.urlopen(req_put):
            pass
        set_status("تم الحفظ ورفع الملفات إلى GitHub بنجاح!")
      except Exception as e:
        set_status(f"خطأ في الاتصال: {str(e)[:25]}")

    threading.Thread(target=background_push, daemon=True).start()

  def open_github_popup(self, instance, then_push=False):
    saved_cfg = self.load_gh_config()
    content = BoxLayout(
        orientation="vertical", padding=dp(15), spacing=dp(10)
    )
    with content.canvas.before:
      Color(0.96, 0.98, 0.96, 1)
      self.bg_rect2 = Rectangle(size=content.size, pos=content.pos)
    content.bind(
        size=lambda s, w: setattr(self.bg_rect2, "size", s.size),
        pos=lambda s, w: setattr(self.bg_rect2, "pos", s.pos),
    )

    header_lbl = Label(
        text=format_ar("مزامنة GitHub"),
        font_size=sp(16),
        bold=True,
        color=(0.05, 0.58, 0.38, 1),
        size_hint_y=None,
        height=dp(35),
        font_name=FONT_PATH if FONT_PATH else "Roboto",
    )
    content.add_widget(header_lbl)

    content.add_widget(
        Label(
            text=format_ar("اسم المالك أو المنظمة (Owner):"),
            color=(0.15, 0.15, 0.15, 1),
            size_hint_y=None,
            height=dp(25),
            font_name=FONT_PATH if FONT_PATH else "Roboto",
        )
    )
    ti_user = TextInput(
        text=saved_cfg.get("user", ""),
        multiline=False,
        size_hint_y=None,
        height=dp(40),
        font_name=FONT_PATH if FONT_PATH else "Roboto",
    )
    content.add_widget(ti_user)

    content.add_widget(
        Label(
            text=format_ar("اسم المستودع (Repository Name):"),
            color=(0.15, 0.15, 0.15, 1),
            size_hint_y=None,
            height=dp(25),
            font_name=FONT_PATH if FONT_PATH else "Roboto",
        )
    )
    ti_repo = TextInput(
        text=saved_cfg.get("repo", ""),
        multiline=False,
        size_hint_y=None,
        height=dp(40),
        font_name=FONT_PATH if FONT_PATH else "Roboto",
    )
    content.add_widget(ti_repo)

    content.add_widget(
        Label(
            text=format_ar("رمز الوصول (Personal Access Token):"),
            color=(0.15, 0.15, 0.15, 1),
            size_hint_y=None,
            height=dp(25),
            font_name=FONT_PATH if FONT_PATH else "Roboto",
        )
    )
    ti_token = TextInput(
        text=saved_cfg.get("token", ""),
        password=True,
        multiline=False,
        size_hint_y=None,
        height=dp(40),
        font_name=FONT_PATH if FONT_PATH else "Roboto",
    )
    content.add_widget(ti_token)

    lbl_git_status = Label(
        text="",
        color=(0.05, 0.58, 0.38, 1),
        size_hint_y=None,
        height=dp(25),
        font_name=FONT_PATH if FONT_PATH else "Roboto",
    )
    content.add_widget(lbl_git_status)

    popup = Popup(
        title="",
        content=content,
        size_hint=(0.9, 0.75),
        separator_color=(0.05, 0.58, 0.38, 1),
    )

    btn_box = BoxLayout(size_hint_y=None, height=dp(45), spacing=dp(10))
    btn_push = Button(
        text=format_ar("رفع وتحديث الموقع واللوغو"),
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

    def push_action(btn):
      user = ti_user.text.strip()
      repo = ti_repo.text.strip()
      token = ti_token.text.strip()

      if not user or not repo or not token:
        lbl_git_status.text = format_ar("الرجاء ملء جميع الحقول المطلوبة!")
        return

      # حفظ البيانات للمرات القادمة (ويمكن تغييرها من هنا في أي وقت)
      self.store_gh_config(user, repo, token)
      self.save_html(None)
      lbl_git_status.text = format_ar("جاري الرفع إلى GitHub...")

      def on_done(msg):
        lbl_git_status.text = format_ar(msg)
        self.status_label.text = format_ar(msg)

      self.push_to_github(user, repo, token, on_done)

    btn_push.bind(on_press=push_action)
    btn_cancel.bind(on_press=popup.dismiss)
    btn_box.add_widget(btn_push)
    btn_box.add_widget(btn_cancel)
    content.add_widget(btn_box)

    popup.open()


# 4. شاشة سجلات الأمان
class LogsScreen(Screen):

  def __init__(self, **kwargs):
    super(LogsScreen, self).__init__(**kwargs)
    scroll = ScrollView()
    layout = BoxLayout(
        orientation="vertical",
        padding=dp(15),
        spacing=dp(12),
        size_hint_y=None,
    )
    layout.bind(minimum_height=layout.setter("height"))

    base_dir = os.path.dirname(os.path.abspath(__file__))
    logo_path = os.path.join(base_dir, "logo.png")
    if os.path.exists(logo_path):
      layout.add_widget(
          Image(
              source=logo_path,
              size_hint_y=None,
              height=dp(90),
              allow_stretch=True,
          )
      )

    layout.add_widget(
        Label(
            text=format_ar("سجلات الأمان والاتصال (Secure Logs)"),
            font_size=sp(16),
            bold=True,
            color=(0.7, 0.2, 0.2, 1),
            size_hint_y=None,
            height=dp(30),
            font_name=FONT_PATH if FONT_PATH else "Roboto",
        )
    )

    sample_logs = [
        "2026-06-06 12:00:22 - Admin Login Successful [DZ]",
        "2026-06-06 12:10:05 - index.html updated successfully",
        "2026-06-06 12:15:30 - Product added to vault (Desktop)",
    ]

    for log in sample_logs:
      layout.add_widget(
          Label(
              text=log,
              size_hint_y=None,
              height=dp(30),
              color=(0.3, 0.3, 0.3, 1),
              font_name=FONT_PATH if FONT_PATH else "Roboto",
          )
      )

    btn_back = Button(
        text=format_ar("العودة للرئيسية"),
        size_hint_y=None,
        height=dp(45),
        background_color=(0.25, 0.25, 0.25, 1),
        color=(1, 1, 1, 1),
        font_name=FONT_PATH if FONT_PATH else "Roboto",
    )
    btn_back.bind(
        on_press=lambda x: setattr(self.manager, "current", "home")
    )
    layout.add_widget(btn_back)

    scroll.add_widget(layout)
    self.add_widget(scroll)


# 5. شاشة الإعدادات
class SettingsScreen(Screen):

  def __init__(self, **kwargs):
    super(SettingsScreen, self).__init__(**kwargs)
    scroll = ScrollView()
    layout = BoxLayout(
        orientation="vertical",
        padding=dp(15),
        spacing=dp(12),
        size_hint_y=None,
    )
    layout.bind(minimum_height=layout.setter("height"))

    base_dir = os.path.dirname(os.path.abspath(__file__))
    logo_path = os.path.join(base_dir, "logo.png")
    if os.path.exists(logo_path):
      layout.add_widget(
          Image(
              source=logo_path,
              size_hint_y=None,
              height=dp(90),
              allow_stretch=True,
          )
      )

    layout.add_widget(
        Label(
            text=format_ar("إعدادات الحساب والنظام (Account Settings)"),
            font_size=sp(16),
            bold=True,
            color=(0.15, 0.35, 0.55, 1),
            size_hint_y=None,
            height=dp(30),
            font_name=FONT_PATH if FONT_PATH else "Roboto",
        )
    )

    layout.add_widget(
        Label(
            text=format_ar("إصدار التطبيق: v2.1.0 (TechVault DZ)"),
            size_hint_y=None,
            height=dp(25),
            color=(0.2, 0.2, 0.2, 1),
            font_name=FONT_PATH if FONT_PATH else "Roboto",
        )
    )
    layout.add_widget(
        Label(
            text=format_ar("حالة الاتصال: متصل بالخزنة المحلية 🇩🇿"),
            size_hint_y=None,
            height=dp(25),
            color=(0.2, 0.2, 0.2, 1),
            font_name=FONT_PATH if FONT_PATH else "Roboto",
        )
    )

    btn_change_pass = Button(
        text=format_ar("تغيير كلمة المرور (Change Password)"),
        size_hint_y=None,
        height=dp(45),
        background_color=(0.8, 0.5, 0.1, 1),
        color=(1, 1, 1, 1),
        font_size=sp(14),
        bold=True,
        font_name=FONT_PATH if FONT_PATH else "Roboto",
    )
    btn_change_pass.bind(on_press=self.open_change_password_popup)
    layout.add_widget(btn_change_pass)

    btn_gh_settings = Button(
        text=format_ar("بيانات GitHub (تغيير)"),
        size_hint_y=None,
        height=dp(45),
        background_color=(0.1, 0.1, 0.1, 1),
        color=(1, 1, 1, 1),
        font_size=sp(14),
        bold=True,
        font_name=FONT_PATH if FONT_PATH else "Roboto",
    )
    btn_gh_settings.bind(
        on_press=lambda x: self.manager.get_screen("products").open_github_popup(None)
    )
    layout.add_widget(btn_gh_settings)

    self.msg_label = Label(
        text="",
        color=(0.05, 0.58, 0.38, 1),
        size_hint_y=None,
        height=dp(25),
        font_name=FONT_PATH if FONT_PATH else "Roboto",
    )
    layout.add_widget(self.msg_label)

    btn_back = Button(
        text=format_ar("العودة للرئيسية"),
        size_hint_y=None,
        height=dp(45),
        background_color=(0.25, 0.25, 0.25, 1),
        color=(1, 1, 1, 1),
        font_name=FONT_PATH if FONT_PATH else "Roboto",
    )
    btn_back.bind(
        on_press=lambda x: setattr(self.manager, "current", "home")
    )
    layout.add_widget(btn_back)

    scroll.add_widget(layout)
    self.add_widget(scroll)

  def open_change_password_popup(self, instance):
    content = BoxLayout(
        orientation="vertical", padding=dp(15), spacing=dp(10)
    )
    with content.canvas.before:
      Color(0.96, 0.98, 0.96, 1)
      self.bg_rect3 = Rectangle(size=content.size, pos=content.pos)
    content.bind(
        size=lambda s, w: setattr(self.bg_rect3, "size", s.size),
        pos=lambda s, w: setattr(self.bg_rect3, "pos", s.pos),
    )

    header_lbl = Label(
        text=format_ar("تغيير كلمة المرور"),
        font_size=sp(16),
        bold=True,
        color=(0.05, 0.58, 0.38, 1),
        size_hint_y=None,
        height=dp(35),
        font_name=FONT_PATH if FONT_PATH else "Roboto",
    )
    content.add_widget(header_lbl)

    content.add_widget(
        Label(
            text=format_ar("كلمة المرور الحالية:"),
            color=(0.15, 0.15, 0.15, 1),
            size_hint_y=None,
            height=dp(25),
            font_name=FONT_PATH if FONT_PATH else "Roboto",
        )
    )
    old_pass = TextInput(
        password=True,
        multiline=False,
        size_hint_y=None,
        height=dp(40),
        font_name=FONT_PATH if FONT_PATH else "Roboto",
    )
    content.add_widget(old_pass)

    content.add_widget(
        Label(
            text=format_ar("كلمة المرور الجديدة:"),
            color=(0.15, 0.15, 0.15, 1),
            size_hint_y=None,
            height=dp(25),
            font_name=FONT_PATH if FONT_PATH else "Roboto",
        )
    )
    new_pass = TextInput(
        password=True,
        multiline=False,
        size_hint_y=None,
        height=dp(40),
        font_name=FONT_PATH if FONT_PATH else "Roboto",
    )
    content.add_widget(new_pass)

    popup = Popup(
        title="",
        content=content,
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
          self.msg_label.text = format_ar(
              "كلمة المرور الجديدة لا يمكن أن تكون فارغة!"
          )
      else:
        self.msg_label.text = format_ar("كلمة المرور الحالية غير صحيحة!")

    btn_save.bind(on_press=save_new_password)
    btn_cancel.bind(on_press=popup.dismiss)
    btn_box.add_widget(btn_save)
    btn_box.add_widget(btn_cancel)
    content.add_widget(btn_box)

    popup.open()


# التطبيق الرئيسي وتجميع الشاشات ودعم زر العودة للهاتف
class TechVaultApp(App):
  vault_password = "1234"

  def build(self):
    self.title = "TechVault DZ Dashboard"
    sm = ScreenManager()
    sm.add_widget(LoginScreen(name="login"))
    sm.add_widget(HomeScreen(name="home"))
    sm.add_widget(ProductsScreen(name="products"))
    sm.add_widget(LogsScreen(name="logs"))
    sm.add_widget(SettingsScreen(name="settings"))

    Window.bind(on_keyboard=self._on_keyboard)
    return sm

  def _on_keyboard(self, window, key, *args):
    if key == 27:
      sm = self.root
      if sm and sm.current not in ["home", "login"]:
        sm.current = "home"
        return True
    return False


if __name__ == "__main__":
  TechVaultApp().run()
