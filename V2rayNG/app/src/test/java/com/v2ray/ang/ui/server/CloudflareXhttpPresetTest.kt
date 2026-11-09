package com.v2ray.ang.ui.server

import com.v2ray.ang.AppConfig.REALITY
import com.v2ray.ang.enums.EConfigType
import com.v2ray.ang.enums.NetworkType
import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertFalse
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.Test

class CloudflareXhttpPresetTest {

    @Test
    fun applyUsesTlsHttp2AndKeepsTheDomainForHostAndSni() {
        val state = ServerUiState(
            configType = EConfigType.VLESS,
            address = "edge.example.com",
            password = "client-id",
            flow = "xtls-rprx-vision",
            network = NetworkType.TCP.type,
            streamSecurity = REALITY,
            publicKeyReality = "keep-existing-key",
            path = "/private-xhttp-path",
        )

        state.applyCloudflareXhttpPreset()

        assertEquals("443", state.port)
        assertEquals(NetworkType.XHTTP.type, state.network)
        assertEquals("auto", state.xhttpMode)
        assertEquals("", state.flow)
        assertEquals("tls", state.streamSecurity)
        assertEquals("chrome", state.fingerPrint)
        assertEquals("h2", state.alpn)
        assertEquals("edge.example.com", state.sni)
        assertEquals("edge.example.com", state.host)
        assertFalse(state.allowInsecure)
        assertEquals("client-id", state.password)
        assertEquals("/private-xhttp-path", state.path)
        assertEquals("keep-existing-key", state.publicKeyReality)
        assertTrue(state.echConfigList.isBlank())
        assertTrue(state.echOutbound.isBlank())
    }

    @Test
    fun applyKeepsConfiguredHostnameWhenAddressIsAnEdgeIp() {
        val state = ServerUiState(
            configType = EConfigType.VLESS,
            address = "104.16.10.20",
            sni = "cdn.example.com",
            host = "cdn.example.com",
        )

        CloudflareXhttpPreset.apply(state)

        assertEquals("104.16.10.20", state.address)
        assertEquals("cdn.example.com", state.sni)
        assertEquals("cdn.example.com", state.host)
    }
}
