package com.v2ray.ang.handler

import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertNull
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.Test

class UpdateCheckerManagerTest {

    @Test
    fun readsTheVersionOutOfTheAgentAssetName() {
        val version = UpdateCheckerManager.releaseVersion("agent-20", listOf("IranXray_0.6.0_arm64-v8a.apk"))

        assertEquals("0.6.0", version)
    }

    @Test
    fun readsTheVersionFromTheSecondAssetWhenTheFirstHasNone() {
        val version = UpdateCheckerManager.releaseVersion(
            "agent-20",
            listOf("release-notes.txt", "IranXray_0.5.0_armeabi-v7a.apk")
        )

        assertEquals("0.5.0", version)
    }

    @Test
    fun fallsBackToAVersionedTag() {
        assertEquals("2.3.15", UpdateCheckerManager.releaseVersion("v2.3.15", emptyList()))
        assertEquals("2.3.15", UpdateCheckerManager.releaseVersion("2.3.15", emptyList()))
    }

    @Test
    fun refusesATagItCannotOrder() {
        assertNull(UpdateCheckerManager.releaseVersion("agent-20", emptyList()))
        assertNull(UpdateCheckerManager.releaseVersion("nightly", emptyList()))
    }

    @Test
    fun ordersDottedVersionsNumerically() {
        assertTrue(UpdateCheckerManager.compareVersions("0.10.0", "0.9.0") > 0)
        assertTrue(UpdateCheckerManager.compareVersions("0.6.0", "0.6.1") < 0)
        assertEquals(0, UpdateCheckerManager.compareVersions("0.6.0", "0.6.0"))
    }

    @Test
    fun theNewestBuildOfTheInstalledVersionIsNotAnUpdate() {
        val latest = UpdateCheckerManager.releaseVersion("agent-20", listOf("IranXray_0.5.0_arm64-v8a.apk"))

        assertEquals(0, UpdateCheckerManager.compareVersions(latest!!, "0.5.0"))
    }
}
