package com.v2ray.ang.handler

import com.google.gson.Gson
import com.v2ray.ang.dto.IPAPIInfo
import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.Test

class SpeedtestManagerTest {

    @Test
    fun `the configured address is asked first`() {
        val urls = SpeedtestManager.candidateIpInfoUrls(
            "https://example.com/ip",
            listOf("https://api.ip.sb/geoip", "https://ipinfo.io/json")
        )
        assertEquals(
            listOf("https://example.com/ip", "https://api.ip.sb/geoip", "https://ipinfo.io/json"),
            urls
        )
    }

    @Test
    fun `a blank setting falls back to the built-in list`() {
        assertEquals(
            listOf("https://api.ip.sb/geoip", "https://ipinfo.io/json"),
            SpeedtestManager.candidateIpInfoUrls("   ", listOf("https://api.ip.sb/geoip", "https://ipinfo.io/json"))
        )
    }

    @Test
    fun `the configured address appears only once`() {
        val urls = SpeedtestManager.candidateIpInfoUrls(
            "https://ipinfo.io/json",
            listOf("https://api.ip.sb/geoip", "https://ipinfo.io/json")
        )
        assertEquals(listOf("https://ipinfo.io/json", "https://api.ip.sb/geoip"), urls)
    }

    @Test
    fun `surrounding spaces are trimmed and empty fallbacks are dropped`() {
        assertEquals(
            listOf("https://example.com/ip", "https://ipinfo.io/json"),
            SpeedtestManager.candidateIpInfoUrls(
                "  https://example.com/ip  ",
                listOf("  ", "https://ipinfo.io/json", "")
            )
        )
    }

    @Test
    fun `the built-in list starts with the historical default`() {
        assertTrue(
            SpeedtestManager.candidateIpInfoUrls(null).first() == "https://api.ip.sb/geoip"
        )
    }

    @Test
    fun `myip style json yields an address and a country code`() {
        val info = Gson().fromJson(
            """{"ip":"203.0.113.7","country":"Iran","cc":"IR"}""",
            IPAPIInfo::class.java
        )
        assertEquals("203.0.113.7", info.ip)
        assertEquals("IR", info.cc)
    }

    @Test
    fun `ipinfo style json yields an address and a country code`() {
        val info = Gson().fromJson(
            """{"ip":"198.51.100.4","country":"IR"}""",
            IPAPIInfo::class.java
        )
        assertEquals("198.51.100.4", info.ip)
        assertEquals("IR", info.country)
    }
}
