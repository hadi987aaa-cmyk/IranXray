package com.v2ray.ang.core

import com.v2ray.ang.ui.server.IranPreset
import com.v2ray.ang.util.JsonUtil
import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertNull
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.Test
import kotlin.random.Random

class IranMaskJitterTest {

    private fun settings(mask: String?): Triple<Int, Int, Int> {
        val root = JsonUtil.parseString(mask)!!
        val tcp = root.getAsJsonArray("tcp")!!
        assertEquals(1, tcp.size())
        val rule = tcp.get(0).asJsonObject
        assertEquals("merge", rule.get("type").asString)
        val s = rule.getAsJsonObject("settings")
        return Triple(s.get("times").asInt, s.get("delayMs").asInt, s.get("maxBytes").asInt)
    }

    @Test
    fun `the untouched preset is recognised`() {
        assertTrue(IranMaskJitter.isPresetMask(IranPreset.FINAL_MASK))
    }

    @Test
    fun `sampled numbers stay inside the envelope`() {
        val (times, delayMs, maxBytes) = settings(IranMaskJitter.apply(IranPreset.FINAL_MASK, Random(7)))
        assertTrue(times in 60..160, "times=$times")
        assertTrue(delayMs in 18..45, "delayMs=$delayMs")
        assertTrue(maxBytes in 8192..28672 && maxBytes % 1024 == 0, "maxBytes=$maxBytes")
    }

    @Test
    fun `the same seed samples the same shape`() {
        assertEquals(
            IranMaskJitter.apply(IranPreset.FINAL_MASK, Random(11)),
            IranMaskJitter.apply(IranPreset.FINAL_MASK, Random(11))
        )
    }

    @Test
    fun `a hand written mask is left alone`() {
        val custom = """{"tcp":[{"type":"merge","settings":{"times":50,"delayMs":12,"maxBytes":4096}}]}"""
        assertEquals(custom, IranMaskJitter.apply(custom, Random(3)))
        assertTrue(!IranMaskJitter.isPresetMask(custom))
    }

    @Test
    fun `a mask with udp rules is left alone`() {
        val withUdp =
            """{"tcp":[{"type":"merge","settings":{"times":100,"delayMs":30,"maxBytes":16384}}],"udp":[{"type":"merge","settings":{}}]}"""
        assertEquals(withUdp, IranMaskJitter.apply(withUdp, Random(5)))
    }

    @Test
    fun `blank and unreadable masks come back untouched`() {
        assertEquals("", IranMaskJitter.apply(""))
        assertEquals("not json", IranMaskJitter.apply("not json"))
        assertNull(IranMaskJitter.apply(null))
    }
}
