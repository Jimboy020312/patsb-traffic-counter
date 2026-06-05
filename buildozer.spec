[app]

title = PATSB Traffic Counter
package.name = patsbtrafficcounter
package.domain = com.patsb

source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json

version = 1.0
# Increment this by 1 every build — Android uses this (not version) to decide
# whether to update in-place or reject the install. Never reuse a number.
android.numeric_version = 1

requirements = python3,kivy,android

orientation = landscape

android.permissions = WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE,VIBRATE,WAKE_LOCK

android.api = 33
android.minapi = 21
android.ndk = 25b
android.archs = arm64-v8a, armeabi-v7a

# Disable Kivy touch postprocessing delays at the manifest level
android.meta_data = kivy:retain_time:0,kivy:double_tap_time:0,kivy:double_tap_distance:0,kivy:retain_distance:0,kivy:jitter_distance:0

# Keep the app data when updating — users won't lose their saved counts
android.allow_backup = True

# Sign with the same key every build so Android accepts the update.
# Generate once with:
#   keytool -genkey -v -keystore patsb.keystore -alias patsb -keyalg RSA -keysize 2048 -validity 10000
# Then fill in the paths/passwords below and keep patsb.keystore safe.
# android.keystore = patsb.keystore
# android.keystore_password = yourpassword
# android.keyalias = patsb
# android.keyalias_password = yourpassword

fullscreen = 1

icon.filename = %(source.dir)s/icon.png

# Include the assets folder so PNG icons are bundled in the APK
source.include_patterns = assets/*.png,assets/*.jpg

[buildozer]
log_level = 2
warn_on_root = 1
