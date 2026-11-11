package com.v2ray.ang.core

import com.google.gson.JsonObject
import com.v2ray.ang.util.JsonUtil
import com.v2ray.ang.util.LogUtil
import kotlin.random.Random

/**
 * Shaghali: the one-tap Iran preset ships one fixed TCP write-batching shape (`times` 100, `delayMs` 30,
 * `maxBytes` 16384) to every user who presses it, so a filter rule written against that exact shape would burn
 * every user at once. [apply] samples the three numbers per connection inside the same envelope, which keeps the
 * DPI-defeating batching while removing the shared constant.
 *
 * Only an untouched preset mask is sampled. A mask the user wrote or edited by hand is returned unchanged, because
 * its numbers are a deliberate choice, and so is a mask that carries `udp` or `quicParams` rules we do not sample.
 */
object IranMaskJitter {

    private const val TAG = "IranMaskJitter"

    const val PRESET_TIMES = 100
    const val PRESET_DELAY_MS = 30
    const val PRESET_MAX_BYTES = 16384

    private const val MIN_TIMES = 60
    private const val MAX_TIMES = 160
    private const val MIN_DELAY_MS = 18
    private const val MAX_DELAY_MS = 45
    private const val MIN_MAX_BYTES_KB = 8
    private const val MAX_MAX_BYTES_KB = 28

    /** True when [mask] is still the untouched preset, i.e. a mask [apply] would sample. */
    fun isPresetMask(mask: String?): Boolean = presetRoot(mask) != null

    /**
     * Returns [mask] with its batching numbers re-sampled, or [mask] itself when it is blank, unreadable or not the
     * untouched preset. [random] is injectable so tests can pin the values.
     */
    fun apply(mask: String?, random: Random = Random.Default): String? {
        val root = presetRoot(mask) ?: return mask
        val tcp = root.getAsJsonArray("tcp") ?: return mask
        val rule = tcp.get(0) as? JsonObject ?: return mask
        val settings = rule.getAsJsonObject("settings") ?: return mask
        settings.addProperty("times", random.nextInt(MIN_TIMES, MAX_TIMES + 1))
        settings.addProperty("delayMs", random.nextInt(MIN_DELAY_MS, MAX_DELAY_MS + 1))
        settings.addProperty("maxBytes", random.nextInt(MIN_MAX_BYTES_KB, MAX_MAX_BYTES_KB + 1) * 1024)
        return root.toString()
    }

    /** The parsed root of [mask] only when it is exactly the untouched preset; null otherwise. */
    private fun presetRoot(mask: String?): JsonObject? {
        if (mask.isNullOrBlank()) return null
        // Gson throws on text that is not JSON at all, and a profile can carry anything a user pasted.
        val root = try {
            JsonUtil.parseString(mask)
        } catch (e: RuntimeException) {
            LogUtil.w(TAG, "finalMask is not JSON, leaving it untouched: ${e.message}")
            null
        } ?: return null
        if (root.has("udp") || root.has("quicParams")) return null
        val tcp = root.getAsJsonArray("tcp") ?: return null
        if (tcp.size() != 1) return null
        val rule = tcp.get(0) as? JsonObject ?: return null
        if (rule.get("type")?.asString != "merge") return null
        val settings = rule.getAsJsonObject("settings") ?: return null
        val times = settings.get("times")?.asInt ?: return null
        val delayMs = settings.get("delayMs")?.asInt ?: return null
        val maxBytes = settings.get("maxBytes")?.asInt ?: return null
        if (times != PRESET_TIMES || delayMs != PRESET_DELAY_MS || maxBytes != PRESET_MAX_BYTES) return null
        return root
    }
}
