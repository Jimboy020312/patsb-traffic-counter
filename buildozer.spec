[app]

title = PATSB Traffic Counter
package.name = patsbtrafficcounter
package.domain = com.patsb

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
# (see build.yml) — it is never committed to the repo. The password
# placeholders below are patched in at build time via sed, the same way
# android.numeric_version is patched using github.run_number.
android.keystore = %(source.dir)s/patsb-release.keystore
android.keystore_password = CI_KEYSTORE_PASSWORD_PLACEHOLDER
android.keyalias = patsb
android.keyalias_password = CI_KEY_PASSWORD_PLACEHOLDER

fullscreen = 1

# FIX: icon.png moved into assets/ alongside the other bundled images —
# move the actual file to assets/icon.png in your repo to match.
icon.filename = %(source.dir)s/assets/icon_android.png

# Include the assets folder so PNG icons are bundled in the APK
source.include_patterns = assets/*.png,assets/*.jpg

[buildozer]
log_level = 2
warn_on_root = 1
