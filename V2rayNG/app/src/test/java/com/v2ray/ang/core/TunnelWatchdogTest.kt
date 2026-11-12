package com.v2ray.ang.core

import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.Test

class TunnelWatchdogTest {

    @Test
    fun `a single missed probe only waits`() {
        assertEquals(
            TunnelWatchdog.Decision.WAIT,
            TunnelWatchdog.decide(consecutiveFailures = 1, restartsInWindow = 0, serviceRunning = true, reloading = false),
        )
    }

    @Test
    fun `two missed probes still wait`() {
        assertEquals(
            TunnelWatchdog.Decision.WAIT,
            TunnelWatchdog.decide(consecutiveFailures = 2, restartsInWindow = 0, serviceRunning = true, reloading = false),
        )
    }

    @Test
    fun `three missed probes restart the core`() {
        assertEquals(
            TunnelWatchdog.Decision.RESTART,
            TunnelWatchdog.decide(consecutiveFailures = 3, restartsInWindow = 0, serviceRunning = true, reloading = false),
        )
    }

    @Test
    fun `a stopped service is not restarted by the watchdog`() {
        assertEquals(
            TunnelWatchdog.Decision.WAIT,
            TunnelWatchdog.decide(consecutiveFailures = 9, restartsInWindow = 0, serviceRunning = false, reloading = false),
        )
    }

    @Test
    fun `a reload in flight is left alone`() {
        assertEquals(
            TunnelWatchdog.Decision.WAIT,
            TunnelWatchdog.decide(consecutiveFailures = 9, restartsInWindow = 0, serviceRunning = true, reloading = true),
        )
    }

    @Test
    fun `the restart cap turns into a rest instead of a loop`() {
        assertEquals(
            TunnelWatchdog.Decision.GIVE_UP,
            TunnelWatchdog.decide(
                consecutiveFailures = 5,
                restartsInWindow = TunnelWatchdog.MAX_RESTARTS_PER_WINDOW,
                serviceRunning = true,
                reloading = false,
            ),
        )
    }

    @Test
    fun `one restart below the cap is still allowed`() {
        assertEquals(
            TunnelWatchdog.Decision.RESTART,
            TunnelWatchdog.decide(
                consecutiveFailures = 4,
                restartsInWindow = TunnelWatchdog.MAX_RESTARTS_PER_WINDOW - 1,
                serviceRunning = true,
                reloading = false,
            ),
        )
    }

    @Test
    fun `the loop cannot spin`() {
        assertTrue(TunnelWatchdog.PROBE_INTERVAL_MS >= 15_000L)
        assertTrue(TunnelWatchdog.PROBE_TIMEOUT_MS < TunnelWatchdog.PROBE_INTERVAL_MS)
        assertTrue(TunnelWatchdog.FAILURES_BEFORE_RESTART in 2..5)
        assertTrue(TunnelWatchdog.GIVE_UP_PAUSE_MS >= TunnelWatchdog.RESTART_WINDOW_MS / 4)
    }
}
