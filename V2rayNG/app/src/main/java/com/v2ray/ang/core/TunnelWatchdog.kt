package com.v2ray.ang.core

/**
 * Decides when the tunnel watchdog restarts the core, and when it stops trying for a while.
 *
 * The rule is pure on purpose: the service loop asks this object, and a JVM test can pin every
 * branch without a device, a socket or a running core.
 *
 * The failure it guards is a tunnel that still reports itself running while nothing passes
 * through it; the user can only clear that by stopping and starting the profile by hand.
 */
object TunnelWatchdog {

    /** How long the loop waits between two probes. */
    const val PROBE_INTERVAL_MS = 45_000L

    /** A probe that has not answered by then counts as a failure. */
    const val PROBE_TIMEOUT_MS = 20_000L

    /** Consecutive failed probes that justify a restart: one is a moment, three are a dead tunnel. */
    const val FAILURES_BEFORE_RESTART = 3

    /** Restarts allowed inside [RESTART_WINDOW_MS] before the watchdog rests for [GIVE_UP_PAUSE_MS]. */
    const val MAX_RESTARTS_PER_WINDOW = 4

    /** The window the restart cap counts, one hour. */
    const val RESTART_WINDOW_MS = 60 * 60 * 1000L

    /** How long the watchdog stops probing once the cap is reached. */
    const val GIVE_UP_PAUSE_MS = 15 * 60 * 1000L

    enum class Decision {
        /** Keep watching: the tunnel is starting, reloading, or only just missed a probe. */
        WAIT,

        /** The tunnel has been dead long enough, restart the core in place. */
        RESTART,

        /** Restarts did not help, leave the tunnel as it is for a while instead of restarting in a loop. */
        GIVE_UP,
    }

    fun decide(
        consecutiveFailures: Int,
        restartsInWindow: Int,
        serviceRunning: Boolean,
        reloading: Boolean,
    ): Decision = when {
        !serviceRunning || reloading -> WAIT
        consecutiveFailures < FAILURES_BEFORE_RESTART -> WAIT
        restartsInWindow >= MAX_RESTARTS_PER_WINDOW -> GIVE_UP
        else -> RESTART
    }
}
