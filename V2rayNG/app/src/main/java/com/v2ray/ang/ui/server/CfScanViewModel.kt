package com.v2ray.ang.ui.server

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.v2ray.ang.core.CfScanResult
import com.v2ray.ang.core.CfScanRunner
import com.v2ray.ang.core.CfScanTarget
import com.v2ray.ang.core.DefaultCfScanRunner
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

/** Why a scan did not start or did not produce a result, mapped to a string by the screen. */
enum class CfScanProblem { MISSING_SNI, NO_CANDIDATES }

/**
 * What the Cloudflare scan dialog shows.
 *
 * [results] is only meaningful once [running] is false; the screen keeps the previous list
 * while a new run is in flight, so a failed rescan does not blank the addresses the user was
 * about to pick.
 */
data class CfScanState(
    val running: Boolean = false,
    val done: Int = 0,
    val total: Int = 0,
    val results: List<CfScanResult> = emptyList(),
    val problem: CfScanProblem? = null,
    val finished: Boolean = false,
)

/**
 * Runs a Cloudflare address scan for the server editor and exposes it as observable state.
 *
 * The scan itself stays in [CfScanRunner], so this class holds no socket code and can be
 * tested on the JVM.
 */
class CfScanViewModel(
    private val runner: CfScanRunner = DefaultCfScanRunner,
) : ViewModel() {

    @Suppress("PropertyName")
    private val _state = MutableStateFlow(CfScanState())

    val state: StateFlow<CfScanState> = _state.asStateFlow()

    private var job: Job? = null

    /**
     * Starts a scan for [sni]. Calling it while a scan runs replaces that scan.
     *
     * A blank [sni] is refused instead of probed: without a Server Name Indication the
     * handshake says nothing about what the network allows for this profile.
     */
    fun start(sni: String) {
        val host = sni.trim()
        if (host.isEmpty()) {
            _state.value = CfScanState(problem = CfScanProblem.MISSING_SNI, finished = true)
            return
        }
        val targets = runner.candidates()
        if (targets.isEmpty()) {
            _state.value = CfScanState(problem = CfScanProblem.NO_CANDIDATES, finished = true)
            return
        }
        job?.cancel()
        _state.value = CfScanState(running = true, total = targets.size)
        job = viewModelScope.launch {
            val results = try {
                runner.scan(targets, host) { done, total ->
                    _state.update { it.copy(done = done, total = total) }
                }
            } catch (cancel: CancellationException) {
                throw cancel
            } catch (_: Throwable) {
                emptyList()
            }
            _state.update {
                it.copy(running = false, done = it.total, results = results, finished = true)
            }
        }
    }

    /** Cancels the running scan, keeping whatever it has found so far. */
    fun stop() {
        job?.cancel()
        job = null
        _state.update { it.copy(running = false, finished = true) }
    }
}
