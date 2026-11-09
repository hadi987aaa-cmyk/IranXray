package com.v2ray.ang.ui.server

import com.v2ray.ang.core.CfScanResult
import com.v2ray.ang.core.CfScanRunner
import com.v2ray.ang.core.CfScanTarget
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.UnconfinedTestDispatcher
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.setMain
import org.junit.jupiter.api.AfterEach
import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertFalse
import org.junit.jupiter.api.Assertions.assertNull
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.BeforeEach
import org.junit.jupiter.api.Test

class CfScanViewModelTest {

    private val targets = listOf(
        CfScanTarget("104.16.0.1", 443),
        CfScanTarget("104.16.0.2", 443),
        CfScanTarget("172.64.0.9", 8443),
    )

    private class FakeRunner(
        private val targets: List<CfScanTarget>,
        private val results: List<CfScanResult> = emptyList(),
        private val gate: CompletableDeferred<Unit>? = null,
        private val failure: Throwable? = null,
    ) : CfScanRunner {
        var scannedSni: String? = null

        override fun candidates(): List<CfScanTarget> = targets

        override suspend fun scan(
            targets: List<CfScanTarget>,
            sni: String,
            onProgress: (done: Int, total: Int) -> Unit,
        ): List<CfScanResult> {
            scannedSni = sni
            gate?.await()
            failure?.let { throw it }
            onProgress(targets.size, targets.size)
            return results
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @BeforeEach
    fun setUp() {
        Dispatchers.setMain(UnconfinedTestDispatcher())
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @AfterEach
    fun tearDown() {
        Dispatchers.resetMain()
    }

    @Test
    fun `initial state is idle`() {
        val state = CfScanViewModel(FakeRunner(targets)).state.value
        assertFalse(state.running)
        assertFalse(state.finished)
        assertEquals(0, state.total)
        assertTrue(state.results.isEmpty())
        assertNull(state.problem)
    }

    @Test
    fun `blank sni is refused without probing`() {
        val runner = FakeRunner(targets)
        val vm = CfScanViewModel(runner)

        vm.start("   ")

        assertEquals(CfScanProblem.MISSING_SNI, vm.state.value.problem)
        assertTrue(vm.state.value.finished)
        assertFalse(vm.state.value.running)
        assertNull(runner.scannedSni)
    }

    @Test
    fun `no candidates reports a problem`() {
        val vm = CfScanViewModel(FakeRunner(emptyList()))

        vm.start("example.com")

        assertEquals(CfScanProblem.NO_CANDIDATES, vm.state.value.problem)
        assertTrue(vm.state.value.finished)
    }

    @Test
    fun `a completed scan exposes its results and progress`() {
        val found = listOf(CfScanResult("104.16.0.2", 443, 31))
        val runner = FakeRunner(targets, results = found)
        val vm = CfScanViewModel(runner)

        vm.start(" Example.com ")

        val state = vm.state.value
        assertEquals("Example.com", runner.scannedSni)
        assertFalse(state.running)
        assertTrue(state.finished)
        assertEquals(3, state.total)
        assertEquals(3, state.done)
        assertEquals(found, state.results)
        assertNull(state.problem)
    }

    @Test
    fun `the scan is running until the runner returns`() {
        val gate = CompletableDeferred<Unit>()
        val vm = CfScanViewModel(FakeRunner(targets, gate = gate))

        vm.start("example.com")

        assertTrue(vm.state.value.running)
        assertEquals(3, vm.state.value.total)

        gate.complete(Unit)

        assertFalse(vm.state.value.running)
        assertTrue(vm.state.value.finished)
    }

    @Test
    fun `stopping clears the running flag`() {
        val gate = CompletableDeferred<Unit>()
        val vm = CfScanViewModel(FakeRunner(targets, gate = gate))

        vm.start("example.com")
        vm.stop()

        assertFalse(vm.state.value.running)
        assertTrue(vm.state.value.finished)
        gate.complete(Unit)
    }

    @Test
    fun `a failing runner leaves the screen not running`() {
        val vm = CfScanViewModel(FakeRunner(targets, failure = IllegalStateException("boom")))

        vm.start("example.com")

        assertFalse(vm.state.value.running)
    }
}
