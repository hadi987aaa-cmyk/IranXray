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

## Feature: Cloudflare address scan

A profile fronted by Cloudflare keeps its own domain as Host/SNI, but the anycast address it
points at can be throttled or blocked. The address field of the server editor now carries a scan
action that probes candidate Cloudflare edge addresses, each with the profile's own SNI, and
writes the fastest one that completes a TLS handshake into the address and port fields.

| File | Change |
|---|---|
| `core/CfIpScanner.kt` | new — CIDR → candidate addresses, TLS handshake probe with a given SNI, bounded-concurrency scan returning the successful endpoints fastest first |
| `core/CfScanRunner.kt` | new — the runner interface the view model depends on, plus its network implementation |
| `ui/server/CfScanViewModel.kt` | new — scan state (`running`, `done`, `total`, `results`, `problem`) as `StateFlow`; refuses a blank SNI, replaces a running scan, keeps the previous results until the new run finishes |
| `ui/server/CfScanDialog.kt` | new — the dialog: SNI field, progress, result rows, Scan/Stop |
| `ui/server/BaseServerActivity.kt` | address field gets the scan action and hosts the dialog; picking a result fills address and port |
| `res/values*/strings.xml` (10 locales) | nine `cf_scan_*` strings, translated for every locale in `localeFilters` |
| `test/.../core/CfIpScannerTest.kt` | new — candidate count, range containment, determinism, invalid CIDR handling, CIDR parsing and IP formatting |
| `test/.../ui/server/CfScanViewModelTest.kt` | new — idle state, blank SNI refusal, no-candidate problem, progress and results, running until the runner returns, stop, runner failure |

Why a TLS handshake is the test: the probe has to reuse the profile's real SNI, because what
Iranian filtering blocks is often the name (or the handshake shape), not the address. A probe to
`https://<ip>` with a mismatched name would report success for endpoints the profile still cannot
use. `endpointIdentificationAlgorithm` is cleared so a valid certificate for another name does
not fail the probe; the dialog's job is reachability of this SNI through this address, not
certificate validation, which the core still performs when the profile connects.

Not verified: the dialog was never rendered on a device or emulator, so its layout at large font
scales, its IME behaviour and its TalkBack labels are unverified. `Not run` for the semantics,
focus-order and IME checks that `ui/AGENTS.md` requires.

