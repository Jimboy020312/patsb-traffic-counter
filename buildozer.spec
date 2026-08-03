[app]

title = Traffic Counter
package.name = trafficcounter
package.domain = com.trafficcounter

source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json

version = 1.0
# This is patched automatically by the GitHub Actions workflow using
# github.run_number — do not edit manually.
android.numeric_version = 1

requirements = python3,kivy,android,pillow

orientation = landscape

android.permissions = WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE,VIBRATE,WAKE_LOCK

android.api = 33
android.minapi = 21
android.ndk = 25b
# FIX: recent Buildozer defaults `android release` to producing a .aab
# (Google Play App Bundle) instead of a plain .apk. AABs can't be
# sideloaded/installed directly — this forces a real installable APK.
android.release_artifact = apk
# FIX (speed): dropped armeabi-v7a (32-bit) — building for two
# architectures roughly doubles native compile/link/package time on every
# single build. arm64-v8a alone covers essentially all Android phones from
# the last several years. If any surveyor colleague is on a genuinely old
# 32-bit-only device, add "armeabi-v7a" back here.
android.archs = arm64-v8a

# android.meta_data line removed — it used colon-separated format which
# causes buildozer to crash at packaging with "not enough values to unpack".
# Touch postprocessing delays are already disabled in main.py via os.environ
# and Config.set() so this line was redundant anyway.

# Keep the app data when updating — users won't lose their saved counts
android.allow_backup = True

# Sign with the same key every build so Android always accepts the update
# in place, rather than refusing with "conflicts with an existing package".
# The keystore file itself is written out by the CI workflow from a secret
# (see build-android.yml) — it is never committed to the repo. The password
# placeholders below are patched in at build time via sed, the same way
# android.numeric_version is patched using github.run_number.
android.keystore = %(source.dir)s/release.keystore
android.keystore_password = CI_KEYSTORE_PASSWORD_PLACEHOLDER
# FIX: keyalias value intentionally NOT renamed away from 'patsb' — it
# must exactly match the alias baked into the actual keystore file when
# it was originally generated via keytool. Renaming this string alone
# (without also running `keytool -changealias` on the real .keystore
# file) would break APK signing outright.
android.keyalias = patsb
android.keyalias_password = CI_KEY_PASSWORD_PLACEHOLDER

fullscreen = 1

# Android's launcher icon — lives in assets/ alongside the other bundled
# images. Make sure assets/icon_android.png actually exists in your repo.
icon.filename = %(source.dir)s/assets/icon_android.png

# FIX: without this, Android shows Kivy's own default splash logo while
# the APK is bootstrapping (unpacking Python, initializing the runtime)
# — BEFORE main.py's own custom LoadingScreen widget ever gets a chance
# to run. presplash.filename replaces that with our own themed image
# instead, and android.presplash_color fills any letterboxing behind it
# with the exact same dark navy used everywhere else in the app
# (Window.clearcolor / LoadingScreen's background), so the handoff from
# native presplash to the real LoadingScreen is seamless rather than a
# jarring flash between two different looks.
presplash.filename = %(source.dir)s/assets/presplash.png
android.presplash_color = #14171F

# Include the assets folder so PNG icons are bundled in the APK
source.include_patterns = assets/*.png,assets/*.jpg

[buildozer]
log_level = 2
warn_on_root = 1
