# Voice ledger — Android client

Kotlin + Jetpack Compose, Material 3, no extra UI/animation libraries —
built to stay light on a mid-range (A-series) Samsung phone rather
than a flagship.

## Get a real APK (no Android Studio install needed)

1. Push this repo to GitHub.
2. Actions tab → "Android build" runs automatically (or trigger it
   manually via "Run workflow"). It builds on GitHub's own runner,
   which has the real Android SDK.
3. Open the finished run → Artifacts → `voice-ledger-debug-apk`.
   Download, unzip, you have `app-debug.apk`.
4. Install it: `adb install app-debug.apk`, or copy it to the phone
   and open it directly (Settings > allow install from this source,
   the usual sideload prompt for an APK not from Play Store).

That's a debug-signed build — fine for putting it on your own phone,
not for handing to anyone else or Play Store. For that, see "Signing
a release build" below.

## Opening it in Android Studio instead

1. Android Studio (Koala/Ladybug or newer) → Open → this folder.
2. Let it sync Gradle; it'll pull dependencies from Google/Maven
   Central per `settings.gradle.kts`. If it doesn't offer to generate
   a Gradle wrapper automatically, Build > "Generate Signed Bundle /
   APK" will prompt for one.
3. Add a launcher icon (right-click `res/` → New → Image Asset) -
   none is wired up yet, see the note in `AndroidManifest.xml`.
4. Run on a physical device with a fingerprint enrolled (the emulator
   supports simulated fingerprint events too, via
   `adb -e emu finger touch <finger-id>`, if you want to test without
   hardware).

## Signing a release build

Needed once you want to give this APK to someone else, or publish it.

```bash
keytool -genkeypair -v -keystore release.keystore -alias voiceledger \
  -keyalg RSA -keysize 2048 -validity 10000
```

Back that file up somewhere durable, outside this repo — if you lose
it or its password, there's no recovery, and you can never publish an
update under the same app identity again.

**Locally**: copy `keystore.properties.example` → `keystore.properties`,
fill in the passwords, put `release.keystore` next to it (both are
gitignored). Then `gradle assembleRelease` (or Android Studio's
"Generate Signed Bundle / APK") produces a signed
`app/build/outputs/apk/release/app-release.apk`.

**Via CI**: add four repo secrets (Settings > Secrets and variables >
Actions) — `ANDROID_KEYSTORE_BASE64` (`base64 -w0 release.keystore`
output), `ANDROID_KEYSTORE_PASSWORD`, `ANDROID_KEY_ALIAS`,
`ANDROID_KEY_PASSWORD`. The workflow's `release-apk` job picks them up
automatically and uploads a signed `voice-ledger-release-apk` artifact.

A signed APK is still just a file you can sideload — actually
publishing to the Play Store additionally needs a Google Play
Developer account (one-time fee) and a store listing, which is a
product decision for you to make, not something to default into.

## Status: what's tested vs. not

Written outside Android Studio, so it had never been compiled until
the CI workflow above exists to do it. If the first Actions run fails,
expect small things — missing resources, a dependency version bump —
not a rethink of the structure. The parts that matter most were
written carefully and should need the least rework:

- `biometric/BiometricSigner.kt` — Keystore key generation
  (`setUserAuthenticationRequired` + `setInvalidatedByBiometricEnrollment`,
  with the correct API-30-vs-earlier branching) and the
  `BiometricPrompt.CryptoObject` signing flow. This is the piece
  worth reviewing most closely, since it's the actual security
  mechanism.
- `network/CanonicalJson.kt` + `network/ApiClient.kt` — talks to the
  server's pairing and transaction endpoints.
- `audio/AudioRecorder.kt` — records straight to 16kHz mono WAV, the
  format the server's STT expects, so no transcoding is needed
  anywhere in the pipeline.

## What's still a stub / needs your decisions

- **Server discovery**: the Settings screen takes a manually-typed
  LAN address (`http://192.168.1.42:8420/`). If you want automatic
  discovery instead of typing an IP, add Android's `NsdManager` to
  discover a `_voiceledger._tcp` mDNS service the server advertises -
  not implemented here to keep the first cut simple and testable.
- **Persisting `serverBaseUrl` / `deviceId`**: currently in-memory
  only (lost on process death). Wire up the `androidx.datastore`
  dependency already in `build.gradle.kts` — it's in there but unused.
- **History screen**: `GET /transactions` is implemented in
  `ApiClient.kt` and ready to call; there's no screen showing it yet.
- **Free-form (single long utterance) capture mode**: only guided
  (field-by-field) mode has a UI. Free-form would reuse the same
  `speechToText` call, then hit `/nlu/*` differently — see
  `server/app/nlu/extractor.py`.

- **Server discovery**: the Settings screen takes a manually-typed
  LAN address (`http://192.168.1.42:8420/`). If you want automatic
  discovery instead of typing an IP, add Android's `NsdManager` to
  discover a `_voiceledger._tcp` mDNS service the server advertises -
  not implemented here to keep the first cut simple and testable.
- **Persisting `serverBaseUrl` / `deviceId`**: currently in-memory
  only (lost on process death). Wire up the `androidx.datastore`
  dependency already in `build.gradle.kts` — it's in there but unused.
- **History screen**: `GET /transactions` is implemented in
  `ApiClient.kt` and ready to call; there's no screen showing it yet.
- **Free-form (single long utterance) capture mode**: only guided
  (field-by-field) mode has a UI. Free-form would reuse the same
  `speechToText` call, then hit `/nlu/*` differently — see
  `server/app/nlu/extractor.py`.
