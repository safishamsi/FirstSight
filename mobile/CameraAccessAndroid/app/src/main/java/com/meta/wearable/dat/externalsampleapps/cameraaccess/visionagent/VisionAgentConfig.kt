package com.meta.wearable.dat.externalsampleapps.cameraaccess.visionagent

import com.meta.wearable.dat.externalsampleapps.cameraaccess.settings.SettingsManager

object VisionAgentConfig {
    val baseUrl: String
        get() = SettingsManager.backendBaseUrl.trim().removeSuffix("/")

    val userId: String
        get() = SettingsManager.backendUserId.trim()

    val userName: String
        get() = SettingsManager.backendUserName.trim()

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
}
