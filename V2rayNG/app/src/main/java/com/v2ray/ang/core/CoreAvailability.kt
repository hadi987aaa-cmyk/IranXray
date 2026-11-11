package com.v2ray.ang.core

import com.v2ray.ang.BuildConfig

/**
 * IranXray: which native cores this APK carries.
 *
 * A `lite` build leaves Aether out — with the Psiphon client and the Tor pluggable transport it launches — because
 * those three binaries are most of the APK's size and a profile that does not select them never runs them. Everything
 * else in the app works without them, so the screens that would need one ask this first, see `docs/agent/CHANGES.md`.
 */
object CoreAvailability {

    /** Whether this build packages the optional cores: Aether, `libpsiphon-tunnel-core.so` and `liblyrebird.so`. */
    val hasOptionalCores: Boolean get() = BuildConfig.CORES != "lite"
}
