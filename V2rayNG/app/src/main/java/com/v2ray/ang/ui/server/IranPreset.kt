package com.v2ray.ang.ui.server

/**
 * IranXray: the client-side settings a profile needs to survive Iranian filtering, in one pick.
 *
 * The three values are independent of the server, so they can be applied to any profile that already has an address,
 * a port and its TLS/REALITY keys:
 * - [FINGERPRINT] makes the TLS ClientHello look like Chrome's instead of Xray's default uTLS profile.
 * - [FINAL_MASK] batches the first writes of the connection, so DPI that keys on packet boundaries sees no signature.
 * - [DIAL_MODE] sends the first byte as TCP urgent data, so DPI that reads the first packet reads a byte it cannot use.
 *
 * [FINAL_MASK] must stay byte-identical to the "merge" entry of `final_mask_preset_values` in `res/values/arrays.xml`,
 * because the field's own picker offers that same preset and the two paths have to store the same thing.
 */
object IranPreset {

    const val FINGERPRINT = "chrome"

    const val DIAL_MODE = "oob.0"

    val FINAL_MASK = "{\n  \"tcp\": [\n    {\"type\": \"merge\", \"settings\": {\"times\": 100, \"delayMs\": 30, " +
        "\"maxBytes\": 16384}}\n  ]\n}"
}
