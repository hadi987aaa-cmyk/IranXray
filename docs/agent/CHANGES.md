# Agent lane

This branch (`agent/iran-mode`) is the isolated workspace of the DSH coding agent. It exists so
that work here never collides with the `iranxray/bootstrap` branch, which another assistant is
editing at the same time.

## Ground rules

- **Branch:** `agent/iran-mode`, forked from `my-releases` at `e7a52cf`.
- **Package id:** `com.iranxray.agent` (upstream `com.patterniha.pattng`) so it installs next to
  PattNG and next to the `com.iranxray.client` build from the other branch.
- **Own pipeline:** `.github/workflows/build-agent.yml` runs only on `agent/**` and on manual
  dispatch. The debug workflow that builds `iranxray/**` never triggers here, and vice versa.
- **Cache keys** are byte-identical to that workflow's, so the native libraries (`libs`,
  `libs-aether`, `libs-psiphon`, `libs-pt`) are shared and a warm repo makes this build warm too.
- **Files this branch owns:** `.github/workflows/build-agent.yml`, `docs/agent/`, and additive
  Kotlin under `V2rayNG/app/src/main/java/com/v2ray/ang/`. Everything else is only touched with
  small, reviewable edits — listed below.

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