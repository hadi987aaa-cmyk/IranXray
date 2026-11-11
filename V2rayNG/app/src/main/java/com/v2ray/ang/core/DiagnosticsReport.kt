package com.v2ray.ang.core

/**
 * Builds the short summary the About screen copies to the clipboard.
 *
 * Deliberately carries no server address, port, UUID, password or subscription URL:
 * the text is meant to be safe to paste into a public issue.
 */
object DiagnosticsReport {
    fun build(
        appVersion: String,
        libVersion: String,
        cores: String,
        androidVersion: String,
        sdkInt: Int,
        mode: String,
        socksPort: Int,
        remoteDns: List<String>,
        routingRulesets: Int,
        delayTestUrl: String,
    ): String = buildString {
        appendLine("IranXray $appVersion (Xray $libVersion, cores $cores)")
        appendLine("Android $androidVersion (SDK $sdkInt)")
        appendLine("Mode: $mode")
        appendLine("SOCKS port: $socksPort")
        appendLine("DNS: ${if (remoteDns.isEmpty()) "-" else remoteDns.joinToString(", ")}")
        appendLine("Routing rulesets: $routingRulesets")
        append("Delay test: $delayTestUrl")
    }
}
