package com.meta.wearable.dat.externalsampleapps.cameraaccess.gemini

import com.meta.wearable.dat.externalsampleapps.cameraaccess.settings.SettingsManager

object GeminiConfig {
    const val WEBSOCKET_BASE_URL =
        "wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContent"
    const val MODEL = "models/gemini-2.5-flash-native-audio-preview-12-2025"

    const val INPUT_AUDIO_SAMPLE_RATE = 16000
    const val OUTPUT_AUDIO_SAMPLE_RATE = 24000
    const val AUDIO_CHANNELS = 1
    const val AUDIO_BITS_PER_SAMPLE = 16

    const val VIDEO_FRAME_INTERVAL_MS = 1000L
    const val VIDEO_JPEG_QUALITY = 50

    val systemInstruction: String
        get() =
            SettingsManager.geminiSystemPrompt.trim() +
                "\n\nTool contract reminder:\n" +
                "- When a visible object matters in the response, append a marker like `<focus:bottle>` so the platform can auto-focus it.\n" +
                "- `start_guidance(task?, sessionId?)` starts a guided workflow session.\n" +
                "- `locate_object(query, includeSegmentation?)` is for grounding visible objects in the current frame.\n" +
                "- `inspect_object(query?)` returns object information and panel content.\n" +
                "- `guide_step(task?, stepIndex, observedLabel?, objectFound?, sessionId?)` is for the laptop-inspection demo guidance flow.\n" +
                "- `advance_step(sessionId?)` moves a guidance session to the next step.\n" +
                "- `execute(task)` is for all external actions and assistant delegation."

    val apiKey: String
        get() = SettingsManager.geminiAPIKey

    val openClawHost: String
        get() = SettingsManager.openClawHost

    val openClawPort: Int
        get() = SettingsManager.openClawPort

    val openClawHookToken: String
        get() = SettingsManager.openClawHookToken

    val openClawGatewayToken: String
        get() = SettingsManager.openClawGatewayToken

    val visionToolBaseUrl: String
        get() = SettingsManager.visionToolBaseUrl

    val visionToolAuthToken: String
        get() = SettingsManager.visionToolAuthToken

    fun websocketURL(): String? {
        if (apiKey == "YOUR_GEMINI_API_KEY" || apiKey.isEmpty()) return null
        return "$WEBSOCKET_BASE_URL?key=$apiKey"
    }

    val isConfigured: Boolean
        get() = apiKey != "YOUR_GEMINI_API_KEY" && apiKey.isNotEmpty()

    val isOpenClawConfigured: Boolean
        get() = openClawGatewayToken != "YOUR_OPENCLAW_GATEWAY_TOKEN"
                && openClawGatewayToken.isNotEmpty()
                && openClawHost != "http://YOUR_MAC_HOSTNAME.local"

    val isVisionToolConfigured: Boolean
        get() = visionToolBaseUrl.isNotBlank() && !visionToolBaseUrl.contains("YOUR_MAC_HOSTNAME")
}
