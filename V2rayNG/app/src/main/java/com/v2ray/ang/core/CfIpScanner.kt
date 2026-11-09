package com.v2ray.ang.core

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.sync.Semaphore
import kotlinx.coroutines.sync.withPermit
import kotlinx.coroutines.withContext
import java.net.InetSocketAddress
import java.util.concurrent.atomic.AtomicInteger
import javax.net.ssl.SNIHostName
import javax.net.ssl.SSLContext
import javax.net.ssl.SSLSocket
import kotlin.random.Random

/**
 * A candidate endpoint for a Cloudflare-fronted (orange cloud) proxy.
 *
 * Only the address and port are scanned; the SNI/Host stay the ones of the user's profile,
 * because the TLS handshake is exactly what the Iranian DPI inspects.
 */
data class CfScanTarget(val address: String, val port: Int) {
    override fun toString(): String = "$address:$port"
}

/** A candidate that completed a TLS handshake with the requested SNI. */
data class CfScanResult(val address: String, val port: Int, val latencyMs: Long)

/**
 * Scans Cloudflare edge addresses for endpoints that still complete a TLS handshake with a
 * given SNI. Used when a profile is fronted by Cloudflare (orange cloud) and the anycast
 * address the profile currently points at is throttled or blocked.
 */
object CfIpScanner {

    /** Cloudflare edge ranges that are commonly reachable from Iran. */
    val DEFAULT_RANGES: List<String> = listOf(
        "104.16.0.0/13",
        "104.24.0.0/14",
        "172.64.0.0/13",
        "188.114.96.0/20",
        "162.159.192.0/24",
        "162.159.193.0/24",
    )

    /**
     * Ports Cloudflare answers on. 443 is the default; the rest are the alternative
     * HTTPS ports that are frequently left open when 443 is blocked on a path.
     */
    val DEFAULT_PORTS: List<Int> = listOf(443, 2053, 2083, 2087, 2096, 8443)

    private const val MAX_CONCURRENCY = 32

    /**
     * Builds a pseudo-random candidate list: [perPort] addresses per port, drawn from
     * [ranges]. Invalid CIDR entries are skipped instead of throwing, so a user-supplied
     * list can never crash the scan.
     */
    fun candidates(
        ranges: List<String> = DEFAULT_RANGES,
        ports: List<Int> = DEFAULT_PORTS,
        perPort: Int = 64,
        random: Random = Random.Default,
    ): List<CfScanTarget> {
        if (perPort <= 0) return emptyList()
        val blocks = ranges.mapNotNull { parseCidr(it) }
        if (blocks.isEmpty()) return emptyList()

        val result = LinkedHashSet<CfScanTarget>()
        for (port in ports) {
            var guard = 0
            while (result.count { it.port == port } < perPort && guard < perPort * 32) {
                guard++
                val (base, hostBits) = blocks[random.nextInt(blocks.size)]
                val offset = if (hostBits == 0) 0L else random.nextLong(0, 1L shl hostBits)
                result.add(CfScanTarget(longToIp(base + offset), port))
            }
        }
        return result.toList()
    }

    /**
     * Completes a TLS handshake against one candidate with [sni] and returns the elapsed
     * milliseconds, or null when the handshake failed or timed out.
     */
    suspend fun probe(target: CfScanTarget, sni: String, timeoutMs: Int = 2500): Long? =
        withContext(Dispatchers.IO) {
            var socket: SSLSocket? = null
            val started = System.nanoTime()
            try {
                val ssl = SSLContext.getInstance("TLS").socketFactory.createSocket() as SSLSocket
                socket = ssl
                ssl.connect(InetSocketAddress(target.address, target.port), timeoutMs)
                ssl.soTimeout = timeoutMs
                val params = ssl.sslParameters
                if (sni.isNotBlank()) {
                    params.serverNames = listOf(SNIHostName(sni.trim()))
                }
                params.endpointIdentificationAlgorithm = null
                ssl.sslParameters = params
                ssl.startHandshake()
                (System.nanoTime() - started) / 1_000_000L
            } catch (_: Throwable) {
                null
            } finally {
                try {
                    socket?.close()
                } catch (_: Throwable) {
                    // Closing a half-open TLS socket is best effort.
                }
            }
        }

    /**
     * Probes every candidate with bounded concurrency and returns the successful ones,
     * fastest first.
     */
    suspend fun scan(
        targets: List<CfScanTarget>,
        sni: String,
        timeoutMs: Int = 2500,
        onProgress: ((done: Int, total: Int) -> Unit)? = null,
    ): List<CfScanResult> = coroutineScope {
        val gate = Semaphore(MAX_CONCURRENCY)
        val total = targets.size
        val done = AtomicInteger(0)
        targets.map { target ->
            async(Dispatchers.IO) {
                gate.withPermit {
                    val result = probe(target, sni, timeoutMs)
                        ?.let { CfScanResult(target.address, target.port, it) }
                    onProgress?.invoke(done.incrementAndGet(), total)
                    result
                }
            }
        }.awaitAll().filterNotNull().sortedBy { it.latencyMs }
    }

    /** Parses `a.b.c.d/prefix` into (network address, number of host bits). */
    internal fun parseCidr(cidr: String): Pair<Long, Int>? {
        val parts = cidr.trim().split('/')
        if (parts.size != 2) return null
        val prefix = parts[1].toIntOrNull() ?: return null
        if (prefix !in 8..32) return null
        val ip = parts[0].trim().split('.')
        if (ip.size != 4) return null
        var value = 0L
        for (octet in ip) {
            val n = octet.toIntOrNull() ?: return null
            if (n !in 0..255) return null
            value = (value shl 8) or n.toLong()
        }
        val hostBits = 32 - prefix
        val network = if (hostBits == 0) value else value and (-1L shl hostBits)
        return network to hostBits
    }

    internal fun longToIp(value: Long): String = buildString {
        append((value shr 24) and 0xFF)
        append('.')
        append((value shr 16) and 0xFF)
        append('.')
        append((value shr 8) and 0xFF)
        append('.')
        append(value and 0xFF)
    }
}
