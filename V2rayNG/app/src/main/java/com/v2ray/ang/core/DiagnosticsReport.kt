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
        shaping: String = "",
    ): String = buildString {
        appendLine("Shaghali $appVersion (Xray $libVersion, cores $cores)")
        appendLine("Android $androidVersion (SDK $sdkInt)")
        appendLine("Mode: $mode")
        appendLine("SOCKS port: $socksPort")
        appendLine("DNS: ${if (remoteDns.isEmpty()) "-" else remoteDns.joinToString(", ")}")
        appendLine("Routing rulesets: $routingRulesets")
        if (shaping.isNotBlank()) {
            appendLine("Shaping: $shaping")
        }
        append("Delay test: $delayTestUrl")
    }

    /**
     * Describes the sampling this build applies at connect time, so a pasted report says which
     * transport shape produced it. Built from the constants that do the sampling, never a copy of them.
     */
    fun shapingSummary(): String = buildString {
        append("mask ${IranMaskJitter.MIN_TIMES}-${IranMaskJitter.MAX_TIMES} / ")
        append("${IranMaskJitter.MIN_DELAY_MS}-${IranMaskJitter.MAX_DELAY_MS} ms / ")
        append("${IranMaskJitter.MIN_MAX_BYTES_KB}-${IranMaskJitter.MAX_MAX_BYTES_KB} KB")
        append(", xhttp ${XhttpJitter.MIN_INTERVAL_MS}-${XhttpJitter.MAX_INTERVAL_MS} ms")
    }
}
