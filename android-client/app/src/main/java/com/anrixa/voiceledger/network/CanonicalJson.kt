package com.anrixa.voiceledger.network

/**
 * Builds a deterministic JSON string (sorted keys, no extra
 * whitespace) from a plain map, so the same transaction always signs
 * to the same bytes.
 *
 * Note: this does NOT need to byte-match the server's own
 * `json.dumps(..., sort_keys=True, ...)` output, and deliberately
 * doesn't try to. The server verifies the ECDSA signature against
 * the literal bytes this client sends and never re-serializes the
 * payload for comparison — see the comment in app/main.py on the
 * server. Sorted keys here are just good hygiene (stable diffs,
 * reproducible signing), not a cross-language contract.
 */
object CanonicalJson {

    fun stringify(payload: Map<String, Any?>): String {
        val sb = StringBuilder()
        writeValue(sortedMapForOutput(payload), sb)
        return sb.toString()
    }

    private fun sortedMapForOutput(map: Map<String, Any?>): Map<String, Any?> =
        map.toSortedMap(compareBy { it })

    private fun writeValue(value: Any?, sb: StringBuilder) {
        when (value) {
            null -> sb.append("null")
            is String -> writeString(value, sb)
            is Boolean -> sb.append(value.toString())
            is Int, is Long -> sb.append(value.toString())
            is Double -> sb.append(formatDouble(value))
            is Map<*, *> -> {
                @Suppress("UNCHECKED_CAST")
                val sorted = sortedMapForOutput(value as Map<String, Any?>)
                sb.append('{')
                sorted.entries.forEachIndexed { i, (k, v) ->
                    if (i > 0) sb.append(',')
                    writeString(k, sb)
                    sb.append(':')
                    writeValue(v, sb)
                }
                sb.append('}')
            }
            is List<*> -> {
                sb.append('[')
                value.forEachIndexed { i, v ->
                    if (i > 0) sb.append(',')
                    writeValue(v, sb)
                }
                sb.append(']')
            }
            else -> throw IllegalArgumentException("Unsupported type in payload: ${value::class}")
        }
    }

    private fun writeString(s: String, sb: StringBuilder) {
        sb.append('"')
        for (c in s) {
            when (c) {
                '"' -> sb.append("\\\"")
                '\\' -> sb.append("\\\\")
                '\n' -> sb.append("\\n")
                '\r' -> sb.append("\\r")
                '\t' -> sb.append("\\t")
                else -> if (c.code < 0x20) sb.append("\\u%04x".format(c.code)) else sb.append(c)
            }
        }
        sb.append('"')
    }

    private fun formatDouble(d: Double): String =
        // Keep currency amounts readable (50000.0, 199.99) without
        // scientific notation; plenty for transaction-sized numbers.
        if (d == d.toLong().toDouble()) "${d.toLong()}.0" else d.toString()
}
