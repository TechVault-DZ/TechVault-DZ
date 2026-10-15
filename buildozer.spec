[app]
title = TechVault DZ
package.name = techvaultdz
package.domain = org.techvault
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,ttf
source.exclude_dirs = bin, .buildozer, venv, __pycache__, .git
source.exclude_patterns = private_key.pem, *.keystore

version = 1.0.0

icon.filename = %(source.dir)s/logo.png
presplash.filename = %(source.dir)s/presplash.png
presplash.color = #0F172A

requirements = python3,hostpython3,kivy==2.3.0,pillow,arabic-reshaper,python-bidi==0.4.2,certifi,urllib3

orientation = portrait
fullscreen = 0

android.api = 33
android.minapi = 24
android.ndk = 25b
android.ndk_api = 24
android.archs = arm64-v8a
android.accept_sdk_license = True

android.permissions = INTERNET, READ_EXTERNAL_STORAGE, WRITE_EXTERNAL_STORAGE

android.allow_backup = False
android.logcat_filters = *:S python:D

p4a.branch = v2024.01.21

[buildozer]
log_level = 2
warn_on_root = 1
