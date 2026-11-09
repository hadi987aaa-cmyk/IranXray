package com.v2ray.ang

import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Test

class AppConfigRepositoryTest {

    @Test
    fun appAndUpdateUrlsPointToTheIranXrayRepository() {
        assertEquals("https://github.com/hadi987aaa-cmyk/IranXray", AppConfig.APP_URL)
        assertEquals(
            "https://api.github.com/repos/hadi987aaa-cmyk/IranXray/releases",
            AppConfig.APP_API_URL,
        )
        assertEquals("${AppConfig.APP_URL}/issues", AppConfig.APP_ISSUES_URL)
    }
}
