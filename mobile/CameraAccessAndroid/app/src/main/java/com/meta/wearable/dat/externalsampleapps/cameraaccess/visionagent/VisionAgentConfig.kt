package com.meta.wearable.dat.externalsampleapps.cameraaccess.visionagent

import com.meta.wearable.dat.externalsampleapps.cameraaccess.settings.SettingsManager

object VisionAgentConfig {
    val baseUrl: String
        get() = SettingsManager.backendBaseUrl.trim().removeSuffix("/")

    val userId: String
        get() = SettingsManager.backendUserId.trim()

    val userName: String
        get() = SettingsManager.backendUserName.trim()

    data class RuntimeConfig(
        val speechPipeline: String,
        val enablePoseProcessor: Boolean,
        val geminiLlmModel: String,
        val fastWhisperModelSize: String,
        val fastWhisperDevice: String,
        val pipelineTurnDelayMs: Int,
        val backendTtsEnabled: Boolean,
    )

    val runtimeConfig: RuntimeConfig
        get() = RuntimeConfig(
            speechPipeline = SettingsManager.backendSpeechPipeline,
            enablePoseProcessor = SettingsManager.backendEnablePoseProcessor,
            geminiLlmModel = SettingsManager.backendGeminiModel,
            fastWhisperModelSize = SettingsManager.backendFastWhisperModelSize,
            fastWhisperDevice = SettingsManager.backendFastWhisperDevice,
            pipelineTurnDelayMs = SettingsManager.backendTurnDelayMs,
            backendTtsEnabled = SettingsManager.backendTtsEnabled,
        )

    val isConfigured: Boolean
        get() = baseUrl.isNotBlank() && !baseUrl.contains("YOUR_MAC_HOSTNAME")

    fun sessionsUrl(): String? {
        if (!isConfigured) return null
        return "${baseUrl}/sessions"
    }

    fun streamUrl(sessionId: String): String? {
        if (!isConfigured || sessionId.isBlank()) return null
        return when {
            baseUrl.startsWith("https://") -> {
                "wss://${baseUrl.removePrefix("https://")}/sessions/${sessionId}/stream"
            }

            baseUrl.startsWith("http://") -> {
                "ws://${baseUrl.removePrefix("http://")}/sessions/${sessionId}/stream"
            }

            else -> "ws://${baseUrl}/sessions/${sessionId}/stream"
        }
    }

    fun sessionStatusUrl(sessionId: String): String? {
        if (!isConfigured || sessionId.isBlank()) return null
        return "${baseUrl}/sessions/${sessionId}"
    }

    fun checklistSetUrl(sessionId: String): String? {
        if (!isConfigured || sessionId.isBlank()) return null
        return "${baseUrl}/sessions/${sessionId}/checklist/set"
    }

    fun protocolsUrl(): String? {
        if (!isConfigured) return null
        return "${baseUrl}/protocols"
    }

    fun protocolSearchUrl(): String? {
        if (!isConfigured) return null
        return "${baseUrl}/protocols/search"
    }

    fun protocolDetailUrl(protocolId: String): String? {
        if (!isConfigured || protocolId.isBlank()) return null
        return "${baseUrl}/protocols/${protocolId}"
    }
}
