package com.v2ray.ang.handler

import com.v2ray.ang.AppConfig
import com.v2ray.ang.dto.IPAPIInfo
import com.v2ray.ang.dto.UrlContentRequest
import com.v2ray.ang.util.HttpUtil
import com.v2ray.ang.util.JsonUtil
import com.v2ray.ang.util.LogUtil
import java.io.IOException
import java.net.InetSocketAddress
import java.net.Socket
import java.net.UnknownHostException

object SpeedtestManager {

    data class RemoteEndpointInfo(
        val country: String?,
        val ipAddress: String?,
    )

    /**
     * Asked in order until one answers. The first entry is the historical default; in Iran that
     * host is frequently unreachable while a plain JSON endpoint still responds, and the caller
     * only needs a country code and an address for the notification.
     */
    private val DEFAULT_IP_INFO_URLS = listOf(
        "https://api.ip.sb/geoip",
        "https://ipinfo.io/json",
        "https://api.myip.com"
    )

    /**
     * Measures the time taken to establish a TCP connection to a given URL and port.
     *
     * @param url The URL to connect to.
     * @param port The port to connect to.
     * @return The connection time in milliseconds, or -1 if the connection failed.
     */
    fun socketConnectTime(url: String, port: Int, timeoutMs: Int = 1500): Long {
        var socket: Socket? = null
        val start = System.currentTimeMillis()

        try {
            socket = Socket()
            socket.connect(InetSocketAddress(url, port), timeoutMs)

            return System.currentTimeMillis() - start
        } catch (e: UnknownHostException) {
            LogUtil.e(AppConfig.TAG, "Unknown host: $url", e)
        } catch (e: IOException) {
            LogUtil.e(AppConfig.TAG, "socketConnectTime IOException: ${e.message}")
        } catch (e: Exception) {
            LogUtil.e(AppConfig.TAG, "Failed to establish socket connection to $url:$port", e)
        } finally {
            socket?.let { s ->
                try {
                    if (!s.isClosed) {
                        s.close()
                    }
                } catch (closeEx: IOException) {
                }
            }
        }
        return -1
    }

    /**
     * The configured address first, then the built-in ones. A blank setting is simply skipped, so
     * a user who clears the field still gets an answer from the next provider.
     */
    internal fun candidateIpInfoUrls(
        configured: String?,
        fallback: List<String> = DEFAULT_IP_INFO_URLS
    ): List<String> = buildList {
        configured?.trim()?.takeIf { it.isNotEmpty() }?.let { add(it) }
        fallback.forEach { raw ->
            val url = raw.trim()
            if (url.isNotEmpty() && url !in this) add(url)
        }
    }

    fun getRemoteIPInfo(): RemoteEndpointInfo? {
        val proxyUsername = SettingsManager.getSocksUsername()
        val proxyPassword = SettingsManager.getSocksPassword()
        val httpPort = SettingsManager.getHttpPort()
        if (httpPort == 0) return null

        val urls = candidateIpInfoUrls(MmkvManager.decodeSettingsString(AppConfig.PREF_IP_API_URL))
        for (url in urls) {
            val info = queryIpInfo(url, httpPort, proxyUsername, proxyPassword)
            if (info != null) return info
        }
        return null
    }

    private fun queryIpInfo(
        url: String,
        httpPort: Int,
        proxyUsername: String?,
        proxyPassword: String?
    ): RemoteEndpointInfo? {
        val content = HttpUtil.getUrlContent(
            UrlContentRequest(
                url = url,
                timeout = 4000,
                httpPort = httpPort,
                proxyUsername = proxyUsername,
                proxyPassword = proxyPassword
            )
        ) ?: return null
        val ipInfo = JsonUtil.fromJsonSafe(content, IPAPIInfo::class.java) ?: return null

        val ip = listOf(
            ipInfo.ip,
            ipInfo.clientIp,
            ipInfo.ip_addr,
            ipInfo.query
        ).firstOrNull { !it.isNullOrBlank() }

        val country = listOf(
            ipInfo.country_code,
            ipInfo.cc,
            ipInfo.countryCode,
            ipInfo.country,
            ipInfo.location?.country_code
        ).firstOrNull { !it.isNullOrBlank() }

        if (ip.isNullOrBlank() && country.isNullOrBlank()) return null

        return RemoteEndpointInfo(
            country = country,
            ipAddress = ip,
        )
    }
}
