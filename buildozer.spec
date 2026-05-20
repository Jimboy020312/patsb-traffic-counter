[app]

# App identity
title = PATSB Traffic Counter
package.name = patsbtrafficcounter
package.domain = com.patsb

# Source
source.dir = .
source.include_exts = py,png,jpg,kv,atlas

# Version
version = 1.0

# Requirements — only what we need
requirements = python3,kivy

# Icon — replace icon.png with your 512x512 company logo PNG
icon.filename = %(source.dir)s/icon.png

# Orientation — landscape only
orientation = landscape

# Android specifics
android.permissions = WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE
android.api = 33
android.minapi = 21
android.ndk = 25b
android.sdk = 33
android.archs = arm64-v8a, armeabi-v7a

# Fullscreen (hides status bar for cleaner look on a working tool)
fullscreen = 1

[buildozer]
log_level = 2
warn_on_root = 1
