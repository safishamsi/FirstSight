package com.meta.wearable.dat.externalsampleapps.cameraaccess.platform

data class FocusMarkerParseResult(
    val cleanedText: String,
    val focusTarget: String?,
)

object FocusMarkerParser {
    private val regex = Regex("""<focus:([^>]+)>""", RegexOption.IGNORE_CASE)

    fun parse(text: String): FocusMarkerParseResult {
        val match = regex.find(text)
        val focusTarget = match?.groupValues?.getOrNull(1)?.trim()?.takeIf { it.isNotBlank() }
        val cleaned = text.replace(regex, "").replace(Regex("\\s{2,}"), " ").trimEnd()
        return FocusMarkerParseResult(
            cleanedText = cleaned,
            focusTarget = focusTarget,
        )
    }
}
