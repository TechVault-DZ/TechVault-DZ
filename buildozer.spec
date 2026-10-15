[app]
title = TechVault DZ
package.name = techvaultdz
package.domain = dz.techvault

source.dir = .
source.include_exts = py,png,jpg,jpeg,kv,atlas,html,ttf,json,txt,md
source.exclude_dirs = bin,.buildozer,__pycache__,.github
source.exclude_patterns = *.pyc,*.pyo,.git*

version = 2.1.0

# المتطلبات: Kivy + دعم العربية
requirements = python3,kivy==2.3.0,arabic-reshaper,python-bidi

orientation = portrait
fullscreen = 0

# الأيقونة وشاشة البداية على مستوى أندرويد
icon.filename = %(source.dir)s/logo.png
presplash.filename = %(source.dir)s/logo.png
presplash.color = #FFFFFF

# الأذونات: إنترنت (GitHub API + الترجمة) + التخزين
android.permissions = INTERNET,ACCESS_NETWORK_STATE,WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE

android.api = 34
android.minapi = 21
android.ndk = 25b
android.ndk_api = 21
android.archs = arm64-v8a, armeabi-v7a
android.allow_backup = True
android.wakelock = False
android.accept_sdk_license = True

# إعدادات تجميع
android.debug_artifact = apk
android.release_artifact = aab

[buildozer]
log_level = 2
warn_on_root = 1