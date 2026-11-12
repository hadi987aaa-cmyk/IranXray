# Agent lane

This branch (`agent/iran-mode`) is the isolated workspace of the DSH coding agent. It exists so
that work here never collides with the `iranxray/bootstrap` branch, which another assistant is
editing at the same time.

## Ground rules

- **Branch:** `agent/iran-mode`, forked from `my-releases` at `e7a52cf`.
- **Package id:** `com.shaghali.app` (round 13; earlier rounds used `com.iranxray.agent`; upstream `com.patterniha.pattng`) so it installs next to
  PattNG and next to the `com.iranxray.client` build from the other branch.
- **Own pipeline:** `.github/workflows/build-agent.yml` runs only on `agent/**` and on manual
  dispatch. The debug workflow that builds `iranxray/**` never triggers here, and vice versa.
- **Cache keys** are byte-identical to that workflow's, so the native libraries (`libs`,
  `libs-aether`, `libs-psiphon`, `libs-pt`) are shared and a warm repo makes this build warm too.
- **Files this branch owns:** `.github/workflows/build-agent.yml`, `docs/agent/`, and additive
  Kotlin under `V2rayNG/app/src/main/java/com/v2ray/ang/`. Everything else is only touched with
  small, reviewable edits — listed below.

## Round 15: the XHTTP rhythm is sampled per connection

A live capture on the user's own server showed the tunnel emitting one 47-byte prelude followed by one
~380-byte body every 20 ms for as long as the session lasted: the default `scMinPostsIntervalMs`. Any
filter can key on that rhythm without ever reading the payload, and every user of this build shares it.

`core/XhttpJitter.kt` fills `scMinPostsIntervalMs` (22-55 ms) and `xpaddingBytes` (a 150-900 byte
window) per connection, and `core/CoreOutboundBuilder.kt` applies it where the XHTTP settings are built.
A value the user typed is preserved; only absent keys are filled in.

| File | Change |
|---|---|
| `V2rayNG/app/src/main/java/com/v2ray/ang/core/XhttpJitter.kt` | new: samples the two timing knobs |
| `V2rayNG/app/src/main/java/com/v2ray/ang/core/CoreOutboundBuilder.kt` | the XHTTP block applies the sampled extra |
| `V2rayNG/app/src/test/java/com/v2ray/ang/core/XhttpJitterTest.kt` | new: 7 tests over blank, hand-written and unreadable input |

Not run: no device build here. The new rhythm has to be confirmed by capturing the tunnel again on the
server, which is the next step with the user.
## Round 16: 1.0.0, the build a user can keep

The About screen's diagnostics line now records which sampling produced the report
(`Shaping: mask 60-160 / 18-45 ms / 8-28 KB, xhttp 22-55 ms`), assembled from the jitter constants
themselves so it cannot drift, and `docs/PRODUCT.md` is the short Persian guide a user needs
(install, add a config, the two buttons, the sampling table, the escape hatch, the limits).

| File | Change |
|---|---|
| `V2rayNG/app/src/main/java/com/v2ray/ang/core/DiagnosticsReport.kt` | optional `shaping` line + `shapingSummary()` |
| `V2rayNG/app/src/main/java/com/v2ray/ang/core/IranMaskJitter.kt` | sampling ranges exposed as public constants |
| `V2rayNG/app/src/main/java/com/v2ray/ang/ui/AboutActivity.kt` | passes the summary into the report |
| `V2rayNG/app/src/test/java/com/v2ray/ang/core/DiagnosticsReportTest.kt` | asserts the shaping line and its position |
| `docs/PRODUCT.md` | new: Persian user guide |

Not run: no device build here; the app still has to be tried on the phone.
## Round 17: the upload chunk ceiling is sampled too

The interval and the padding were sampled in round 15, but every session still advertised the same
maximum POST payload, so the *size* half of the rhythm stayed constant. `scMaxEachPostBytes` is now
drawn per connection from 400-900 KB, and the diagnostics line records it next to the other ranges.

| File | Change |
|---|---|
| `V2rayNG/app/src/main/java/com/v2ray/ang/core/XhttpJitter.kt` | samples `scMaxEachPostBytes` when the profile leaves it out |
| `V2rayNG/app/src/main/java/com/v2ray/ang/core/DiagnosticsReport.kt` | `post <min>-<max> KB` appended to the shaping line |
| `V2rayNG/app/src/test/java/com/v2ray/ang/core/XhttpJitterTest.kt` | asserts the sampled ceiling and its ordering |
| `V2rayNG/app/src/test/java/com/v2ray/ang/core/DiagnosticsReportTest.kt` | asserts the new segment of the shaping line |

A value the user wrote themselves is still left alone: only absent keys are filled.

Not run: no device build here; the transport still has to be compared against a capture from the phone.
## Changes against `my-releases`

| File | Change |
|---|---|
| `V2rayNG/app/build.gradle.kts` | `applicationId` → `com.iranxray.agent`; `versionName` also reads `-PiranXrayVersion`; output file names `PattNG_*` → `IranXray_*` |
| `.github/workflows/build-agent.yml` | new — debug APK build, fixed debug signing key, release publishing, native-library inspection |
| `docs/agent/CHANGES.md` | this file |

## Priority

The user's priority is stated explicitly: the configs that must work are the ones **behind the
Cloudflare orange cloud** (proxied DNS), because Iran's filtering now restricts Cloudflare
severely. Anything that improves that path — TCP write masking, first-packet obfuscation,
ClientHello fragmentation, clean-edge scanning, XHTTP padding — ranks above other features.

## Removed: Cloudflare address scan

The scan feature (commit `012ed4e`) was withdrawn at the user's request: he wants the client to
stay lean and the address field simple. `BaseServerActivity.kt` and the ten `res/values*/strings.xml`
were restored from base `e7a52cf`, and `core/CfIpScanner.kt`, `core/CfScanRunner.kt`,
`ui/server/CfScanViewModel.kt`, `ui/server/CfScanDialog.kt` and their two tests were deleted in one
commit. Only the settings a profile needs remained.

## Round 1: lite builds (release `agent-10`)

The measured APK was 76.4 MB, of which ~54 MB was three optional native cores that this user never
selects: `libpsiphon-tunnel-core.so` 20.9 MB, `libaether.so` 18.0 MB, `liblyrebird.so` 15.5 MB.

| File | Change |
|---|---|
| `.github/workflows/build-agent.yml` | `cores` choice input (`lite` default, `all` opt-in); the Aether/Psiphon/Tor Rust-Go steps, their caches and the Psiphon server list run only for `all`; staging copies `libs/` always and the optional cores only for `all` |
| `V2rayNG/app/src/main/java/com/v2ray/ang/AppConfig.kt` | `DELAY_TEST_URL` `https://www.gstatic.com/generate_204` -> `https://www.bing.com`; `DELAY_TEST_URL2` `https://www.google.com/generate_204` -> `https://www.wikipedia.org` (both old hosts are blocked in Iran, so every latency test reported a timeout) |

Result: 53,731,247 B (51.2 MiB). Startup is unaffected because the only `System.loadLibrary` in the
app is `TProxyService.kt:39` `System.loadLibrary("hev-socks5-tunnel")`; the optional cores are
launched as child processes and are only reached when a profile selects them.

## Round 2: R8 (release `agent-12`)

`isMinifyEnabled` and `isShrinkResources` were hard-coded `false`, which left 33.9 MB of dex.

| File | Change |
|---|---|
| `V2rayNG/app/build.gradle.kts` | release `isMinifyEnabled` / `isShrinkResources` follow `-PiranXrayMinify` (default false, so an ad-hoc build without the flag stays debuggable) |
| `V2rayNG/app/proguard-rules.pro` | keeps `com.v2ray.ang.service.**` (the native tunnel calls back through fixed JNI names built with `-DPKGNAME=com/v2ray/ang/service`), `libv2ray.**`, `com.v2ray.ang.dto.**` and its fields (Gson writes them by name), the enums, `com.tencent.mmkv.**`, and the attributes R8 strips by default |
| `.github/workflows/build-agent.yml` | `minify` boolean input (default true) and `MINIFY` env; both assemble commands pass `-PiranXrayMinify` |

Result: 25,272,017 B (24.1 MiB), one `classes.dex` of 5.7 MB, zero missing-class warnings, the
signature unchanged (`CN=Cloak`). `Not run`: the runtime checks R8 makes necessary (launch, profile
persistence across restart, settings save, connecting a profile) were not executed on a device in
this round.

## Round 3: Iran preset (this build)

The three client-side settings that decide whether a handshake survives Iranian DPI lived in three
different parts of the form. One button now sets all three.

| File | Change |
|---|---|
| `ui/server/IranPreset.kt` | new: `FINGERPRINT = "chrome"`, `DIAL_MODE = "oob.0"`, `FINAL_MASK` = the `merge` preset (`times: 100`, `delayMs: 30`, `maxBytes: 16384`), kept byte-identical to `final_mask_preset_values` in `res/values/arrays.xml` |
| `ui/server/BaseServerActivity.kt` | `IranPresetButton` under the dialMode field: sets the three values and confirms with a toast |
| `res/values*/strings.xml` (10 locales) | `server_preset_iran`, `server_preset_iran_applied`, `server_preset_iran_hint` |
| `test/.../ui/server/IranPresetTest.kt` | new: the mask parses as JSON and carries the merge settings; the two literal values stay what Xray reads |

The preset does not touch the address, the port or the keys: those belong to the server. It also
cannot turn mux off, because mux is a global setting (`PREF_MUX_ENABLED`), not a profile one.

## Round 4: lite builds hide the cores they lack

A lite build leaves `libaether.so`, `libpsiphon-tunnel-core.so` and `liblyrebird.so` out, but the UI still offered
Aether in the import menu and still listed Aether profiles saved by a full build. Selecting either failed without
saying why.

| File | Change |
|---|---|
| `V2rayNG/app/build.gradle.kts` | `buildConfigField("String", "CORES", ...)` from `-PiranXrayCores` (default `all`, so an ad-hoc build keeps every core) |
| `.github/workflows/build-agent.yml` | both assemble commands pass `-PiranXrayCores="$CORES"` |
| `core/CoreAvailability.kt` | new: `hasOptionalCores`, true unless `BuildConfig.CORES == "lite"` |
| `ui/main/MainImportMenu.kt` | `importMenuActions()` drops the Aether entry when the cores are absent; the composable calls it |
| `ui/main/MainActivity.kt` | `importManually` refuses Aether with a toast when the cores are absent (deep links and intents reach it too) |
| `core/LauncherManager.kt` | `refusesMissingCore` stops a start from the button and from the quick-settings tile when the selected profile is an Aether one, and explains why |
| `res/values*/strings.xml` (10 locales) | `toast_aether_not_packaged` |
| `test/.../ui/main/ImportMenuActionsTest.kt` | new: only Aether leaves the menu; a full build still offers it |

`Not run`: the toast and the menu were not observed on a device in this round.

## Round 5: the app stops carrying another build's promotion and logo

Three things in the drawer were inherited from upstream and visible on every launch: a
`Promotion` entry that opened a third-party web page (`https://9.234456.xyz/abc.html`, base64 in
`AppConfig.APP_PROMOTION_URL`), and a 270 KB `ic_pattng_logo.png` shown as the drawer header, while
the launcher icon was already this build's own. The nine newest strings also fell back to English
in every one of the nine translations.

| File | Change |
|---|---|
| `ui/main/MainDrawer.kt` | `MainDestination.Promotion` removed from the enum and from the drawer list; header image is `R.mipmap.ic_launcher_foreground` instead of `R.drawable.ic_pattng_logo` |
| `ui/main/MainActivity.kt` | the `Promotion` branch of `navigateTo` removed, so no code path opens that page |
| `res/drawable-nodpi/ic_pattng_logo.png` | deleted (270,217 B) |
| `res/values*/strings.xml` (9 locales) | the nine strings that were only in `values/`: `aether_hint_fragment_delay`, `aether_hint_fragment_size`, `aether_lab_exit_dial_mode`, `aether_lab_exit_node`, `preset_setting_cipher_suites`, `preset_setting_dial_mode`, `preset_setting_final_mask`, `server_lab_target_strategy`, `sub_info_traffic` |
| `.github/workflows/build-agent.yml` | two new checks after the assemble step: `BuildConfig.CORES` must carry the requested core set, and every `values-*` locale must carry every key of `values/` |
| `docs/agent/CHANGES.md` | this section |

The two checks exist because both failures are silent: a misnamed gradle property falls back to
`all` (a lite build would ship every core again without a word), and a missing translation falls
back to English on that phone. `AppConfig.APP_PROMOTION_URL` itself is left in place; nothing reads
it any more.

`Not run`: the drawer was not looked at on a device in this round.

## Round 6: the built-in update check looks at this repository

The drawer's "check for update" asked `patterniha/PattNG` for its newest release, so it would have
offered an upstream APK: a different signing key, so the install fails, and a version numbering
that has nothing to do with this fork. Pointing it here alone would not have been enough either —
builds are tagged `agent-<run number>`, and `agent-20` orders above `0.5.0`, so every run would
have looked like an update for ever.

| File | Change |
|---|---|
| `AppConfig.kt` | `APP_URL` and `APP_API_URL` point at `hadi987aaa-cmyk/IranXray`; the round-1 delay-test constants get their indentation back |
| `handler/UpdateCheckerManager.kt` | `releaseVersion()` reads the app version out of the asset name (`IranXray_<version>_<abi>.apk`) and falls back to a numeric `v<version>` tag; a release carrying neither is not offered, instead of nagging with an unorderable tag; `compareVersions` is `internal` so the test can reach it |
| `test/.../handler/UpdateCheckerManagerTest.kt` | new: the asset name wins over the tag, unorderable tags are refused, `0.10.0 > 0.9.0`, and the newest build of the installed version is not an update |

`Not run`: the dialog was not opened on a device in this round.

## Round 7: the app stops calling itself PattNG on every language but English

`app_name` is `translatable="false"`, yet all nine locale files carried their own copy — set to
`PattNG`. A Persian phone therefore showed the upstream name under the launcher icon, in the
notification channel ("سرویس PattNG"), on the quick-settings tile and in several Vietnamese toasts,
while only the English/default resource said `IranXray`.

| File | Change |
|---|---|
| `res/values-*/strings.xml` (9 locales) | the `app_name` copy removed, since one non-translatable value in `values/` serves every locale |
| `res/values*/strings.xml` (10 files) | the remaining `PattNG` mentions replaced by `IranXray` (notification channel, widget and tile labels, the Vietnamese strings, `title_server`) |
| `.github/workflows/build-agent.yml` | the locale-parity check now ignores `translatable="false"` keys, and a new check fails the build when `PattNG` survives anywhere under `res/values*/` |

`Not run`: the launcher label and the notification channel were not looked at on a device.

## Round 8: the help and policy links belong to this fork

The About screen still had three rented links. "Telegram channel" opened `t.me/github_2dust`,
the upstream author's channel; the privacy policy was fetched from `2dust/v2rayNG`; and the
settings screen's "mode help" opened `$APP_URL/wiki/Mode`, a wiki the fork does not have, so the
tap landed on a 404.

| File | Change |
|---|---|
| `AppConfig.kt` | `APP_DOCS_URL` added; `APP_WIKI_MODE` and `APP_PRIVACY_POLICY` point at this repository's own documents; `TG_CHANNEL_URL` and the dead `APP_PROMOTION_URL` removed |
| `ui/AboutActivity.kt` | the Telegram row removed — the fork has no channel to send anyone to |
| `docs/PRIVACY.md` | new: what is stored locally, what leaves the device, permissions, third-party cores |
| `docs/MODE.md` | new: VPN, proxy-only and root modes, what each one intercepts, and the notes that matter on Iranian networks |

The document links carry the branch name (`blob/agent/iran-mode/docs`) because the files only
exist here; both paths have to move when this branch is merged.

`Not run`: the About screen and the mode-help tap were not exercised on a device in this round.

## Round 9: the routing presets only reference codes that exist

Xray drops a routing rule whose `geosite:`/`geoip:` code is not in the packaged database, and
says so only in its own log. The APK therefore shipped one dead rule: `custom_routing_black`
asked for `geosite:gfw`, a category the bundled Iran-oriented geosite does not carry, so the
"proxy the blocked sites" rule of that preset matched nothing but `geosite:greatfire`.

| File | Change |
|---|---|
| `assets/custom_routing_black` | `geosite:gfw` removed from the blocked-sites rule; `geosite:greatfire` already carries that list in the bundled database |
| `scripts/agent/check_routing_codes.py` | new: reads the codes out of `assets/geosite.dat` and `assets/geoip.dat` inside the built APK and compares them with every code the packaged `assets/custom_routing_*` files reference |
| `.github/workflows/build-agent.yml` | new step "Verify the routing presets only use codes the databases carry", after the release is published so a broken preset cannot cost a working APK |

Checked against a local build of 0.8.0 first: 18 referenced codes, 17 present, `geosite:gfw`
missing — the same one this change removes.

`Not run`: the black preset was not selected on a device in this round.
## Round 10: one tap copies a diagnostics summary

When the connection misbehaves on a phone, the only thing the user can send is "it does not work".
The About screen now has a "Copy diagnostics" row that puts a short, paste-safe summary on the
clipboard: app version, Xray library version, the cores this build carries, Android version,
the running mode, the SOCKS port, the remote DNS servers, how many routing rulesets are stored
and the delay-test URL.

It deliberately contains no server address, port, UUID, password or subscription URL, so the
text can be pasted into a public issue.

| File | Change |
|---|---|
| ``core/DiagnosticsReport.kt`` | new: pure builder for the report text, no Android imports so it is JVM-testable |
| ``ui/AboutActivity.kt`` | the report is assembled in the activity (the UI layer must not read settings or storage), passed into ``AboutScreen``, and copied with ``LocalClipboardManager`` plus a toast |
| ``res/values*/strings.xml`` | three new strings (row title, subtitle, toast) in all ten locales |
| ``test/.../core/DiagnosticsReportTest.kt`` | new: exact line layout, no trailing blank line, empty DNS prints ``-``, several servers stay on one line, and no share-link scheme or credential ever appears |

``Not run``: the clipboard copy and the toast were not exercised on a device in this round.
## Round 11: the release APK stores classes.dex compressed

Measurement first: in the 0.10.0 APK, `classes.dex` (5,702,540 B), `resources.arsc` and the
`res/**.png` entries are all stored with method 0, i.e. not deflated, which is the modern AGP
default. Only `lib/**` and `assets/**` were compressed.

`resources.arsc` must stay uncompressed (Android 11+ requirement), but `classes.dex` does not.
`packaging { dex { useLegacyPackaging = true } }` turns the old behaviour back on: Android
extracts the dex at install time instead of mapping it straight from the APK.

| File | Change |
|---|---|
| ``V2rayNG/app/build.gradle.kts`` | ``packaging { dex { useLegacyPackaging = true } }``; ``jniLibs`` keeps its existing setting |

Trade-off accepted: a small cold-start cost in exchange for a smaller file to download by hand.
If the DSL name were wrong the Gradle configuration step would fail immediately, before the
long native steps, so the experiment costs a minute at most.

``Not run``: cold-start time was not measured on a device in this round.
## Round 12: the remote-endpoint lookup no longer depends on one host

After a connection succeeds the app asks a public JSON endpoint for the exit country and address
and shows them in the notification. Only `https://api.ip.sb/geoip` was ever asked, so when that
host is unreachable the label simply stayed empty.

`SpeedtestManager.getRemoteIPInfo()` now walks a short ordered list: the address from the
`ip_api_url` setting first, then `https://api.ip.sb/geoip`, `https://ipinfo.io/json` and
`https://api.myip.com`, stopping at the first answer. A blank setting is skipped rather than
treated as "no lookup". `IPAPIInfo` gained the `cc` field that myip.com uses for the country code.

| File | Change |
|---|---|
| ``handler/SpeedtestManager.kt`` | fallback chain via ``candidateIpInfoUrls`` (trimmed, de-duplicated, configured first); per-request timeout 4 s; an answer with neither address nor country counts as a failure so the next host is tried |
| ``dto/IPAPIInfo.kt`` | ``cc`` field, read before the free-form ``country`` name |
| ``test/.../handler/SpeedtestManagerTest.kt`` | new: order, blank setting, de-duplication, trimming, the historical default first, and parsing of the myip/ipinfo JSON shapes |

``Not run``: the notification text was not observed on a device in this round.
## Round 13: the app is now called Shaghali

The name, the icon and the palette were still rented from upstream and from my own earlier
placeholder. This round gives the app its own identity end to end - launcher label, notification
channel, adaptive icon (background, foreground, monochrome), legacy icon and round icon at five
densities, the TV banner, the Compose colour schemes and the window background.

Because the identity is the package name for Android, `applicationId` moved to
`com.shaghali.app`. That is a **new install**: the old `com.iranxray.agent` stays where it is,
so a working profile can be kept until the new build is verified, but settings and profiles do not
migrate between the two.

The release asset names moved with the brand (`Shaghali_<version>_<abi>.apk`), and
`UpdateCheckerManager` parses that prefix, so the in-app update check keeps working.

| File | Change |
|---|---|
| `app/build.gradle.kts` | `applicationId = "com.shaghali.app"`; output names `Shaghali_*` / `Shaghali_fdroid_*` |
| `res/mipmap-*/` | new `ic_launcher`, `ic_launcher_round`, `ic_launcher_bg`, `ic_launcher_foreground`, `ic_launcher_monochrome` at mdpi..xxxhdpi; new `ic_banner` / `ic_banner_foreground` (320x180) |
| `res/values/ic_banner_background.xml` | banner background `#17123A` instead of white |
| `res/values*/strings.xml` | `app_name` and `notification_channel_service` now say Shaghali in all ten locales |
| `ui/compose/Theme.kt` | indigo/emerald/cyan colour schemes for light and dark, new semantic colours |
| `res/values/themes.xml` | window background `#FBFAFF` light / `#0B0A14` dark |
| `handler/UpdateCheckerManager.kt` | asset-version regex `Shaghali_(\d+(?:\.\d+)*)_` |
| `core/DiagnosticsReport.kt` | the copied summary starts with `Shaghali <version>` |
| `.github/workflows/build-agent.yml` | artifact/release names `Shaghali-*`; the resource brand guard now rejects `PattNG` **and** `IranXray` |

`Not run`: the icon was not observed on a launcher, and the dark palette was not compared on a
device in this round.

## Round 14: the preset no longer sends one fixed shape

| File | Change |
| --- | --- |
| `core/IranMaskJitter.kt` | new: samples `times` 60-160, `delayMs` 18-45, `maxBytes` 8-28 KB for an untouched preset mask; leaves a hand-written mask, or one carrying `udp`/`quicParams`, alone |
| `core/CoreOutboundBuilder.kt` | both places that apply a profile's `finalMask` now pass it through `IranMaskJitter.apply(...)` |
| `test/.../core/IranMaskJitterTest.kt` | 6 tests: presets recognised, sampled values in range, seeded determinism, hand-written mask untouched, udp mask untouched, blank/unreadable untouched |

Why: every profile that presses the one-tap Iran preset used to send the identical merge shape
(`times` 100, `delayMs` 30, `maxBytes` 16384), so a filter rule written against that exact shape
would burn every user at once. The sampled shape keeps the batching that defeats packet-boundary DPI
while removing the shared constant.

`Not run`: nothing was captured on a device or a server, so the effect on a real DPR is unproven;
the ranges are a reasoned envelope, not a measured distribution.