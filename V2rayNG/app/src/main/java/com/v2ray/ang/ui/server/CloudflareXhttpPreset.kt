package com.v2ray.ang.ui.server

import com.v2ray.ang.AppConfig.TLS
import com.v2ray.ang.enums.NetworkType

/**
 * Applies the client-side settings expected by a VLESS + XHTTP endpoint behind
 * Cloudflare's orange-cloud HTTP proxy.
 *
 * This is only a client preset: the origin must independently support TLS/H2,
 * XHTTP, and Cloudflare gRPC proxying. A literal IP still needs a hostname in
 * SNI/Host, which the user can provide in the existing fields.
 */
internal object CloudflareXhttpPreset {
    fun apply(state: ServerUiState) {
        val address = state.address.trim()
        val configuredSni = state.sni.trim()
        val configuredHost = state.host.trim()
        val domain = configuredSni.ifBlank {
            configuredHost.ifBlank { address.takeUnless(::isIpLiteral).orEmpty() }
        }

        state.port = "443"
        state.network = NetworkType.XHTTP.type
        state.xhttpMode = "auto"
        state.flow = ""
        state.streamSecurity = TLS
        state.allowInsecure = false
        state.fingerPrint = state.fingerPrint.ifBlank { "chrome" }
        state.alpn = "h2"
        state.sni = domain
        state.host = configuredHost.ifBlank { domain }
        state.echConfigList = ""
        state.echOutbound = ""
    }

    private fun isIpLiteral(value: String): Boolean =
        value.contains(':') || IPV4_PATTERN.matches(value)

    private val IPV4_PATTERN = Regex("""(?:[0-9]{1,3}\.){3}[0-9]{1,3}""")
}
