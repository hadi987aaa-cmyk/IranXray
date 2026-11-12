package com.v2ray.ang.core

import com.google.gson.JsonObject
import com.v2ray.ang.util.JsonUtil
import kotlin.random.Random

/**
 * An XHTTP connection is visible on the wire as a rhythm: with the packaged defaults every POST follows
 * the previous one by the same short interval, so one whole session looks like a metronome — a live
 * capture of a real server showed one exchange every 20 ms for as long as the tunnel stayed open.
 *
 * Sampling that interval per connection keeps the transport doing exactly what it did before, while
 * removing the constant that a single filter rule could otherwise key on. A value the user typed
 * themselves is left alone: this only fills in what is absent.
 */
object XhttpJitter {

    const val KEY_INTERVAL = "scMinPostsIntervalMs"
    const val KEY_PADDING = "xpaddingBytes"

    /** Range the sampled post interval is drawn from, in milliseconds. */
    const val MIN_INTERVAL_MS = 22
    const val MAX_INTERVAL_MS = 55

    /** Range the sampled padding window is drawn from, in bytes. */
    const val MIN_PADDING_BYTES = 150
    const val MAX_PADDING_BYTES = 900

    /**
     * Returns [extra] with the two timing knobs filled in, or [extra] itself when it is not a JSON object.
     * [random] is injectable so tests can pin the sampled values.
     */
    fun apply(extra: String?, random: Random = Random.Default): String {
        val root = try {
            if (extra.isNullOrBlank()) JsonObject() else JsonUtil.parseString(extra)
        } catch (e: RuntimeException) {
            null
        } ?: return extra.orEmpty()

        if (!root.has(KEY_INTERVAL)) {
            root.addProperty(KEY_INTERVAL, random.nextInt(MIN_INTERVAL_MS, MAX_INTERVAL_MS + 1))
        }
        if (!root.has(KEY_PADDING)) {
            val start = random.nextInt(MIN_PADDING_BYTES, MAX_PADDING_BYTES / 2)
            val end = random.nextInt(start + 100, MAX_PADDING_BYTES + 1)
            root.addProperty(KEY_PADDING, "$start-$end")
        }
        return root.toString()
    }
}
