package com.v2ray.ang.ui.main

import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertFalse
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.Test

class ImportMenuActionsTest {

    @Test
    fun aetherIsNotOfferedByABuildWithoutTheCores() {
        assertFalse(importMenuActions(hasOptionalCores = false).contains(ImportMenuAction.Aether))
    }

    @Test
    fun aetherIsOfferedByAFullBuild() {
        assertTrue(importMenuActions(hasOptionalCores = true).contains(ImportMenuAction.Aether))
    }

    @Test
    fun onlyAetherLeavesTheMenu() {
        val lite = importMenuActions(hasOptionalCores = false)
        val full = importMenuActions(hasOptionalCores = true)
        assertEquals(full.size - 1, lite.size)
        assertEquals(full - ImportMenuAction.Aether, lite)
    }
}
