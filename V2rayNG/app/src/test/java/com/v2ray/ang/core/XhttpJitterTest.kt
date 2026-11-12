package com.v2ray.ang.core

import com.google.gson.JsonParser
import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertNotNull
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.Test
import kotlin.random.Random

class XhttpJitterTest {

    private fun parsed(result: String) = JsonParser.parseString(result).asJsonObject

    @Test
    fun `a profile without extra gets both timing knobs`() {
        val result = parsed(XhttpJitter.apply(null, Random(7)))

        val interval = result.get(XhttpJitter.KEY_INTERVAL).asInt
        assertTrue(interval in XhttpJitter.MIN_INTERVAL_MS..XhttpJitter.MAX_INTERVAL_MS, "interval=$interval")

        val padding = result.get(XhttpJitter.KEY_PADDING).asString
        val parts = padding.split("-")
        assertEquals(2, parts.size, "padding=$padding")
        assertTrue(parts[0].toInt() < parts[1].toInt(), "padding=$padding")
    }

    @Test
    fun `a blank string behaves like no extra`() {
        val result = parsed(XhttpJitter.apply("   ", Random(3)))
        assertNotNull(result.get(XhttpJitter.KEY_INTERVAL))
    }

    @Test
    fun `the same seed samples the same values`() {
        assertEquals(XhttpJitter.apply(null, Random(11)), XhttpJitter.apply(null, Random(11)))
    }

    @Test
    fun `a hand written interval is kept`() {
        val result = parsed(XhttpJitter.apply("""{"scMinPostsIntervalMs":80}""", Random(5)))
        assertEquals(80, result.get(XhttpJitter.KEY_INTERVAL).asInt)
    }

    @Test
    fun `hand written padding is kept`() {
        val result = parsed(XhttpJitter.apply("""{"xpaddingBytes":"100-200"}""", Random(5)))
        assertEquals("100-200", result.get(XhttpJitter.KEY_PADDING).asString)
    }

    @Test
    fun `other keys survive untouched`() {
        val result = parsed(XhttpJitter.apply("""{"noSSEHeader":true,"scMaxEachPostBytes":500000}""", Random(5)))
        assertTrue(result.get("noSSEHeader").asBoolean)
        assertEquals(500000, result.get("scMaxEachPostBytes").asInt)
    }

    @Test
    fun `text that is not JSON is handed back unchanged`() {
        assertEquals("not json", XhttpJitter.apply("not json", Random(5)))
    }
}
