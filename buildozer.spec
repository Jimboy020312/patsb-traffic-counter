[app]

title = PATSB Traffic Counter
package.name = patsbtrafficcounter
package.domain = com.patsb

source.dir = .
source.include_exts = py,png,jpg,kv,atlas

version = 1.0

requirements = python3,kivy

orientation = landscape

# Android 12 fix: target API 31, use latest p4a for exported activity support
android.api = 31
android.minapi = 21
android.ndk = 25b
android.archs = arm64-v8a, armeabi-v7a

# Android 12 requires explicit exported flag on activities
android.manifest.extra = <uses-feature android:name="android.hardware.touchscreen" android:required="false" />

# Use latest python-for-android which has Android 12 fixes
p4a.branch = master

# Permissions
android.permissions = WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE

fullscreen = 1

# Icon
icon.filename = %(source.dir)s/icon.png

[buildozer]
log_level = 2
warn_on_root = 1
