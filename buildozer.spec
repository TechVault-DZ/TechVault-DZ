[app]
title = TechVault DZ
package.name = techvaultdz
package.domain = dz.techvault

source.dir = .
source.include_exts = py,png,jpg,jpeg,kv,atlas,html,ttf,json,txt,md
source.exclude_dirs = bin,.buildozer,__pycache__,.github
source.exclude_patterns = *.pyc,*.pyo,.git*

version = 2.1.0

# المتطلبات: Kivy + دعم العربية + sqlite3
# - sqlite3 : ضروري وإلا يفشل import sqlite3 على الهاتف
# - python-bidi==0.4.2 : النسخ الأحدث مكتوبة بـ Rust ولا تُبنى على Android
requirements = python3,hostpython3,kivy==2.3.0,sqlite3,arabic-reshaper,python-bidi==0.4.2

orientation = portrait
fullscreen = 0

# الأيقونة وشاشة البداية على مستوى أندرويد
icon.filename = %(source.dir)s/logo.png
presplash.filename = %(source.dir)s/logo.png
presplash.color = #FFFFFF

# الأذونات: إنترنت (GitHub API + الترجمة) + التخزين
android.permissions = INTERNET,ACCESS_NETWORK_STATE,WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE

android.api = 33
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

android.enable_androidx = True
android.logcat_filters = *:S python:D

# نسخة p4a مستقرة مع kivy 2.3.0 / Python 3.11 / NDK 25b
p4a.branch = v2024.01.21

[buildozer]
log_level = 2
warn_on_root = 1