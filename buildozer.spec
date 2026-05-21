[app]

title = PATSB Traffic Counter
package.name = patsbtrafficcounter
package.domain = com.patsb

source.dir = .
source.include_exts = py,png,jpg,kv,atlas

version = 1.0

requirements = python3,kivy,android

orientation = landscape

android.permissions = WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE
android.api = 33
android.minapi = 21
android.ndk = 25b
android.archs = arm64-v8a, armeabi-v7a

fullscreen = 1

icon.filename = %(source.dir)s/icon.png

[buildozer]
log_level = 2
warn_on_root = 1
