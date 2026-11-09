package com.v2ray.ang.core

import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertNotNull
import org.junit.jupiter.api.Assertions.assertNull
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.Test
import kotlin.random.Random

class CfIpScannerTest {

    private fun ipToLong(ip: String): Long =
        ip.split('.').fold(0L) { acc, part -> (acc shl 8) or part.toLong() }

    @Test
    fun `candidates produce requested count per port`() {
        val targets = CfIpScanner.candidates(
            ranges = listOf("104.16.0.0/13"),
            ports = listOf(443, 8443),
            perPort = 8,
            random = Random(7),
        )
        assertEquals(8, targets.count { it.port == 443 })
        assertEquals(8, targets.count { it.port == 8443 })
        assertEquals(targets.size, targets.distinct().size)
    }

    @Test
    fun `candidates stay inside the configured range`() {
        val network = ipToLong("104.16.0.0")
        val targets = CfIpScanner.candidates(
            ranges = listOf("104.16.0.0/13"),
            ports = listOf(443),
            perPort = 200,
            random = Random(11),
        )
        assertTrue(targets.isNotEmpty())
        for (target in targets) {
            val value = ipToLong(target.address)
            assertTrue(value in network..(network + (1L shl 19) - 1), target.address)
        }
    }

    @Test
    fun `candidates are deterministic for a seeded random`() {
        val first = CfIpScanner.candidates(perPort = 5, random = Random(42))
        val second = CfIpScanner.candidates(perPort = 5, random = Random(42))
        assertEquals(first, second)
    }

    @Test
    fun `candidates skip invalid ranges`() {
        val targets = CfIpScanner.candidates(
            ranges = listOf("not-a-cidr", "104.16.0.0/33", "104.16.0.0", "172.64.0.0/13"),
            ports = listOf(443),
            perPort = 3,
            random = Random(3),
        )
        assertEquals(3, targets.size)
        val network = ipToLong("172.64.0.0")
        for (target in targets) {
            val value = ipToLong(target.address)
            assertTrue(value in network..(network + (1L shl 19) - 1), target.address)
        }
    }

    @Test
    fun `candidates return empty when nothing can be parsed`() {
        assertTrue(CfIpScanner.candidates(ranges = listOf("garbage"), perPort = 4).isEmpty())
        assertTrue(CfIpScanner.candidates(perPort = 0).isEmpty())
    }

    @Test
    fun `parseCidr normalizes the network address`() {
        assertEquals(ipToLong("104.16.0.0") to 19, CfIpScanner.parseCidr("104.16.5.7/13"))
        assertEquals(ipToLong("10.0.0.5") to 0, CfIpScanner.parseCidr("10.0.0.5/32"))
        assertNull(CfIpScanner.parseCidr("10.0.0.0/7"))
        assertNull(CfIpScanner.parseCidr("10.0.0.256/24"))
        assertNull(CfIpScanner.parseCidr("10.0.0/24"))
        assertNull(CfIpScanner.parseCidr("10.0.0.0/24/8"))
    }

    @Test
    fun `longToIp round trips`() {
        assertEquals("188.114.96.1", CfIpScanner.longToIp(ipToLong("188.114.96.1")))
        assertEquals("0.0.0.0", CfIpScanner.longToIp(0))
        assertEquals("255.255.255.255", CfIpScanner.longToIp(4294967295L))
        assertNotNull(CfIpScanner.longToIp(1))
    }
}
