package com.v2ray.ang.ui.server

import com.v2ray.ang.util.JsonUtil
import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertNotNull
import org.junit.jupiter.api.Test

class IranPresetTest {

    @Test
    fun finalMaskIsTheMergePreset() {
        val root = JsonUtil.parseString(IranPreset.FINAL_MASK)
        assertNotNull(root, "the preset's finalMask must be valid JSON, or saving the profile rejects it")

        val tcp = root!!.getAsJsonArray("tcp")
        assertEquals(1, tcp.size())

        val rule = tcp[0].asJsonObject
        assertEquals("merge", rule.get("type").asString)

        val settings = rule.getAsJsonObject("settings")
        assertEquals(100, settings.get("times").asInt)
        assertEquals(30, settings.get("delayMs").asInt)
        assertEquals(16384, settings.get("maxBytes").asInt)
    }

    @Test
    fun valuesAreWhatXrayReads() {
        assertEquals("chrome", IranPreset.FINGERPRINT)
        assertEquals("oob.0", IranPreset.DIAL_MODE)
    }
}
