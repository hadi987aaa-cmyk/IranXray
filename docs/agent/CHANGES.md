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
