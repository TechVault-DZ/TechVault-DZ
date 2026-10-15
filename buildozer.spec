[app]
title = TechVault DZ
package.name = techvaultdz
package.domain = dz.techvault

source.dir = .
source.include_exts = py,png,jpg,jpeg,kv,atlas,ttf,html,json,xml
source.exclude_dirs = bin, .buildozer, venv, __pycache__, .git, .github
source.exclude_patterns = *.pyc, *.pyo, *.db, startup_error.txt

version = 2.1.0

icon.filename = %(source.dir)s/logo.png
presplash.filename = %(source.dir)s/logo.png
presplash.color = #FFFFFF

# المتطلبات — مبنية على ملفك الناجح ShowroomManager
# - hostpython3 : ضروري (كان ناقصاً عندك)
# - sqlite3 : ضروري وإلا يفشل import sqlite3 على الهاتف
# - python-bidi==0.4.2 : النسخ الأحدث Rust ولا تُبنى على Android
# - pillow : لمعاينة الصور في FileChooserIconView

requirements = python3,hostpython3,kivy==2.3.0,sqlite3,pillow,certifi,arabic-reshaper,python-bidi==0.4.2

orientation = portrait
fullscreen = 0

android.permissions = INTERNET, READ_EXTERNAL_STORAGE, WRITE_EXTERNAL_STORAGE, READ_MEDIA_IMAGES, ACCESS_NETWORK_STATE

android.api = 33
android.minapi = 24
android.ndk = 25b
android.ndk_api = 24
android.archs = arm64-v8a, armeabi-v7a
android.accept_sdk_license = True
android.allow_backup = True
android.wakelock = False

android.enable_androidx = True
android.gradle_dependencies = androidx.core:core:1.9.0
android.logcat_filters = *:S python:D

# نسخة p4a مستقرة مع kivy 2.3.0 / Python 3.11 / NDK 25b
p4a.branch = v2024.01.21

[buildozer]
log_level = 2
warn_on_root = 1