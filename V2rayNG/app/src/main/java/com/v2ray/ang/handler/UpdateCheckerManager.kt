package com.v2ray.ang.handler

import android.os.Build
import com.v2ray.ang.AppConfig
import com.v2ray.ang.BuildConfig
import com.v2ray.ang.dto.CheckUpdateResult
import com.v2ray.ang.dto.GitHubRelease
import com.v2ray.ang.dto.UrlContentRequest
import com.v2ray.ang.extension.concatUrl
import com.v2ray.ang.util.HttpUtil
import com.v2ray.ang.util.JsonUtil
import com.v2ray.ang.util.LogUtil
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

object UpdateCheckerManager {
    /** The app version inside an asset name such as `Shaghali_0.6.0_arm64-v8a.apk`. */
    private val ASSET_VERSION = Regex("""Shaghali_(\d+(?:\.\d+)*)_""")

    /** A dotted numeric version, the only shape [compareVersions] can order. */
    private val NUMERIC_VERSION = Regex("""\d+(\.\d+)*""")

    suspend fun checkForUpdate(includePreRelease: Boolean = false): CheckUpdateResult = withContext(Dispatchers.IO) {
        val url = if (includePreRelease) {
            AppConfig.APP_API_URL
        } else {
            AppConfig.APP_API_URL.concatUrl("latest")
        }

        val proxyUsername = SettingsManager.getSocksUsername()
        val proxyPassword = SettingsManager.getSocksPassword()

        var response = HttpUtil.getUrlContent(
            UrlContentRequest(
                url = url,
                timeout = 5000
            )
        )
        if (response.isNullOrEmpty()) {
            val httpPort = SettingsManager.getHttpPort()
            response = HttpUtil.getUrlContent(
                UrlContentRequest(
                    url = url,
                    timeout = 5000,
                    httpPort = httpPort,
                    proxyUsername = proxyUsername,
                    proxyPassword = proxyPassword
                )
            )
                ?: throw IllegalStateException("Failed to get response")
        }

        val latestRelease = if (includePreRelease) {
            JsonUtil.fromJsonSafe(response, Array<GitHubRelease>::class.java)
                ?.firstOrNull()
                ?: throw IllegalStateException("No pre-release found")
        } else {
            JsonUtil.fromJsonSafe(response, GitHubRelease::class.java)
        }
        if (latestRelease == null) {
            return@withContext CheckUpdateResult(hasUpdate = false)
        }

        val latestVersion = releaseVersion(latestRelease.tagName, latestRelease.assets.map { it.name })
        if (latestVersion == null) {
            // A release we cannot order against the installed version must not be offered: an
            // unorderable tag compared as if it were newer would nag the user forever.
            LogUtil.i(
                AppConfig.TAG,
                "Release ${latestRelease.tagName} carries no app version; skipping the update check"
            )
            return@withContext CheckUpdateResult(hasUpdate = false)
        }
        LogUtil.i(
            AppConfig.TAG,
            "Found new version: $latestVersion (current: ${BuildConfig.VERSION_NAME})"
        )

        return@withContext if (compareVersions(latestVersion, BuildConfig.VERSION_NAME) > 0) {
            val downloadUrl = getDownloadUrl(latestRelease, Build.SUPPORTED_ABIS[0])
            CheckUpdateResult(
                hasUpdate = true,
                latestVersion = latestVersion,
                releaseNotes = latestRelease.body,
                downloadUrl = downloadUrl,
                isPreRelease = latestRelease.prerelease
            )
        } else {
            CheckUpdateResult(hasUpdate = false)
        }
    }

    /**
     * The app version a release stands for.
     *
     * Builds are tagged `agent-<run number>`, one per CI run, so the tag says nothing about the
     * app version; the APK name does. A repository that publishes `v<version>` tags keeps working
     * through the tag fallback.
     */
    internal fun releaseVersion(tagName: String, assetNames: List<String>): String? {
        assetNames.firstNotNullOfOrNull { ASSET_VERSION.find(it)?.groupValues?.get(1) }
            ?.let { return it }

        val fromTag = tagName.removePrefix("v")
        return if (NUMERIC_VERSION.matches(fromTag)) fromTag else null
    }

    internal fun compareVersions(version1: String, version2: String): Int {
        // Compare all numeric segments so suffixed tags like "2.3.2-P1" work:
        // "2.3.2-P1" -> [2,3,2,1], "2.3.2" -> [2,3,2], "2.3.2-P2" > "2.3.2-P1" > "2.3.2"
        val numberRegex = Regex("\\d+")
        val v1 = numberRegex.findAll(version1).map { it.value.toInt() }.toList()
        val v2 = numberRegex.findAll(version2).map { it.value.toInt() }.toList()

        for (i in 0 until maxOf(v1.size, v2.size)) {
            val num1 = v1.getOrElse(i) { 0 }
            val num2 = v2.getOrElse(i) { 0 }
            if (num1 != num2) return num1 - num2
        }
        return 0
    }

    private fun getDownloadUrl(release: GitHubRelease, abi: String): String {
        val fDroid = "fdroid"

        val assetsByAbi = release.assets.filter {
            (it.name.contains(abi, true))
        }

        val asset = if (BuildConfig.APPLICATION_ID.contains(fDroid, ignoreCase = true)) {
            assetsByAbi.firstOrNull { it.name.contains(fDroid) }
        } else {
            assetsByAbi.firstOrNull { !it.name.contains(fDroid) }
        }

        return asset?.browserDownloadUrl
            ?: throw IllegalStateException("No compatible APK found")
    }
}
