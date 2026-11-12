package com.v2ray.ang.core

import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertFalse
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.Test

class DiagnosticsReportTest {

    private fun report(remoteDns: List<String> = listOf("https://8.8.8.8/dns-query")) =
        DiagnosticsReport.build(
            appVersion = "0.10.0",
            libVersion = "26.11.1",
            cores = "lite",
            androidVersion = "13",
            sdkInt = 33,
            mode = "vpn",
            socksPort = 10808,
            remoteDns = remoteDns,
            routingRulesets = 1,
            delayTestUrl = "https://www.bing.com"
        )

    @Test
    fun `report lists every setting on its own line`() {
        assertEquals(
            listOf(
                "Shaghali 0.10.0 (Xray 26.11.1, cores lite)",
                "Android 13 (SDK 33)",
                "Mode: vpn",
                "SOCKS port: 10808",
                "DNS: https://8.8.8.8/dns-query",
                "Routing rulesets: 1",
                "Delay test: https://www.bing.com"
            ),
            report().lines()
        )
    }

    @Test
    fun `report ends without a trailing blank line`() {
        assertFalse(report().endsWith("\n"), report())
    }

    @Test
    fun `an empty dns list prints a dash instead of an empty label`() {
        assertTrue(report(emptyList()).lines().contains("DNS: -"))
    }

    @Test
    fun `several dns servers stay on one line`() {
        val line = report(listOf("https://1.1.1.1/dns-query", "178.22.122.100"))
            .lines()
            .single { it.startsWith("DNS:") }
        assertEquals("DNS: https://1.1.1.1/dns-query, 178.22.122.100", line)
    }

    @Test
    fun `the report never carries a share link or credential`() {
        val text = report()
        listOf("vmess://", "vless://", "trojan://", "ss://", "uuid").forEach {
            assertFalse(text.contains(it, ignoreCase = true), text)
        }
    }
    @Test
    fun `the shaping summary appears when the caller supplies one`() {
        val text = DiagnosticsReport.build(
            appVersion = "1.0.0",
            libVersion = "26.11.1",
            cores = "lite",
            androidVersion = "13",
            sdkInt = 33,
            mode = "vpn",
            socksPort = 10808,
            remoteDns = emptyList(),
            routingRulesets = 0,
            delayTestUrl = "https://www.bing.com",
            shaping = DiagnosticsReport.shapingSummary()
        )
        val line = text.lines().single { it.startsWith("Shaping:") }
        assertTrue(line.contains("mask 60-160"), line)
        assertTrue(line.contains("xhttp 22-55"), line)
        assertTrue(line.contains("post 400-900 KB"), line)
        assertEquals("Delay test: https://www.bing.com", text.lines().last())
    }
}
