package com.v2ray.ang.core

/**
 * The Cloudflare scan as the editor needs it: a candidate list and a probe run.
 *
 * Split out of [CfIpScanner] so a test can drive the editor's view model without opening
 * sockets.
 */
interface CfScanRunner {

    /** The endpoints the editor will try, in the order they are probed. */
    fun candidates(): List<CfScanTarget>

    /** Probes every element of [targets] with [sni] and reports how many are done. */
    suspend fun scan(
        targets: List<CfScanTarget>,
        sni: String,
        onProgress: (done: Int, total: Int) -> Unit,
    ): List<CfScanResult>
}

/** The real scan, over the network. */
object DefaultCfScanRunner : CfScanRunner {

    override fun candidates(): List<CfScanTarget> = CfIpScanner.candidates()

    override suspend fun scan(
        targets: List<CfScanTarget>,
        sni: String,
        onProgress: (done: Int, total: Int) -> Unit,
    ): List<CfScanResult> = CfIpScanner.scan(targets, sni, onProgress = onProgress)
}
